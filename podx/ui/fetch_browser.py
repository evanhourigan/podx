"""Interactive episode browser for podcast RSS feeds.

Migrated to Textual TUI using SelectionBrowserApp widget (Phase 3.2.3).
"""

from typing import Any, Dict, List, Optional

import feedparser
from rich.text import Text

from ..utils import format_date, format_duration, generate_workdir
from .widgets import show_selection_browser


def load_episodes_from_rss(
    show_name: str, rss_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Load episodes from RSS feed.

    Args:
        show_name: Name of the podcast show
        rss_url: Direct RSS feed URL (optional, will search if not provided)

    Returns:
        List of episode dictionaries, or empty list on error
    """
    try:
        # Find RSS feed if not provided
        if not rss_url:
            from ..fetch import find_feed_for_show

            print(f"🔍 Finding RSS feed for: {show_name}")
            feed_url = find_feed_for_show(show_name)
            if not feed_url:
                print(f"❌ Could not find RSS feed for: {show_name}")
                return []
            rss_url = feed_url

        # Parse RSS feed
        print(f"📡 Loading episodes from: {rss_url}")
        feed = feedparser.parse(rss_url)

        if not feed.entries:
            print("❌ No episodes found in RSS feed")
            return []

        # Extract episode information
        episodes = []
        for entry in feed.entries:
            # Get audio URL from enclosures
            audio_url = None
            duration = None

            # Extract duration from iTunes tags first (more reliable)
            if hasattr(entry, "itunes_duration"):
                try:
                    duration_str = entry.itunes_duration
                    # Check if it's already in seconds (pure number)
                    try:
                        duration = int(duration_str)
                    except ValueError:
                        # Parse HH:MM:SS or MM:SS format
                        parts = duration_str.split(":")
                        if len(parts) == 3:  # HH:MM:SS
                            duration = (
                                int(parts[0]) * 3600
                                + int(parts[1]) * 60
                                + int(parts[2])
                            )
                        elif len(parts) == 2:  # MM:SS
                            duration = int(parts[0]) * 60 + int(parts[1])
                except (ValueError, AttributeError):
                    pass

            if hasattr(entry, "enclosures") and entry.enclosures:
                for enclosure in entry.enclosures:
                    if enclosure.type and "audio" in enclosure.type:
                        audio_url = enclosure.href
                        break

            episode = {
                "title": entry.title,
                "published": (
                    entry.published if hasattr(entry, "published") else "Unknown"
                ),
                "description": entry.summary if hasattr(entry, "summary") else "",
                "audio_url": audio_url,
                "duration": duration,
                "link": entry.link if hasattr(entry, "link") else "",
                "show_name": show_name,  # Add show_name for status checking
            }

            episodes.append(episode)

        print(f"✅ Loaded {len(episodes)} episodes")
        return episodes

    except Exception as e:
        print(f"❌ Error loading episodes: {e}")
        return []


def _format_fetch_cell(column_key: str, value: Any, item: Dict[str, Any]) -> Text:
    """Format cell content for fetch browser."""
    if column_key == "date":
        date = format_date(item.get("published", "Unknown"))
        # Check if episode is already fetched
        show_name = item.get("show_name", "Unknown")
        episode_dir = generate_workdir(show_name, item.get("published", ""))
        episode_meta_file = episode_dir / "episode-meta.json"
        is_fetched = episode_meta_file.exists()

        # Add status indicator
        status_indicator = "✓ " if is_fetched else "  "
        return Text(status_indicator + date, style="green")

    if column_key == "duration":
        duration = format_duration(item.get("duration"))
        return Text(duration, style="yellow")

    if column_key == "title":
        title = item.get("title", "Unknown")
        return Text(title, style="white")

    return Text(str(value) if value is not None else "", style="white")


def show_fetch_browser(
    show_name: str, rss_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Show interactive browser for selecting episodes to fetch.

    Args:
        show_name: Name of the podcast show
        rss_url: Direct RSS feed URL (optional)

    Returns:
        Selected episode dict, or None if cancelled
    """
    # Load episodes from RSS
    episodes = load_episodes_from_rss(show_name, rss_url)
    if not episodes:
        return None

    columns = [
        ("Date", "date", 14),
        ("Duration", "duration", 10),
        ("Title", "title", 70),
    ]

    return show_selection_browser(
        items=episodes,
        columns=columns,
        title=f"🎙️ {show_name} - Select Episode to Download",
        item_name="episode",
        format_cell=_format_fetch_cell,
    )


# Backward compatibility: keep EpisodeBrowser class as deprecated wrapper
class EpisodeBrowser:
    """DEPRECATED: Use show_fetch_browser() function instead.

    This class is kept for backward compatibility but now uses Textual TUI internally.
    """

    def __init__(
        self, show_name: str, rss_url: Optional[str] = None, episodes_per_page: int = 8
    ):
        """Initialize browser with show name and RSS URL.

        Args:
            show_name: Name of the podcast show
            rss_url: Direct RSS feed URL (optional)
            episodes_per_page: Ignored (Textual handles pagination automatically)
        """
        self.show_name = show_name
        self.rss_url = rss_url
        self.episodes_per_page = episodes_per_page
        self.items_per_page = episodes_per_page
        self.episodes = []  # Will be populated by load_episodes()
        self.items = self.episodes  # Alias for compatibility

    def load_episodes(self) -> bool:
        """Load episodes from RSS feed.

        Returns:
            True if episodes loaded successfully, False otherwise
        """
        self.episodes = load_episodes_from_rss(self.show_name, self.rss_url)
        self.items = self.episodes
        return len(self.episodes) > 0

    def browse(self) -> Optional[Dict[str, Any]]:
        """Show browser and return selected episode.

        Returns:
            Selected episode dict, or None if cancelled
        """
        return show_fetch_browser(self.show_name, self.rss_url)
