"""Interactive browser for selecting episodes to transcode."""

import json
from pathlib import Path
from typing import Any, Dict, List

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
)
from .interactive_browser import InteractiveBrowser

logger = get_logger(__name__)


def scan_transcodable_episodes(base_dir: Path = Path.cwd()) -> List[Dict[str, Any]]:
    """Scan for episode-meta.json files in subdirectories."""
    episodes = []

    # Recursively search for episode-meta.json files
    for meta_file in base_dir.rglob("episode-meta.json"):
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

            # Check for existing transcoded version
            audio_meta_path = meta_file.parent / "audio-meta.json"
            is_transcoded = audio_meta_path.exists()

            episodes.append(
                {
                    "meta_file": meta_file,
                    "meta_data": meta_data,
                    "audio_path": audio_path,
                    "is_transcoded": is_transcoded,
                    "directory": meta_file.parent,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to parse {meta_file}: {e}")
            continue

    # Sort by directory path for consistent ordering
    episodes.sort(key=lambda x: str(x["directory"]))

    return episodes


class TranscodeBrowser(InteractiveBrowser):
    """Interactive browser for selecting episodes to transcode."""

    def __init__(self, episodes: List[Dict[str, Any]], episodes_per_page: int = 10):
        super().__init__(episodes, episodes_per_page, item_name="episode")
        # Keep episodes as alias for backward compatibility
        self.episodes = self.items
        self.episodes_per_page = self.items_per_page

    def _get_item_title(self, item: Dict[str, Any]) -> str:
        """Get title of episode for selection confirmation."""
        meta = item.get("meta_data", {})
        return meta.get("episode_title", "Unknown")

    def display_page(self) -> None:
        """Display current page with table and navigation options."""
        if not self.console:
            return

        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.items))
        page_episodes = self.items[start_idx:end_idx]

        # Create title
        title = f"🎙️ Episodes Available for Transcoding (Page {self.current_page + 1}/{self.total_pages})"

        # Compute dynamic Title width - standardize status width to 24
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

        # Add episodes to table
        for i, episode in enumerate(page_episodes):
            episode_num = start_idx + i + 1
            meta = episode["meta_data"]

            # Status indicator
            status = "✓ Done" if episode["is_transcoded"] else "○ New"

            # Extract info from metadata
            show = meta.get("show", "Unknown")

            # Extract date from published or path
            date_str = meta.get("episode_published", "")
            if date_str:
                # Try to parse date
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

            title_text = meta.get("episode_title", "Unknown")

            table.add_row(str(episode_num), status, show, date, title_text)

        self.console.print(table)

        # Show navigation options
        options = []
        options.append(
            f"[cyan]1-{len(self.items)}[/cyan]: Select episode to transcode"
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
