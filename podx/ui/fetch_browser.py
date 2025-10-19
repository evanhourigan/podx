"""Interactive episode browser for podcast RSS feeds."""

from typing import Any, Dict, List, Optional

import feedparser

from ..utils import format_date, format_duration, generate_workdir

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


class EpisodeBrowser:
    """Interactive episode browser with pagination."""

    def __init__(
        self, show_name: str, rss_url: Optional[str] = None, episodes_per_page: int = 8
    ):
        self.show_name = show_name
        self.rss_url = rss_url
        self.episodes_per_page = episodes_per_page
        self.console = make_console() if RICH_AVAILABLE else None
        self.episodes: List[Dict[str, Any]] = []
        self.current_page = 0
        self.total_pages = 0

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
            self.episodes = []
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

                self.episodes.append(episode)

            # Calculate pagination
            self.total_pages = (
                len(self.episodes) + self.episodes_per_page - 1
            ) // self.episodes_per_page

            if self.console:
                self.console.print(
                    f"✅ Loaded [green]{len(self.episodes)}[/green] episodes"
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

        start_idx = self.current_page * self.episodes_per_page
        end_idx = min(start_idx + self.episodes_per_page, len(self.episodes))
        page_episodes = self.episodes[start_idx:end_idx]

        # Create title
        title = f"🎙️ {self.show_name} - Episodes (Page {self.current_page + 1}/{self.total_pages})"

        # Compute Title width and render with shared styling
        term_width = self.console.size.width
        fixed_widths = {"num": 4, "date": 12, "dur": 8}
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
        table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed_widths["date"], no_wrap=True)
        table.add_column("Duration", style="yellow", width=fixed_widths["dur"], justify="right", no_wrap=True)
        table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_width, no_wrap=True, overflow="ellipsis")

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
        options.append(
            f"[cyan]1-{len(self.episodes)}[/cyan]: Select episode to download"
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
                        if self.console:
                            self.console.print(
                                f"✅ Selected: [green]{selected_episode['title']}[/green]"
                            )
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
        if not self.load_episodes():
            return None

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
