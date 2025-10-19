"""Interactive episode browser for transcription."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logging import get_logger

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Shared UI styling
try:
    from . import (
        make_console,
        TABLE_BORDER_STYLE,
        TABLE_HEADER_STYLE,
        TABLE_NUM_STYLE,
        TABLE_SHOW_STYLE,
        TABLE_DATE_STYLE,
        TABLE_TITLE_COL_STYLE,
    )
except Exception:

    def make_console():
        return Console()

    TABLE_BORDER_STYLE = "grey50"
    TABLE_HEADER_STYLE = "bold magenta"
    TABLE_NUM_STYLE = "cyan"
    TABLE_SHOW_STYLE = "yellow3"
    TABLE_DATE_STYLE = "bright_blue"
    TABLE_TITLE_COL_STYLE = "white"


def scan_transcribable_episodes(base_dir: Path = Path.cwd()) -> List[Dict[str, Any]]:
    """Scan for audio-meta.json files (transcoded episodes ready for transcription)."""
    episodes = []

    # Recursively search for audio-meta.json files
    for meta_file in base_dir.rglob("audio-meta.json"):
        try:
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))

            # Check if audio file exists
            if "audio_path" not in meta_data:
                continue

            audio_path = Path(meta_data["audio_path"])
            if not audio_path.exists():
                # Try relative to meta file directory
                audio_path = meta_file.parent / audio_path.name
                if not audio_path.exists():
                    continue

            # Check for existing transcripts by reading JSON (provider-aware)
            transcripts = {}

            # Discover any transcript-*.json and read asr_model from content
            for transcript_path in meta_file.parent.glob("transcript-*.json"):
                try:
                    data = json.loads(transcript_path.read_text(encoding="utf-8"))
                    asr_model = data.get("asr_model") or data.get("model") or "unknown"
                    transcripts[asr_model] = transcript_path
                except Exception:
                    continue

            # Check for legacy transcript.json (unknown model)
            legacy_transcript = meta_file.parent / "transcript.json"
            if legacy_transcript.exists():
                # Try to determine model from content
                try:
                    transcript_data = json.loads(
                        legacy_transcript.read_text(encoding="utf-8")
                    )
                    model = transcript_data.get("asr_model", "unknown")
                    transcripts[model] = legacy_transcript
                except Exception:
                    transcripts["unknown"] = legacy_transcript

            episodes.append(
                {
                    "meta_file": meta_file,
                    "meta_data": meta_data,
                    "audio_path": audio_path,
                    "transcripts": transcripts,
                    "directory": meta_file.parent,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to parse {meta_file}: {e}")
            continue

    # Sort by directory path for consistent ordering
    episodes.sort(key=lambda x: str(x["directory"]))

    return episodes


class TranscribeBrowser:
    """Interactive episode browser for transcription."""

    def __init__(self, episodes: List[Dict[str, Any]], episodes_per_page: int = 10):
        self.episodes = episodes
        self.episodes_per_page = episodes_per_page
        self.console = make_console() if RICH_AVAILABLE else None
        self.current_page = 0
        self.total_pages = (
            (len(episodes) + episodes_per_page - 1) // episodes_per_page
            if episodes
            else 1
        )

    def display_page(self) -> None:
        """Display current page of episodes."""
        if not self.console:
            return

        start_idx = self.current_page * self.episodes_per_page
        end_idx = min(start_idx + self.episodes_per_page, len(self.episodes))
        page_episodes = self.episodes[start_idx:end_idx]

        # Create title
        title = f"🎙️ Episodes Available for Transcription (Page {self.current_page + 1}/{self.total_pages})"

        # Compute dynamic Title width so table fits terminal
        term_width = self.console.size.width
        fixed_widths = {"num": 4, "status": 24, "show": 20, "date": 12}
        borders_allowance = 16
        title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)

        # Create table with shared styling
        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            border_style=TABLE_BORDER_STYLE,
            title=title,
            expand=False,
        )
        table.add_column("#", style=TABLE_NUM_STYLE, width=fixed_widths["num"], justify="right", no_wrap=True)
        table.add_column("Status", style="magenta", width=fixed_widths["status"], no_wrap=True, overflow="ellipsis")
        table.add_column("Show", style=TABLE_SHOW_STYLE, width=fixed_widths["show"], no_wrap=True, overflow="ellipsis")
        table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed_widths["date"], no_wrap=True)
        table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_width, no_wrap=True, overflow="ellipsis")

        # Add episodes to table
        for i, episode in enumerate(page_episodes):
            episode_num = start_idx + i + 1

            # Load episode metadata from episode-meta.json if it exists
            episode_meta_file = episode["directory"] / "episode-meta.json"
            if episode_meta_file.exists():
                try:
                    episode_meta = json.loads(
                        episode_meta_file.read_text(encoding="utf-8")
                    )
                except Exception:
                    episode_meta = {}
            else:
                episode_meta = {}

            # Status indicator
            if episode["transcripts"]:
                models_list = ", ".join(episode["transcripts"].keys())
                status = f"✓ {models_list}"
            else:
                status = "○ New"

            # Extract info from metadata
            show = episode_meta.get("show", "Unknown")

            # Extract date
            date_str = episode_meta.get("episode_published", "")
            if date_str:
                try:
                    from dateutil import parser as dtparse

                    parsed = dtparse.parse(date_str)
                    date = parsed.strftime("%Y-%m-%d")
                except Exception:
                    date = date_str[:10] if len(date_str) >= 10 else date_str
            else:
                # Try to extract from directory name
                parts = str(episode["directory"]).split("/")
                date = parts[-1] if parts else "Unknown"

            title = episode_meta.get("episode_title", "Unknown")

            table.add_row(str(episode_num), status, show, date, title)

        self.console.print(table)

        # Show navigation options
        options = []
        options.append(
            f"[cyan]1-{len(self.episodes)}[/cyan]: Select episode to transcribe"
        )

        if self.current_page < self.total_pages - 1:
            options.append("[yellow]N[/yellow]: Next page")

        if self.current_page > 0:
            options.append("[yellow]P[/yellow]: Previous page")

        options.append("[red]Q[/red]: Quit")

        options_text = " • ".join(options)

        panel = Panel(
            options_text, title="Options", border_style="blue", padding=(0, 1)
        )

        self.console.print(panel)

    def get_user_input(self) -> Optional[Dict[str, Any]]:
        """Get user input and return selected episode or None."""
        while True:
            try:
                user_input = input("\n👉 Your choice: ").strip().upper()

                if not user_input:
                    continue

                # Quit
                if user_input in ["Q", "QUIT", "EXIT"]:
                    if self.console:
                        self.console.print("👋 Goodbye!")
                    return None

                # Next page
                if user_input == "N" and self.current_page < self.total_pages - 1:
                    self.current_page += 1
                    return {}  # Empty dict signals page change

                # Previous page
                if user_input == "P" and self.current_page > 0:
                    self.current_page -= 1
                    return {}  # Empty dict signals page change

                # Episode selection
                try:
                    episode_num = int(user_input)
                    if 1 <= episode_num <= len(self.episodes):
                        selected_episode = self.episodes[episode_num - 1]
                        # Show confirmation
                        if self.console:
                            # Load metadata to get title
                            episode_meta_file = selected_episode["directory"] / "episode-meta.json"
                            if episode_meta_file.exists():
                                try:
                                    import json
                                    episode_meta = json.loads(episode_meta_file.read_text(encoding="utf-8"))
                                    title = episode_meta.get("episode_title", "Unknown")
                                except Exception:
                                    title = "Unknown"
                            else:
                                title = "Unknown"
                            self.console.print(f"✅ Selected: [green]{title}[/green]")
                        return selected_episode
                    else:
                        if self.console:
                            self.console.print(
                                f"[red]❌ Invalid choice. Please select 1-{len(self.episodes)}[/red]"
                            )
                except ValueError:
                    pass

                # Invalid input
                if self.console:
                    self.console.print("[red]❌ Invalid input. Please enter a number.[/red]")

            except (KeyboardInterrupt, EOFError):
                if self.console:
                    self.console.print("\n👋 Goodbye!")
                return None

    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop."""
        while True:
            if self.console:
                self.console.clear()
            self.display_page()

            result = self.get_user_input()

            # None means quit
            if result is None:
                return None

            # Empty dict means page change, continue loop
            if not result:
                continue

            # Non-empty dict means episode selected
            return result
