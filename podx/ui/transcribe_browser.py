"""Interactive episode browser for transcription.

Migrated to Textual TUI using SelectionBrowserApp widget (Phase 3.2.3).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.text import Text

from ..logging import get_logger
from .widgets import show_selection_browser

logger = get_logger(__name__)


def scan_transcribable_episodes(base_dir: Path = Path.cwd()) -> List[Dict[str, Any]]:
    """Scan for audio-meta.json files (transcoded episodes ready for transcription)."""
    episodes = []

    # Recursively search for audio-meta.json files
    for meta_file in base_dir.rglob("audio-meta.json"):
        # Skip root-level audio-meta.json (should be in subdirectories)
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


def _format_transcribe_cell(column_key: str, value: Any, item: Dict[str, Any]) -> Text:
    """Format cell content for transcribe browser."""
    # Load episode metadata if needed
    episode_meta = {}
    episode_meta_file = item["directory"] / "episode-meta.json"
    if episode_meta_file.exists():
        try:
            episode_meta = json.loads(episode_meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    if column_key == "status":
        if item.get("transcripts"):
            models_list = ", ".join(item["transcripts"].keys())
            return Text(f"✓ {models_list}", style="green")
        return Text("○ New", style="yellow")

    if column_key == "show":
        show = episode_meta.get("show", "Unknown")
        return Text(show[:20], style="cyan")

    if column_key == "date":
        date_str = episode_meta.get("episode_published", "")
        if date_str:
            try:
                from dateutil import parser as dtparse

                parsed = dtparse.parse(date_str)
                return Text(parsed.strftime("%Y-%m-%d"), style="blue")
            except Exception:
                date = date_str[:10] if len(date_str) >= 10 else date_str
                return Text(date, style="blue")
        # Try to extract from directory name
        parts = str(item["directory"]).split("/")
        date = parts[-1] if parts else "Unknown"
        return Text(date, style="blue")

    if column_key == "title":
        title = episode_meta.get("episode_title", "Unknown")
        return Text(title, style="white")

    return Text(str(value) if value is not None else "", style="white")


def show_transcribe_browser(episodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Show interactive browser for selecting episodes to transcribe.

    Args:
        episodes: List of episode dictionaries (from scan_transcribable_episodes)

    Returns:
        Selected episode dict, or None if cancelled
    """
    columns = [
        ("Status", "status", 24),
        ("Show", "show", 20),
        ("Date", "date", 12),
        ("Title", "title", 50),
    ]

    return show_selection_browser(
        items=episodes,
        columns=columns,
        title="🎙️ Select Episode for Transcription",
        item_name="episode",
        format_cell=_format_transcribe_cell,
    )


# Backward compatibility: keep TranscribeBrowser class as deprecated wrapper
class TranscribeBrowser:
    """DEPRECATED: Use show_transcribe_browser() function instead.

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
        return show_transcribe_browser(self.episodes)
