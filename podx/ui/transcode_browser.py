"""Interactive browser for selecting episodes to transcode.

Migrated to Textual TUI using SelectionBrowserApp widget (Phase 3.2.2).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.text import Text

from ..logging import get_logger
from .widgets import show_selection_browser

logger = get_logger(__name__)


def scan_transcodable_episodes(base_dir: Path = Path.cwd()) -> List[Dict[str, Any]]:
    """Scan for episode-meta.json files in subdirectories."""
    episodes = []

    # Recursively search for episode-meta.json files
    for meta_file in base_dir.rglob("episode-meta.json"):
        # Skip root-level episode-meta.json (should be in subdirectories)
        if meta_file.parent == base_dir:
            continue

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


def _format_transcode_cell(column_key: str, value: Any, item: Dict[str, Any]) -> Text:
    """Format cell content for transcode browser."""
    meta = item.get("meta_data", {})

    if column_key == "status":
        if item.get("is_transcoded"):
            return Text("✓ Done", style="green")
        return Text("○ New", style="yellow")

    if column_key == "show":
        show = meta.get("show", "Unknown")
        return Text(show[:20], style="cyan")

    if column_key == "date":
        # Extract date from published or path
        date_str = meta.get("episode_published", "")
        if date_str:
            # Try to parse date
            try:
                from dateutil import parser as dtparse

                parsed = dtparse.parse(date_str)
                return Text(parsed.strftime("%Y-%m-%d"), style="green")
            except Exception:
                date = date_str[:10] if len(date_str) >= 10 else date_str
                return Text(date, style="green")
        # Try to extract from directory name
        parts = str(item["directory"]).split("/")
        date = parts[-1] if parts else "Unknown"
        return Text(date, style="green")

    if column_key == "title":
        title_text = meta.get("episode_title", "Unknown")
        return Text(title_text, style="white")

    return Text(str(value) if value is not None else "", style="white")


def show_transcode_browser(episodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Show interactive browser for selecting episodes to transcode.

    Args:
        episodes: List of episode dictionaries (from scan_transcodable_episodes)

    Returns:
        Selected episode dict, or None if cancelled
    """
    columns = [
        ("Status", "status", 12),
        ("Show", "show", 20),
        ("Date", "date", 12),
        ("Title", "title", 60),
    ]

    return show_selection_browser(
        items=episodes,
        columns=columns,
        title="🎙️ Select Episode for Transcoding",
        item_name="episode",
        format_cell=_format_transcode_cell,
    )


# Backward compatibility: keep TranscodeBrowser class as deprecated wrapper
class TranscodeBrowser:
    """DEPRECATED: Use show_transcode_browser() function instead.

    This class is kept for backward compatibility but now uses Textual TUI internally.
    """

    def __init__(self, episodes: List[Dict[str, Any]], episodes_per_page: int = 10):
        """Initialize browser with episodes.

        Args:
            episodes: List of episode dictionaries
            episodes_per_page: Ignored (Textual handles pagination automatically)
        """
        self.episodes = episodes
        self.items = episodes  # Alias for compatibility
        self.episodes_per_page = episodes_per_page
        self.items_per_page = episodes_per_page

    def browse(self) -> Optional[Dict[str, Any]]:
        """Show browser and return selected episode.

        Returns:
            Selected episode dict, or None if cancelled
        """
        return show_transcode_browser(self.episodes)
