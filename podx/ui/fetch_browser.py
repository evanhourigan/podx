"""Interactive episode browser for podcast RSS feeds."""

from typing import Any, Dict, Optional

import feedparser

from ..utils import format_date, format_duration, generate_workdir
from .interactive_browser import InteractiveBrowser

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
        TABLE_BORDER_STYLE,
        TABLE_HEADER_STYLE,
        TABLE_NUM_STYLE,
        TABLE_DATE_STYLE,
        TABLE_TITLE_COL_STYLE,
    )
except Exception:

    def make_console():
        return Console()

    TABLE_BORDER_STYLE = "grey50"
    TABLE_HEADER_STYLE = "bold magenta"
    TABLE_NUM_STYLE = "cyan"
    TABLE_DATE_STYLE = "green"
    TABLE_TITLE_COL_STYLE = "white"


class EpisodeBrowser(InteractiveBrowser):
    """Interactive episode browser with pagination."""

    def __init__(
        self, show_name: str, rss_url: Optional[str] = None, episodes_per_page: int = 8
    ):
        self.show_name = show_name
        self.rss_url = rss_url
        # Initialize with empty list, load_episodes() will populate it
        super().__init__([], episodes_per_page, item_name="episode")
        # Keep episodes as alias for backward compatibility
        self.episodes = self.items
        self.episodes_per_page = self.items_per_page

    def _get_item_title(self, item: Dict[str, Any]) -> str:
        """Get title of episode for selection confirmation."""
        return item.get("title", "Unknown")

    def load_episodes(self) -> bool:
        """Load episodes from RSS feed."""
        try:
            # Find RSS feed if not provided
            if not self.rss_url:
                # Import here to avoid circular dependency
                from ..fetch import find_feed_for_show

                if self.console:
                    self.console.print(
                        f"🔍 Finding RSS feed for: [cyan]{self.show_name}[/cyan]"
                    )
                feed_url = find_feed_for_show(self.show_name)
                if not feed_url:
                    if self.console:
                        self.console.print(
                            f"❌ Could not find RSS feed for: {self.show_name}"
                        )
                    return False
                self.rss_url = feed_url

            # Parse RSS feed
            if self.console:
                self.console.print(
                    f"📡 Loading episodes from: [yellow]{self.rss_url}[/yellow]"
                )
            feed = feedparser.parse(self.rss_url)

            if not feed.entries:
                if self.console:
                    self.console.print("❌ No episodes found in RSS feed")
                return False

            # Extract episode information
            self.items.clear()  # Clear instead of creating new list to maintain alias
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
                }

                self.items.append(episode)

            # Calculate pagination - update base class total_pages
            self.total_pages = max(
                1, (len(self.items) + self.items_per_page - 1) // self.items_per_page
            )

            if self.console:
                self.console.print(
                    f"✅ Loaded [green]{len(self.items)}[/green] episodes"
                )
            return True

        except Exception as e:
            if self.console:
                self.console.print(f"❌ Error loading episodes: {e}")
            return False

    def display_page(self) -> None:
        """Display current page of episodes."""
        if not self.console:
            return

        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.items))
        page_episodes = self.items[start_idx:end_idx]

        # Create title
        title = f"🎙️ {self.show_name} - Episodes (Page {self.current_page + 1}/{self.total_pages})"

        # Compute Title width and render with shared styling
        term_width = self.console.size.width
        fixed_widths = {"num": 4, "date": 12, "dur": 8}
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
            "Date", style=TABLE_DATE_STYLE, width=fixed_widths["date"], no_wrap=True
        )
        table.add_column(
            "Duration",
            style="yellow",
            width=fixed_widths["dur"],
            justify="right",
            no_wrap=True,
        )
        table.add_column(
            "Title",
            style=TABLE_TITLE_COL_STYLE,
            width=title_width,
            no_wrap=True,
            overflow="ellipsis",
        )

        # Add episodes to table
        for i, episode in enumerate(page_episodes):
            episode_num = start_idx + i + 1
            date = format_date(episode["published"])
            duration = format_duration(episode["duration"])
            title_text = episode["title"]

            # Check if episode is already fetched
            episode_dir = generate_workdir(self.show_name, episode["published"])
            episode_meta_file = episode_dir / "episode-meta.json"
            is_fetched = episode_meta_file.exists()

            # Add status indicator: ✓ for fetched, blank for not fetched
            status_indicator = "✓" if is_fetched else " "
            date_display = f"{status_indicator} {date}"

            table.add_row(str(episode_num), date_display, duration, title_text)

        self.console.print(table)

        # Show navigation options
        options = []
        options.append(f"[cyan]1-{len(self.items)}[/cyan]: Select episode to download")

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

    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop. Load episodes first, then start browsing."""
        if not self.load_episodes():
            return None

        # Call parent browse() after episodes are loaded
        return super().browse()
