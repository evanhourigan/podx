"""Interactive two-phase browser for selecting transcripts to preprocess."""

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
from .episode_browser_tui import ModelLevelProcessingBrowser, select_episode_with_tui
from .two_phase_browser import TwoPhaseTranscriptBrowser

logger = get_logger(__name__)


class PreprocessTwoPhase(TwoPhaseTranscriptBrowser):
    """Two-phase browser: select episode → select most-processed transcript to preprocess."""

    def scan_transcripts(self, episode_dir: Path) -> List[Dict[str, Any]]:
        """Scan episode directory for most-processed transcript per ASR model.

        Processing priority (highest to lowest):
        1. Preprocessed transcript (transcript-preprocessed-{model}.json)
        2. Diarized transcript (transcript-diarized-{model}.json)
        3. Base transcript (transcript-{model}.json)

        Args:
            episode_dir: Episode directory to scan

        Returns:
            List of most-processed transcript dictionaries (one per ASR model)
        """
        # Track best transcript for each ASR model
        best_transcripts: Dict[str, Dict[str, Any]] = {}

        # Scan for all transcript files
        for transcript_file in episode_dir.glob("transcript-*.json"):
            filename = transcript_file.stem

            try:
                # Load transcript data
                transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))

                # Determine ASR model and processing level
                asr_model = None
                processing_level = 0  # 0=base, 1=diarized, 2=preprocessed

                if filename.startswith("transcript-preprocessed-"):
                    asr_model = filename[len("transcript-preprocessed-") :]
                    processing_level = 2
                elif filename.startswith("transcript-diarized-"):
                    asr_model = filename[len("transcript-diarized-") :]
                    processing_level = 1
                elif (
                    filename.startswith("transcript-")
                    and "diarized" not in filename
                    and "preprocessed" not in filename
                    and "aligned" not in filename
                ):
                    asr_model = filename[len("transcript-") :]
                    processing_level = 0
                else:
                    continue  # Skip other variants

                if not asr_model:
                    continue

                # Update best transcript for this model if this is more processed
                if asr_model not in best_transcripts or processing_level > best_transcripts[asr_model]["processing_level"]:
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

                    best_transcripts[asr_model] = {
                        "transcript_file": transcript_file,
                        "transcript_data": transcript_data,
                        "asr_model": asr_model,
                        "processing_level": processing_level,
                        "processing_stage": ["base", "diarized", "preprocessed"][
                            processing_level
                        ],
                        "episode_meta": episode_meta,
                        "directory": episode_dir,
                    }

            except Exception as e:
                logger.debug(f"Failed to parse {transcript_file}: {e}")
                continue

        # Sort by ASR model name
        transcripts = sorted(best_transcripts.values(), key=lambda t: t["asr_model"])
        return transcripts

    def get_transcript_title(self, transcript: Dict[str, Any]) -> str:
        """Get display title for transcript confirmation.

        Args:
            transcript: Transcript dictionary

        Returns:
            Title string combining model and processing stage
        """
        asr_model = transcript["asr_model"]
        stage = transcript["processing_stage"]
        return f"{asr_model} ({stage})"

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
        title = f"📝 Select Transcript to Preprocess (Page {browser.current_page + 1}/{browser.total_pages})"

        # Compute dynamic Title width
        term_width = self.console.size.width
        fixed_widths = {"num": 4, "model": 30, "stage": 20}
        borders_allowance = 16
        title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)

        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            border_style=TABLE_BORDER_STYLE,
            title=title,
            expand=False,
        )
        table.add_column(
            "#", style=TABLE_NUM_STYLE, width=fixed_widths["num"], justify="right", no_wrap=True
        )
        table.add_column(
            "ASR Model", style="cyan", width=fixed_widths["model"], no_wrap=True, overflow="ellipsis"
        )
        table.add_column(
            "Current Stage", style="magenta", width=fixed_widths["stage"], no_wrap=True
        )
        table.add_column(
            "Episode Title", style=TABLE_TITLE_COL_STYLE, width=title_width, no_wrap=True, overflow="ellipsis"
        )

        for idx, item in enumerate(page_items, start=start_idx + 1):
            asr_model = item["asr_model"]
            stage_emoji = {"base": "○", "diarized": "◐", "preprocessed": "✓"}
            stage = item["processing_stage"]
            stage_display = f"{stage_emoji.get(stage, '○')} {stage.title()}"
            episode_title = item["episode_meta"].get("episode_title", "Unknown")

            table.add_row(str(idx), asr_model, stage_display, episode_title)

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
        # Phase 1: Select episode using Textual TUI
        try:
            episode, episode_meta = select_episode_with_tui(
                self.scan_dir, show_filter=self.show_filter
            )
        except SystemExit:
            return None

        if not episode:
            return None

        # Phase 2: Select transcript using Textual TUI
        transcripts = self.scan_transcripts(episode["directory"])

        if not transcripts:
            print(f"❌ No transcripts found in episode: {episode.get('title', 'Unknown')}")
            return None

        # Use ModelLevelProcessingBrowser for transcript selection
        # For preprocess, we want to show processing_stage instead of completion status
        app = ModelLevelProcessingBrowser(
            items=transcripts,
            model_key="asr_model",
            status_key="processing_level",  # Not used for checkmarks in preprocess
        )
        app.TITLE = "Select Transcript to Preprocess"
        selected_transcript = app.run()

        return selected_transcript
