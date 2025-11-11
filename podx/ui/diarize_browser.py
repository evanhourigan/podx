"""Interactive two-phase browser for selecting base transcripts to diarize."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..logging import get_logger
from ..ui_styles import (
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    TABLE_TITLE_COL_STYLE,
)
from .episode_browser_tui import ModelLevelProcessingBrowser
from .two_phase_browser import TwoPhaseTranscriptBrowser

logger = get_logger(__name__)


def scan_diarizable_transcripts(scan_dir: Path) -> List[Dict[str, Any]]:
    """
    DEPRECATED: Legacy function for backward compatibility.
    Use DiarizeTwoPhase.browse() for interactive selection instead.

    Scan directory for base transcript files.
    Returns list of base transcripts with their metadata and diarization status.

    In v2.0, diarization runs alignment internally, so we scan for base
    (non-aligned) transcripts instead of aligned ones.
    """
    transcripts = []
    seen_transcripts = set()  # Track unique transcripts to avoid duplicates

    # Find all base transcript files (format: transcript-{model}.json)
    for transcript_file in scan_dir.rglob("transcript-*.json"):
        # Skip non-base transcript files (diarized, preprocessed, aligned)
        filename = transcript_file.stem
        if any(
            keyword in filename for keyword in ["diarized", "preprocessed", "aligned"]
        ):
            continue

        try:
            # Load transcript data
            transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))

            # Extract ASR model from filename
            # Format: transcript-{model}.json
            if filename.startswith("transcript-"):
                asr_model = filename[len("transcript-") :]
            else:
                continue

            # Create unique key to avoid duplicates (episode dir + asr model)
            unique_key = (str(transcript_file.parent), asr_model)
            if unique_key in seen_transcripts:
                continue
            seen_transcripts.add(unique_key)

            # Get audio path
            audio_path = transcript_data.get("audio_path")
            if not audio_path:
                continue

            audio_path = Path(audio_path)
            if not audio_path.exists():
                continue

            # Check if diarized version exists (new format first, then legacy)
            diarized_file_new = (
                transcript_file.parent / f"transcript-diarized-{asr_model}.json"
            )
            diarized_file_legacy = (
                transcript_file.parent / f"diarized-transcript-{asr_model}.json"
            )
            is_diarized = diarized_file_new.exists() or diarized_file_legacy.exists()
            # Use new format for output
            diarized_file = diarized_file_new

            # Try to get episode metadata for better display
            episode_meta_file = transcript_file.parent / "episode-meta.json"
            episode_meta = {}
            if episode_meta_file.exists():
                try:
                    episode_meta = json.loads(
                        episode_meta_file.read_text(encoding="utf-8")
                    )
                except Exception:
                    episode_meta = {}

            transcripts.append(
                {
                    "transcript_file": transcript_file,
                    "transcript_data": transcript_data,
                    "audio_path": audio_path,
                    "asr_model": asr_model,
                    "is_diarized": is_diarized,
                    "diarized_file": diarized_file,
                    "episode_meta": episode_meta,
                    "directory": transcript_file.parent,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to parse {transcript_file}: {e}")
            continue

    # Sort by date (most recent first) then by show name
    def sort_key(t):
        date_str = t["episode_meta"].get("episode_published", "")
        return (date_str, t["episode_meta"].get("show", ""))

    transcripts.sort(key=sort_key, reverse=True)
    return transcripts


class DiarizeTwoPhase(TwoPhaseTranscriptBrowser):
    """Two-phase browser: select episode → select base transcript to diarize."""

    def scan_transcripts(self, episode_dir: Path) -> List[Dict[str, Any]]:
        """Scan episode directory for base (non-diarized, non-preprocessed) transcripts.

        Args:
            episode_dir: Episode directory to scan

        Returns:
            List of base transcript dictionaries with metadata
        """
        transcripts = []

        # Find all base transcript files in this episode directory
        for transcript_file in episode_dir.glob("transcript-*.json"):
            # Skip non-base transcript files
            filename = transcript_file.stem
            if any(
                keyword in filename
                for keyword in ["diarized", "preprocessed", "aligned"]
            ):
                continue

            try:
                # Load transcript data
                transcript_data = json.loads(
                    transcript_file.read_text(encoding="utf-8")
                )

                # Extract ASR model from filename
                if filename.startswith("transcript-"):
                    asr_model = filename[len("transcript-") :]
                else:
                    continue

                # Get audio path
                audio_path = transcript_data.get("audio_path")
                if not audio_path:
                    continue

                audio_path = Path(audio_path)
                if not audio_path.exists():
                    continue

                # Check if diarized version exists
                diarized_file_new = (
                    episode_dir / f"transcript-diarized-{asr_model}.json"
                )
                diarized_file_legacy = (
                    episode_dir / f"diarized-transcript-{asr_model}.json"
                )
                is_diarized = (
                    diarized_file_new.exists() or diarized_file_legacy.exists()
                )
                diarized_file = diarized_file_new

                # Load episode metadata
                episode_meta_file = episode_dir / "episode-meta.json"
                episode_meta = {}
                if episode_meta_file.exists():
                    try:
                        episode_meta = json.loads(
                            episode_meta_file.read_text(encoding="utf-8")
                        )
                    except Exception:
                        pass

                transcripts.append(
                    {
                        "transcript_file": transcript_file,
                        "transcript_data": transcript_data,
                        "audio_path": audio_path,
                        "asr_model": asr_model,
                        "is_diarized": is_diarized,
                        "diarized_file": diarized_file,
                        "episode_meta": episode_meta,
                        "directory": episode_dir,
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to parse {transcript_file}: {e}")
                continue

        # Sort by ASR model name
        transcripts.sort(key=lambda t: t["asr_model"])
        return transcripts

    def get_transcript_title(self, transcript: Dict[str, Any]) -> str:
        """Get display title for transcript confirmation.

        Args:
            transcript: Transcript dictionary

        Returns:
            Title string combining model and status
        """
        asr_model = transcript["asr_model"]
        status = "✓ diarized" if transcript["is_diarized"] else "○ not diarized"
        return f"{asr_model} ({status})"

    def display_transcript_page(self, browser) -> None:
        """Display transcript selection table for current page.

        Args:
            browser: TranscriptBrowser instance with pagination info
        """
        if not self.console:
            return

        # Calculate page bounds
        start_idx = browser.current_page * browser.items_per_page
        end_idx = min(start_idx + browser.items_per_page, len(browser.items))
        page_items = browser.items[start_idx:end_idx]

        # Create title
        title = f"📝 Select Base Transcript to Diarize (Page {browser.current_page + 1}/{browser.total_pages})"

        # Compute dynamic Title width
        term_width = self.console.size.width
        fixed_widths = {"num": 4, "model": 30, "status": 20}
        borders_allowance = 16
        title_width = max(
            30, term_width - sum(fixed_widths.values()) - borders_allowance
        )

        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            border_style=TABLE_BORDER_STYLE,
            title=title,
            expand=False,
        )
        table.add_column(
            "#",
            style=TABLE_NUM_STYLE,
            width=fixed_widths["num"],
            justify="right",
            no_wrap=True,
        )
        table.add_column(
            "ASR Model",
            style="cyan",
            width=fixed_widths["model"],
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            "Status", style="magenta", width=fixed_widths["status"], no_wrap=True
        )
        table.add_column(
            "Episode Title",
            style=TABLE_TITLE_COL_STYLE,
            width=title_width,
            no_wrap=True,
            overflow="ellipsis",
        )

        for idx, item in enumerate(page_items, start=start_idx + 1):
            asr_model = item["asr_model"]
            status = "✓ Diarized" if item["is_diarized"] else "○ Not diarized"
            episode_title = item["episode_meta"].get("episode_title", "Unknown")

            table.add_row(str(idx), asr_model, status, episode_title)

        self.console.print(table)

        # Show navigation options in Panel
        options = []
        options.append(f"[cyan]1-{len(browser.items)}[/cyan]: Select transcript")

        if browser.current_page < browser.total_pages - 1:
            options.append("[yellow]N[/yellow]: Next page")

        if browser.current_page > 0:
            options.append("[yellow]P[/yellow]: Previous page")

        options.append("[red]Q[/red]: Quit")

        options_text = " • ".join(options)
        panel = Panel(
            options_text, title="Options", border_style="blue", padding=(0, 1)
        )
        self.console.print(panel)

    def browse(self) -> Optional[Dict[str, Any]]:
        """Run two-phase selection using Textual TUI: episode → transcript.

        Returns:
            Selected transcript dictionary, or None if cancelled
        """
        from ..logging import restore_logging, suppress_logging
        from .episode_selector import scan_episode_status

        # Phase 1: Select episode using Textual TUI
        # First scan all episodes and filter to only those with base transcripts
        suppress_logging()
        try:
            episodes = scan_episode_status(self.scan_dir)

            # Apply show filter if provided
            if self.show_filter:
                s_l = self.show_filter.lower()
                episodes = [e for e in episodes if s_l in (e.get("show", "").lower())]

            # Filter to only episodes with base transcripts
            episodes_with_transcripts = []
            for ep in episodes:
                transcripts = self.scan_transcripts(ep["directory"])
                if transcripts:
                    episodes_with_transcripts.append(ep)

            if not episodes_with_transcripts:
                restore_logging()
                if self.show_filter:
                    print(
                        f"❌ No episodes with base transcripts found for show '{self.show_filter}' in {self.scan_dir}"
                    )
                else:
                    print(
                        f"❌ No episodes with base transcripts found in {self.scan_dir}"
                    )
                raise SystemExit(1)

            # Sort newest first
            episodes_sorted = sorted(
                episodes_with_transcripts,
                key=lambda x: (x["date"], x["show"]),
                reverse=True,
            )

            # Run the TUI
            from .episode_browser_tui import EpisodeBrowserTUI

            app = EpisodeBrowserTUI(episodes_sorted, self.scan_dir)
            result = app.run()

            if result == (None, None):
                restore_logging()
                print("❌ Diarization cancelled")
                raise SystemExit(0)

            episode, episode_meta = result

        finally:
            restore_logging()

        if not episode:
            return None

        # Phase 2: Select transcript using Textual TUI
        transcripts = self.scan_transcripts(episode["directory"])

        if not transcripts:
            print(
                f"❌ No base transcripts found in episode: {episode.get('title', 'Unknown')}"
            )
            raise SystemExit(0)

        # Use ModelLevelProcessingBrowser for transcript selection
        app = ModelLevelProcessingBrowser(
            items=transcripts,
            model_key="asr_model",
            status_key="is_diarized",
        )
        app.TITLE = "Select Base Transcript to Diarize"
        selected_transcript = app.run()

        return selected_transcript
