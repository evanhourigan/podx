"""Interactive browser for selecting aligned transcripts to diarize."""

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
    TABLE_SHOW_STYLE,
    TABLE_DATE_STYLE,
    TABLE_TITLE_COL_STYLE,
    make_console,
)

logger = get_logger(__name__)


def scan_diarizable_transcripts(scan_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan directory for aligned transcript files (both new and legacy formats).
    Returns list of aligned transcripts with their metadata and diarization status.
    """
    transcripts = []
    seen_transcripts = set()  # Track unique transcripts to avoid duplicates

    # Find all aligned transcript files (new format: transcript-aligned-*.json, legacy: aligned-transcript-*.json)
    for pattern in ["transcript-aligned-*.json", "aligned-transcript-*.json"]:
        for aligned_file in scan_dir.rglob(pattern):
            try:
                # Load aligned transcript data
                aligned_data = json.loads(aligned_file.read_text(encoding="utf-8"))

                # Extract ASR model from filename
                filename = aligned_file.stem
                if filename.startswith("transcript-aligned-"):
                    asr_model = filename[len("transcript-aligned-") :]
                elif filename.startswith("aligned-transcript-"):
                    asr_model = filename[len("aligned-transcript-") :]
                else:
                    continue

                # Create unique key to avoid duplicates (episode dir + asr model)
                unique_key = (str(aligned_file.parent), asr_model)
                if unique_key in seen_transcripts:
                    continue
                seen_transcripts.add(unique_key)

                # Get audio path
                audio_path = aligned_data.get("audio_path")
                if not audio_path:
                    continue

                audio_path = Path(audio_path)
                if not audio_path.exists():
                    continue

                # Check if diarized version exists (new format first, then legacy)
                diarized_file_new = (
                    aligned_file.parent / f"transcript-diarized-{asr_model}.json"
                )
                diarized_file_legacy = (
                    aligned_file.parent / f"diarized-transcript-{asr_model}.json"
                )
                is_diarized = diarized_file_new.exists() or diarized_file_legacy.exists()
                # Use new format for output
                diarized_file = diarized_file_new

                # Try to get episode metadata for better display
                episode_meta_file = aligned_file.parent / "episode-meta.json"
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
                        "aligned_file": aligned_file,
                        "aligned_data": aligned_data,
                        "audio_path": audio_path,
                        "asr_model": asr_model,
                        "is_diarized": is_diarized,
                        "diarized_file": diarized_file,
                        "episode_meta": episode_meta,
                        "directory": aligned_file.parent,
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to parse {aligned_file}: {e}")
                continue

    # Sort by date (most recent first) then by show name
    def sort_key(t):
        date_str = t["episode_meta"].get("episode_published", "")
        return (date_str, t["episode_meta"].get("show", ""))

    transcripts.sort(key=sort_key, reverse=True)
    return transcripts


class DiarizeBrowser:
    """Interactive browser for selecting aligned transcripts to diarize."""

    def __init__(self, transcripts: List[Dict[str, Any]], items_per_page: int = 10):
        self.transcripts = transcripts
        self.items_per_page = items_per_page
        self.console = make_console() if RICH_AVAILABLE else None
        self.current_page = 0
        self.total_pages = max(
            1, (len(transcripts) + items_per_page - 1) // items_per_page
        )

    def display_page(self) -> None:
        """Display current page with table and navigation options."""
        if not self.console:
            return

        # Calculate page bounds
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.transcripts))
        page_items = self.transcripts[start_idx:end_idx]

        # Create title (shortened per spec)
        title = f"🎙️ Episodes Available for Diarization (Page {self.current_page + 1}/{self.total_pages})"

        # Compute dynamic Title width
        term_width = self.console.size.width
        fixed_widths = {"num": 4, "status": 24, "show": 20, "date": 12}
        borders_allowance = 16
        title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)

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

        for idx, item in enumerate(page_items, start=start_idx + 1):
            episode_meta = item["episode_meta"]
            asr_model = item["asr_model"]
            status = f"✓ {asr_model}" if item["is_diarized"] else f"○ {asr_model}"

            show = episode_meta.get("show", "Unknown")

            # Format date to YYYY-MM-DD
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
                parts = str(item["directory"]).split("/")
                date = parts[-1] if parts else "Unknown"

            title_text = episode_meta.get("episode_title", "Unknown")

            table.add_row(str(idx), status, show, date, title_text)

        self.console.print(table)

        # Show navigation options in Panel
        options = []
        options.append(
            f"[cyan]1-{len(self.transcripts)}[/cyan]: Select episode to diarize"
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
        """Get user input and return selected item or None for quit."""
        if not self.console:
            return None

        user_input = input("\n👉 Your choice: ").strip().upper()

        # Quit
        if user_input in ["Q", "QUIT", "EXIT"]:
            self.console.print("👋 Goodbye!")
            return None

        # Next page
        if user_input == "N" and self.current_page < self.total_pages - 1:
            self.current_page += 1
            return {}  # Signal page change

        # Previous page
        if user_input == "P" and self.current_page > 0:
            self.current_page -= 1
            return {}  # Signal page change

        # Episode selection
        try:
            episode_num = int(user_input)
            if 1 <= episode_num <= len(self.transcripts):
                selected = self.transcripts[episode_num - 1]
                # Show confirmation
                title = selected["episode_meta"].get("episode_title", "Unknown")
                self.console.print(f"✅ Selected: [green]{title}[/green]")
                return selected
            else:
                self.console.print(
                    f"[red]❌ Invalid choice. Please select 1-{len(self.transcripts)}[/red]"
                )
                return {}  # Stay on same page
        except ValueError:
            self.console.print("[red]❌ Invalid input. Please enter a number.[/red]")
            return {}  # Stay on same page

    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop. Returns selected transcript or None."""
        if not self.console:
            return None

        while True:
            self.console.clear()
            self.display_page()
            result = self.get_user_input()

            # {} signals page change, keep looping
            if result == {}:
                continue
            # None signals quit or actual selection
            return result
