"""Modal screen for fetching podcast episodes from RSS feeds."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, Label, Static


class FetchModal(ModalScreen[Optional[Tuple[Dict[str, Any], Dict[str, Any]]]]):
    """Modal screen for fetching episodes from RSS feeds."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    FetchModal {
        align: center middle;
    }

    #fetch-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #search-container {
        height: auto;
        margin-bottom: 1;
    }

    #search-label {
        margin-bottom: 1;
        text-style: bold;
        color: $accent;
    }

    #search-input {
        margin-bottom: 1;
    }

    #podcast-table-container {
        height: 60%;
        border: solid $primary;
        margin-bottom: 1;
    }

    #podcast-table-container.hidden {
        display: none;
    }

    #episode-table-container {
        height: 60%;
        border: solid $primary;
        margin-bottom: 1;
    }

    #episode-table-container.hidden {
        display: none;
    }

    #fetch-detail-container {
        height: auto;
        min-height: 10;
        max-height: 30%;
        border: solid $accent;
        padding: 1;
        margin-bottom: 1;
    }

    #fetch-detail-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #status-message {
        color: $warning;
        text-style: italic;
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel", show=True),
        Binding("enter", "fetch_selected", "Fetch Episode", show=True),
    ]

    def __init__(self, scan_dir: Path, *args: Any, **kwargs: Any) -> None:
        """Initialize fetch modal.

        Args:
            scan_dir: Directory to save fetched episodes to
        """
        super().__init__(*args, **kwargs)
        self.scan_dir = scan_dir
        self.rss_episodes: List[Dict[str, Any]] = []
        self.feed_url: Optional[str] = None
        self.show_name: Optional[str] = None
        self.podcast_results: List[Dict[str, Any]] = []
        self.viewing_mode: str = "search"  # "search", "podcasts", "episodes"

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="fetch-container"):
            with Vertical(id="search-container"):
                yield Label("Search for a podcast show:", id="search-label")
                yield Input(
                    placeholder="Enter show name and press Enter...", id="search-input"
                )
                yield Static("", id="status-message")
            # Podcast selection table (hidden initially)
            with Vertical(id="podcast-table-container", classes="hidden"):
                yield DataTable(
                    id="fetch-podcast-table", cursor_type="row", zebra_stripes=True
                )
            # Episode selection table
            with Vertical(id="episode-table-container"):
                yield DataTable(
                    id="fetch-episode-table", cursor_type="row", zebra_stripes=True
                )
            with Vertical(id="fetch-detail-container"):
                yield Static("Episode Details", id="fetch-detail-title")
                yield Static("Select a show to see episodes", id="fetch-detail-content")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the modal on mount."""

        # Focus the search input
        self.query_one("#search-input", Input).focus()

        # Set up the podcast table
        podcast_table = self.query_one("#fetch-podcast-table", DataTable)
        podcast_table.add_column("Podcast", key="podcast", width=50)
        podcast_table.add_column("Author", key="author", width=30)
        podcast_table.add_column("Episodes", key="episodes", width=10)

        # Set up the episode table
        table = self.query_one("#fetch-episode-table", DataTable)
        table.add_column(Text("Date", style="bold green"), width=12)
        table.add_column(Text("Title", style="bold white"), width=60)
        table.add_column(Text("Duration", style="bold cyan"), width=10)

        # If show_name was pre-set, trigger automatic search
        if self.show_name:
            self.search_and_load(self.show_name)

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        """Handle search submission."""
        input_value = event.value.strip()
        if not input_value:
            return

        status = self.query_one("#status-message", Static)

        # Check if input is a URL (RSS or YouTube)
        if input_value.startswith(("http://", "https://", "www.")):
            # Direct URL provided
            self.feed_url = (
                input_value
                if input_value.startswith("http")
                else f"https://{input_value}"
            )
            self.show_name = "Podcast"  # Default name, will be extracted from feed
            status.update("📡 Loading episodes from URL...")
            self.load_episodes_from_url(self.feed_url)
        else:
            # Show name search
            self.show_name = input_value
            status.update(f"🔍 Searching for '{input_value}'...")
            self.search_and_load(input_value)

    def _parse_feed_episodes(self, feed_url: str) -> None:
        """Parse feed and extract episode information.

        Args:
            feed_url: RSS feed URL to parse
        """
        import feedparser

        feed = feedparser.parse(feed_url)

        if not feed.entries:
            self.app.call_from_thread(self._show_error, "No episodes found in RSS feed")
            return

        # Extract show name from feed if not already set
        if not self.show_name or self.show_name == "Podcast":
            if hasattr(feed.feed, "title"):
                self.show_name = feed.feed.title

        # Extract episode information
        episodes = []
        for entry in feed.entries:
            # Get audio URL
            audio_url = None
            if hasattr(entry, "enclosures") and entry.enclosures:
                for enclosure in entry.enclosures:
                    if enclosure.type and "audio" in enclosure.type:
                        audio_url = enclosure.href
                        break

            # Get duration
            duration = None
            if hasattr(entry, "itunes_duration"):
                try:
                    duration_str = entry.itunes_duration
                    try:
                        duration = int(duration_str)
                    except ValueError:
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

            # Parse and format published date to YYYY-MM-DD
            published_str = "Unknown"
            if hasattr(entry, "published"):
                try:
                    from dateutil import parser as dtparse

                    parsed_date = dtparse.parse(entry.published)
                    published_str = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    # Fall back to raw published string if parsing fails
                    published_str = entry.published

            episode = {
                "title": entry.title,
                "published": published_str,
                "description": entry.summary if hasattr(entry, "summary") else "",
                "audio_url": audio_url,
                "duration": duration,
                "link": entry.link if hasattr(entry, "link") else "",
                "feed_url": feed_url,
            }

            episodes.append(episode)

        self.rss_episodes = episodes
        self.app.call_from_thread(self._populate_table)

    @work(exclusive=True, thread=True)
    def load_episodes_from_url(self, feed_url: str) -> None:
        """Load episodes directly from a feed URL.

        Args:
            feed_url: RSS feed URL to load
        """
        try:
            self._parse_feed_episodes(feed_url)
        except Exception as e:
            self.app.call_from_thread(
                self._show_error, f"Error loading episodes: {str(e)}"
            )

    @work(exclusive=True, thread=True)
    def search_and_load(self, show_name: str) -> None:
        """Search for show and load episodes.

        Args:
            show_name: Name of the show to search for
        """
        try:
            # Search for podcasts
            from ..fetch import search_podcasts

            podcasts = search_podcasts(show_name)
            if not podcasts:
                self.app.call_from_thread(
                    self._show_error, f"No podcasts found for '{show_name}'"
                )
                return

            # Store search results
            self.podcast_results = podcasts
            self.show_name = show_name

            # If multiple podcasts, show selection screen
            if len(podcasts) > 1:
                self.app.call_from_thread(self._show_podcast_selection, podcasts)
            else:
                # Only one podcast, load it directly
                feed_url = podcasts[0].get("feedUrl")
                if not feed_url:
                    self.app.call_from_thread(
                        self._show_error, "Podcast has no feed URL"
                    )
                    return

                self.feed_url = feed_url
                self.show_name = podcasts[0].get("collectionName", show_name)
                self._parse_feed_episodes(feed_url)

        except Exception as e:
            self.app.call_from_thread(self._show_error, f"Error searching: {str(e)}")

    def _show_error(self, message: str) -> None:
        """Show an error message.

        Args:
            message: Error message to display
        """
        status = self.query_one("#status-message", Static)
        status.update(f"❌ {message}")

    def _show_podcast_selection(self, podcasts: List[Dict[str, Any]]) -> None:
        """Show podcast selection table.

        Args:
            podcasts: List of podcast results from iTunes
        """

        # Hide episode table, show podcast table
        self.query_one("#episode-table-container").add_class("hidden")
        self.query_one("#podcast-table-container").remove_class("hidden")
        self.viewing_mode = "podcasts"

        # Populate podcast table
        podcast_table = self.query_one("#fetch-podcast-table", DataTable)
        podcast_table.clear()

        for podcast in podcasts:
            name = self._truncate(podcast.get("collectionName", "Unknown"), 48)
            author = self._truncate(podcast.get("artistName", "Unknown"), 28)
            track_count = str(podcast.get("trackCount", "?"))

            podcast_table.add_row(
                Text(name, style="cyan"),
                Text(author, style="white"),
                Text(track_count, style="green"),
            )

        # Update status and label
        status = self.query_one("#status-message", Static)
        status.update(f"✅ Found {len(podcasts)} podcasts - Select one to see episodes")

        label = self.query_one("#search-label", Label)
        label.update(f"Select podcast for '{self.show_name}'")

        # Update detail panel
        detail = self.query_one("#fetch-detail-content", Static)
        detail.update("Select a podcast from the list above to see its episodes")

        # Focus the table
        podcast_table.focus()

        # Update detail for first podcast
        if podcasts:
            self._update_podcast_detail(0)

    def _update_podcast_detail(self, row_idx: int) -> None:
        """Update detail panel with podcast info.

        Args:
            row_idx: Index of podcast in results list
        """
        if row_idx >= len(self.podcast_results):
            return

        podcast = self.podcast_results[row_idx]
        detail = self.query_one("#fetch-detail-content", Static)

        # Build detail text
        name = podcast.get("collectionName", "Unknown")
        author = podcast.get("artistName", "Unknown")
        genre = podcast.get("primaryGenreName", "Unknown")
        track_count = podcast.get("trackCount", "?")
        release_date = podcast.get("releaseDate", "Unknown")

        detail_text = (
            f"Podcast: {name}\n"
            f"Author: {author}\n"
            f"Genre: {genre}\n"
            f"Episodes: {track_count}\n"
            f"Latest: {release_date}"
        )
        detail.update(detail_text)

    def _populate_table(self) -> None:
        """Populate the episode table with RSS episodes."""
        # Hide podcast table, show episode table
        self.query_one("#podcast-table-container").add_class("hidden")
        self.query_one("#episode-table-container").remove_class("hidden")
        self.viewing_mode = "episodes"

        table = self.query_one("#fetch-episode-table", DataTable)
        table.clear()


        from ..utils import format_date, format_duration

        for ep in self.rss_episodes:
            # Format date
            date_str = format_date(ep.get("published", "Unknown"))

            # Format duration
            duration_str = format_duration(ep.get("duration"))

            # Truncate title
            title = self._truncate(ep.get("title", "Unknown"), 58)

            table.add_row(
                Text(date_str, style="green"),
                Text(title, style="white"),
                Text(duration_str, style="cyan"),
            )

        # Update status
        status = self.query_one("#status-message", Static)
        status.update(f"✅ Loaded {len(self.rss_episodes)} episodes")

        # Update search label to show show name
        if self.show_name:
            label = self.query_one("#search-label", Label)
            label.update(f"Episodes for '{self.show_name}'")

        # Focus the table
        table.focus()

        # Update detail panel for first episode
        if self.rss_episodes:
            self._update_fetch_detail(0)

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    @on(DataTable.RowHighlighted, "#fetch-podcast-table")
    def on_podcast_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update detail panel when cursor moves in podcast table."""
        self._update_podcast_detail(event.cursor_row)

    @on(DataTable.RowSelected, "#fetch-podcast-table")
    def on_podcast_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle podcast selection - load episodes for selected podcast."""
        if event.cursor_row >= len(self.podcast_results):
            return

        selected_podcast = self.podcast_results[event.cursor_row]
        feed_url = selected_podcast.get("feedUrl")

        if not feed_url:
            self._show_error("Selected podcast has no feed URL")
            return

        # Store feed URL and show name
        self.feed_url = feed_url
        self.show_name = selected_podcast.get("collectionName", self.show_name)

        # Update status
        status = self.query_one("#status-message", Static)
        status.update("⬇️  Loading episodes...")

        # Load episodes in background worker
        self.load_episodes_from_url(feed_url)

    @on(DataTable.RowHighlighted, "#fetch-episode-table")
    def on_episode_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update detail panel when cursor moves in episode table."""
        self._update_fetch_detail(event.cursor_row)

    @on(DataTable.RowSelected, "#fetch-episode-table")
    def on_fetch_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in fetch table (Enter key pressed)."""
        self.action_fetch_selected()

    def _update_fetch_detail(self, row_index: int) -> None:
        """Update the fetch detail panel with episode information.

        Args:
            row_index: Index of the highlighted row
        """
        if row_index < 0 or row_index >= len(self.rss_episodes):
            return

        ep = self.rss_episodes[row_index]

        from ..utils import format_duration

        # Build detail text
        details = []
        details.append(f"[bold cyan]Title:[/bold cyan] {ep.get('title', 'Unknown')}")
        details.append(
            f"[bold cyan]Published:[/bold cyan] {ep.get('published', 'Unknown')}"
        )

        duration = ep.get("duration")
        if duration:
            duration_str = format_duration(duration)
            details.append(f"[bold cyan]Duration:[/bold cyan] {duration_str}")

        description = ep.get("description", "")
        if description:
            # Strip HTML tags
            import re

            description = re.sub(r"<[^>]+>", "", description)
            # Truncate long descriptions
            if len(description) > 200:
                description = description[:197] + "..."
            details.append(f"[bold cyan]Description:[/bold cyan]\n{description}")

        audio_url = ep.get("audio_url", "")
        if audio_url:
            details.append(f"[bold cyan]Audio URL:[/bold cyan] [dim]{audio_url}[/dim]")

        detail_text = "\n".join(details)

        # Update the detail panel
        detail_content = self.query_one("#fetch-detail-content", Static)
        detail_content.update(detail_text)

    def action_fetch_selected(self) -> None:
        """Fetch the selected episode."""
        table = self.query_one("#fetch-episode-table", DataTable)
        row_index = table.cursor_row

        if row_index < 0 or row_index >= len(self.rss_episodes):
            return

        selected_episode = self.rss_episodes[row_index]

        # Update status
        status = self.query_one("#status-message", Static)
        status.update("⬇️  Fetching episode...")

        # Fetch the episode
        self.fetch_episode(selected_episode)

    @work(exclusive=True, thread=True)
    def fetch_episode(self, episode: Dict[str, Any]) -> None:
        """Fetch the selected episode.

        Args:
            episode: Episode dictionary to fetch
        """
        try:
            from ..fetch import fetch_episode_from_feed

            # Fetch the episode
            result = fetch_episode_from_feed(
                show_name=self.show_name or "Unknown",
                rss_url=self.feed_url or "",
                episode_published=episode.get("published", "Unknown"),
                episode_title=episode.get("title", "Unknown"),
                output_dir=self.scan_dir,
            )

            if result:
                # Return the fetched episode info to the main browser
                self.app.call_from_thread(self._fetch_complete, result)
            else:
                self.app.call_from_thread(self._show_error, "Failed to fetch episode")

        except Exception as e:
            self.app.call_from_thread(
                self._show_error, f"Error fetching episode: {str(e)}"
            )

    def _fetch_complete(self, result: Dict[str, Any]) -> None:
        """Handle fetch completion.

        Args:
            result: Fetch result dictionary
        """
        # Build episode and metadata dicts similar to scan_episode_status
        ep_dir = Path(result.get("directory", ""))
        meta_path = ep_dir / "episode-meta.json"

        if meta_path.exists():
            import json

            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))

                # Build episode dict
                episode = {
                    "meta_path": meta_path,
                    "directory": ep_dir,
                    "show": meta.get("show", "Unknown"),
                    "date": result.get("date", "Unknown"),
                    "title": meta.get("episode_title", "Unknown"),
                    "audio_meta": (ep_dir / "audio-meta.json").exists(),
                    "transcripts": [],
                    "aligned": [],
                    "diarized": [],
                    "deepcasts": [],
                    "has_consensus": False,
                    "notion": False,
                    "last_run": "",
                    "processing_flags": "",
                }

                self.dismiss((episode, meta))
            except Exception as e:
                self._show_error(f"Error loading fetched episode: {str(e)}")
        else:
            self._show_error("Episode metadata not found after fetch")
