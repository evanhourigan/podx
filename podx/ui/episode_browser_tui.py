"""Interactive episode browser using Textual with cursor navigation and detail panel."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static


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
        from rich.text import Text

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
        from rich.text import Text

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

        from rich.text import Text

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


class EpisodeBrowserTUI(App[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]]):
    """Interactive episode browser with cursor navigation and detail panel."""

    TITLE = "Episodes Available for PodX Processing"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #main-container {
        width: 100%;
        height: 100%;
    }

    #table-container {
        width: 100%;
        height: 70%;
        border: solid $primary;
    }

    #detail-container {
        width: 100%;
        height: 30%;
        border: solid $accent;
        padding: 1 2;
    }

    #detail-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .detail-field {
        margin: 0 0 0 2;
    }

    .detail-label {
        color: $text-muted;
        text-style: bold;
    }

    .detail-value {
        color: $text;
    }

    DataTable {
        height: 100%;
        background: $background;
    }

    DataTable > .datatable--header {
        background: $panel;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $primary 20%;
    }

    /* Zebra striping */
    DataTable .datatable--even {
        background: $surface 30%;
    }

    DataTable .datatable--odd {
        background: transparent;
    }
    """

    BINDINGS = [
        Binding("f", "open_fetch", "Fetch Episode", show=True),
        Binding("enter", "select", "Continue", show=True),
        Binding("escape", "quit_app", "Cancel", show=True),
    ]

    def __init__(
        self,
        episodes: List[Dict[str, Any]],
        scan_dir: Path,
        show_last_run: bool = False,
        show_config_on_select: bool = False,
        initial_config: Optional[Dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize episode browser.

        Args:
            episodes: List of episode dictionaries
            scan_dir: Directory episodes were scanned from
            show_last_run: Whether to show Last Run column (for podx run)
            show_config_on_select: If True, show config modal before exiting
            initial_config: Initial configuration for config modal
        """
        super().__init__(*args, **kwargs)
        self.episodes = episodes
        self.scan_dir = scan_dir
        self.show_last_run = show_last_run
        self.show_config_on_select = show_config_on_select
        self.initial_config = initial_config or {}
        self.selected_episode: Optional[Dict[str, Any]] = None
        self.final_config: Optional[Dict[str, Any]] = None

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header(show_clock=False, icon="")
        with Vertical(id="main-container"):
            with Vertical(id="table-container"):
                yield DataTable(
                    id="episode-table", cursor_type="row", zebra_stripes=True
                )
            with Vertical(id="detail-container"):
                yield Static("Episode Details", id="detail-title")
                yield Static("", id="detail-content")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the data table on mount."""
        from rich.text import Text

        from ..utils import format_duration

        table = self.query_one("#episode-table", DataTable)

        # Add columns with colors
        table.add_column(Text("Show", style="bold magenta"), width=20)
        table.add_column(Text("Date", style="bold green"), width=12)
        table.add_column(Text("Title", style="bold white"))  # Expandable
        table.add_column(Text("Duration", style="bold cyan"), width=10)
        if self.show_last_run:
            table.add_column(Text("Last Run", style="bold dim"), width=17)

        # Add rows
        for ep in self.episodes:
            duration_str = format_duration(ep.get("duration"))

            row_data = [
                Text(ep.get("show", "Unknown"), style="magenta"),
                Text(ep.get("date", "Unknown"), style="green"),
                Text(ep.get("title", "Unknown"), style="white"),
                Text(duration_str, style="cyan"),
            ]

            if self.show_last_run:
                last_run = ep.get("last_run", "")
                row_data.append(Text(last_run or "-", style="white"))

            table.add_row(*row_data)

        # Focus the table
        table.focus()

        # Update detail panel for first episode if available
        if self.episodes:
            self._update_detail_panel(0)

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update detail panel when cursor moves."""
        try:
            self._update_detail_panel(event.cursor_row)
        except Exception:
            # Ignore errors during highlight - can happen during screen transitions
            pass

    @on(DataTable.RowSelected, "#episode-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key pressed)."""
        self.action_select()

    def _update_detail_panel(self, row_index: int) -> None:
        """Update the detail panel with episode information.

        Args:
            row_index: Index of the highlighted row
        """
        if row_index < 0 or row_index >= len(self.episodes):
            return

        ep = self.episodes[row_index]

        # Build detail text
        from ..utils import format_duration

        details = []
        details.append(f"[bold cyan]Show:[/bold cyan] {ep.get('show', 'Unknown')}")
        details.append(f"[bold cyan]Title:[/bold cyan] {ep.get('title', 'Unknown')}")
        details.append(f"[bold cyan]Date:[/bold cyan] {ep.get('date', 'Unknown')}")

        # Duration
        duration = ep.get("duration")
        if duration:
            duration_str = format_duration(duration)
            details.append(f"[bold cyan]Duration:[/bold cyan] {duration_str}")

        # Get processing artifacts
        transcripts = ep.get("transcripts", [])
        diarized = ep.get("diarized", [])
        deepcasts = ep.get("deepcasts", [])
        has_consensus = ep.get("has_consensus", False)

        # Extract unique ASR models from all transcript files
        all_models = set()
        for t in transcripts:
            # Extract model from filenames like "transcript-large-v3.json", "transcript-diarized-large-v3.json"
            name = t.name
            if name.startswith("transcript-") and name.endswith(".json"):
                # Remove "transcript-" prefix and ".json" suffix
                middle = name[11:-5]
                # Remove stage prefixes (aligned-, diarized-, preprocessed-)
                for prefix in ["aligned-", "diarized-", "preprocessed-"]:
                    if middle.startswith(prefix):
                        middle = middle[len(prefix) :]
                        break
                if middle:
                    all_models.add(middle)

        if all_models:
            models_str = ", ".join(sorted(all_models))
            details.append(f"[bold cyan]ASR Models:[/bold cyan] {models_str}")

        # Diarized transcripts - show models or (none)
        diar_models = set()
        for d in diarized:
            name = d.name
            if name.startswith("transcript-diarized-") and name.endswith(".json"):
                model = name[20:-5]  # Remove "transcript-diarized-" and ".json"
                if model:
                    diar_models.add(model)
        if diar_models:
            diar_str = ", ".join(sorted(diar_models))
            details.append(f"[bold cyan]Diarizations:[/bold cyan] {diar_str}")
        else:
            details.append("[bold cyan]Diarizations:[/bold cyan] [dim](none)[/dim]")

        # Pre-processed transcripts - show models or (none)
        prep_models = set()
        for p in transcripts:
            name = p.name
            if (
                "preprocessed" in name
                and name.startswith("transcript-")
                and name.endswith(".json")
            ):
                # Extract model from "transcript-preprocessed-large-v3.json"
                middle = name[11:-5]  # Remove "transcript-" and ".json"
                if middle.startswith("preprocessed-"):
                    model = middle[13:]  # Remove "preprocessed-"
                    if model:
                        prep_models.add(model)
        if prep_models:
            prep_str = ", ".join(sorted(prep_models))
            details.append(f"[bold cyan]Pre-Processed:[/bold cyan] {prep_str}")
        else:
            details.append("[bold cyan]Pre-Processed:[/bold cyan] [dim](none)[/dim]")

        # Deepcast outputs - show (ASR model, AI model, type) or count
        if deepcasts:
            # Try to extract deepcast metadata
            deepcast_info = []
            for dc in deepcasts[:3]:  # Show first 3
                # Try to parse deepcast filename for info
                # Format: deepcast-{asr_model}-{ai_model}-{type}.{ext}
                name = dc.stem
                if name.startswith("deepcast-"):
                    parts = name[9:].split("-", 2)
                    if len(parts) >= 3:
                        asr_m, ai_m, dc_type = parts[0], parts[1], parts[2]
                        deepcast_info.append(f"({asr_m}, {ai_m}, {dc_type})")
            if deepcast_info:
                info_str = ", ".join(deepcast_info)
                if len(deepcasts) > 3:
                    info_str += f" ... (+{len(deepcasts)-3} more)"
                details.append(f"[bold cyan]Deepcasts:[/bold cyan] {info_str}")
            else:
                # Fallback to just count
                details.append(
                    f"[bold cyan]Deepcasts:[/bold cyan] {len(deepcasts)} output{'s' if len(deepcasts) > 1 else ''}"
                )
        else:
            details.append("[bold cyan]Deepcasts:[/bold cyan] [dim](none)[/dim]")

        # Consensus
        if has_consensus:
            details.append("[bold cyan]Consensus:[/bold cyan] Yes")

        # Directory info
        ep_dir = ep.get("directory", "")
        details.append(f"[bold cyan]Directory:[/bold cyan] [dim]{ep_dir}[/dim]")

        detail_text = "\n".join(details)

        # Update the detail panel
        detail_content = self.query_one("#detail-content", Static)
        detail_content.update(detail_text)

    def action_select(self) -> None:
        """Select the currently highlighted episode."""
        table = self.query_one("#episode-table", DataTable)
        row_index = table.cursor_row

        if row_index < 0 or row_index >= len(self.episodes):
            return

        selected = self.episodes[row_index]
        self.selected_episode = selected

        # If config modal should be shown, show it; otherwise exit immediately
        if self.show_config_on_select:
            self.show_config_modal()
        else:
            # Load full metadata from file and exit
            meta_path = selected.get("meta_path")
            if meta_path and meta_path.exists():
                import json

                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    self.exit((selected, meta))
                except Exception:
                    self.exit((selected, {}))
            else:
                self.exit((selected, {}))

    def show_config_modal(self) -> None:
        """Show configuration modal after episode selection."""

        async def show() -> None:
            from .config_panel import ConfigPanel

            config = await self.push_screen_wait(ConfigPanel(self.initial_config))
            if config is not None:
                # User confirmed config - exit with episode and config
                self.final_config = config

                # Load metadata
                meta_path = self.selected_episode.get("meta_path")
                if meta_path and meta_path.exists():
                    import json

                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        self.exit((self.selected_episode, meta, config))
                    except Exception:
                        self.exit((self.selected_episode, {}, config))
                else:
                    self.exit((self.selected_episode, {}, config))
            # If config is None, user pressed Esc - stay on episode browser (do nothing)

        self.run_worker(show())

    def action_open_fetch(self) -> None:
        """Open the fetch modal to fetch a new episode."""

        async def open_fetch_modal() -> None:
            result = await self.push_screen_wait(FetchModal(self.scan_dir))
            if result:
                # Episode was fetched, add it to the list and sort it
                episode, meta = result
                self.episodes.append(episode)

                # Re-sort episodes (newest first, same as initial sort)
                self.episodes.sort(key=lambda x: (x["date"], x["show"]), reverse=True)

                # Find the index of the newly added episode
                episode_path = episode.get("directory")
                new_index = 0
                for idx, ep in enumerate(self.episodes):
                    if ep.get("directory") == episode_path:
                        new_index = idx
                        break

                # Refresh table with sorted episodes
                self._refresh_table()

                # Select the newly added episode at its sorted position
                table = self.query_one("#episode-table", DataTable)
                table.move_cursor(row=new_index)
                # Update detail panel after a short delay to ensure screen is ready
                self.call_later(lambda: self._update_detail_panel(new_index))

        self.run_worker(open_fetch_modal())

    def _refresh_table(self) -> None:
        """Refresh the episode table with current episodes list."""
        from rich.text import Text

        from ..utils import format_duration

        table = self.query_one("#episode-table", DataTable)
        table.clear()

        # Re-add all rows - must match the column structure from on_mount
        for ep in self.episodes:
            duration_str = format_duration(ep.get("duration"))

            row_data = [
                Text(ep.get("show", "Unknown"), style="magenta"),
                Text(ep.get("date", "Unknown"), style="green"),
                Text(ep.get("title", "Unknown"), style="white"),
                Text(duration_str, style="cyan"),
            ]

            if self.show_last_run:
                last_run = ep.get("last_run", "")
                row_data.append(Text(last_run or "-", style="white"))

            table.add_row(*row_data)

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.exit((None, None))


def select_episode_with_config(
    scan_dir: Path,
    config: Dict[str, Any],
    show_filter: Optional[str] = None,
) -> Tuple[
    Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]
]:
    """Select episode and configure pipeline using TUI with integrated config modal.

    Args:
        scan_dir: Directory to scan for episodes
        config: Initial pipeline configuration
        show_filter: Optional show name filter

    Returns:
        Tuple of (selected_episode, episode_metadata, updated_config) or (None, None, None) if cancelled

    Raises:
        SystemExit: If no episodes found
    """
    from ..logging import restore_logging, suppress_logging
    from .episode_selector import scan_episode_status

    # Suppress logging to prevent messages from corrupting TUI display
    suppress_logging()

    try:
        # Scan episodes
        episodes = scan_episode_status(scan_dir)

        # Optional filter by --show if provided
        if show_filter:
            s_l = show_filter.lower()
            episodes = [e for e in episodes if s_l in (e.get("show", "").lower())]

        if not episodes:
            restore_logging()
            if show_filter:
                print(f"❌ No episodes found for show '{show_filter}' in {scan_dir}")
            else:
                print(f"❌ No episodes found in {scan_dir}")
            raise SystemExit(1)

        # Sort newest first
        episodes_sorted = sorted(
            episodes, key=lambda x: (x["date"], x["show"]), reverse=True
        )

        # Run TUI with config modal enabled
        app = EpisodeBrowserTUI(
            episodes_sorted,
            scan_dir,
            show_last_run=True,
            show_config_on_select=True,
            initial_config=config,
        )
        result = app.run()

        # Handle cancellation or None result
        if result is None or result == (None, None):
            restore_logging()
            return (None, None, None)

        # Unpack result - should be (episode, meta, config)
        if isinstance(result, tuple) and len(result) == 3:
            return result
        elif isinstance(result, tuple) and len(result) == 2:
            # Fallback for older code paths
            restore_logging()
            return (result[0], result[1], None)
        else:
            # Unexpected format
            restore_logging()
            return (None, None, None)

    finally:
        restore_logging()


def select_episode_with_tui(
    scan_dir: Path,
    show_filter: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Select an episode using the Textual TUI.

    Args:
        scan_dir: Directory to scan for episodes
        show_filter: Optional show name filter

    Returns:
        Tuple of (selected_episode, episode_metadata) or (None, None) if cancelled

    Raises:
        SystemExit: If no episodes found
    """
    from ..logging import restore_logging, suppress_logging
    from .episode_selector import scan_episode_status

    # Suppress logging to prevent messages from corrupting TUI display
    suppress_logging()

    try:
        # Scan episodes
        episodes = scan_episode_status(scan_dir)

        # Optional filter by --show if provided
        if show_filter:
            s_l = show_filter.lower()
            episodes = [e for e in episodes if s_l in (e.get("show", "").lower())]

        if not episodes:
            if show_filter:
                print(f"❌ No episodes found for show '{show_filter}' in {scan_dir}")
                print("Tip: run 'podx-fetch --interactive' to download episodes first.")
            else:
                print(f"❌ No episodes found in {scan_dir}")
            raise SystemExit(1)

        # Sort newest first
        episodes_sorted = sorted(
            episodes, key=lambda x: (x["date"], x["show"]), reverse=True
        )

        # Run the TUI (with Last Run column for podx run)
        app = EpisodeBrowserTUI(episodes_sorted, scan_dir, show_last_run=True)
        result = app.run()

        if result == (None, None):
            print("❌ Episode selection cancelled")
            raise SystemExit(0)

        return result
    finally:
        # Always restore logging after TUI exits
        restore_logging()


class StandaloneFetchBrowser(App[Optional[Dict[str, Any]]]):
    """Standalone fetch browser for podx-fetch --interactive."""

    TITLE = "Podcast Episode Fetch"
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        show_name: Optional[str],
        rss_url: Optional[str],
        output_dir: Path,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize standalone fetch browser.

        Args:
            show_name: Name of show to search for (optional)
            rss_url: Direct RSS URL (optional)
            output_dir: Directory to save fetched episodes
        """
        super().__init__(*args, **kwargs)
        self.show_name = show_name
        self.rss_url = rss_url
        self.output_dir = output_dir
        self.result: Optional[Dict[str, Any]] = None

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        # Just show a simple message and immediately open the fetch modal
        yield Header(show_clock=False, icon="")
        yield Static("Loading fetch browser...", id="loading-message")
        yield Footer()

    def on_mount(self) -> None:
        """Open fetch modal on mount."""
        self.open_fetch_modal()

    def open_fetch_modal(self) -> None:
        """Open the fetch modal."""

        async def show_modal() -> None:
            # Create a temporary FetchModal with pre-filled show name
            modal = FetchModal(self.output_dir)
            if self.rss_url:
                modal.rss_url = self.rss_url
            if self.show_name:
                modal.show_name = self.show_name
                # Note: search will be triggered automatically in modal's on_mount

            result = await self.push_screen_wait(modal)
            if result:
                # Episode was fetched - result is (episode, meta)
                episode, meta = result
                # Reconstruct the expected result format for fetch.py main()
                full_result = {
                    "meta": meta,
                    "meta_path": str(episode.get("meta_path", "")),
                    "directory": str(episode.get("directory", "")),
                    "date": episode.get("date", ""),
                }
                self.exit(full_result)
            else:
                # User cancelled
                self.exit(None)

        self.run_worker(show_modal())


def run_fetch_browser_standalone(
    show_name: Optional[str],
    rss_url: Optional[str],
    output_dir: Path,
) -> Optional[Dict[str, Any]]:
    """Run standalone fetch browser for podx-fetch --interactive.

    Args:
        show_name: Name of show to search for (optional)
        rss_url: Direct RSS URL (optional)
        output_dir: Directory to save fetched episodes

    Returns:
        Fetch result dictionary with metadata, or None if cancelled
    """
    app = StandaloneFetchBrowser(show_name, rss_url, output_dir)
    return app.run()


class ModelLevelProcessingBrowser(App):
    """Browser for model-level commands (align, diarize, preprocess) - one row per ASR model."""

    TITLE = "Select Transcript for Processing"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: $background;
    }

    #table-container {
        height: 1fr;
        border: solid $primary;
    }

    DataTable {
        height: 100%;
        background: $background;
    }

    DataTable > .datatable--header {
        text-style: bold;
        background: $boost;
    }

    DataTable > .datatable--cursor {
        background: $secondary 30%;
    }

    DataTable .datatable--even {
        background: $surface 30%;
    }

    DataTable .datatable--odd {
        background: transparent;
    }

    #detail-panel {
        width: 100%;
        height: 8;
        border-top: solid $primary;
        padding: 1 2;
        background: $panel;
    }

    #detail-content {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("enter", "select", "Select & Continue", show=True),
        Binding("escape", "quit_app", "Cancel", show=True),
    ]

    def __init__(
        self,
        items: List[Dict[str, Any]],
        model_key: str = "asr_model",
        status_key: str = "is_aligned",
    ):
        """Initialize model-level browser.

        Args:
            items: List of transcript/model items
            model_key: Key to extract model name from (default: "asr_model")
            status_key: Key to check for completion status (default: "is_aligned")
        """
        super().__init__()
        self.items = items
        self.model_key = model_key
        self.status_key = status_key
        self.selected_item = None

        # Check if any items have checkmarks
        self.has_checkmarks = any(item.get(status_key, False) for item in items)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False, icon="")
        with Container(id="table-container"):
            yield DataTable(id="item-table", cursor_type="row", zebra_stripes=True)
        yield Container(
            Static(id="detail-content"),
            id="detail-panel",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#item-table", DataTable)

        # Add columns - conditionally include checkmark column (no heading, 2 chars wide)
        if self.has_checkmarks:
            table.add_column("", key="check", width=2)

        table.add_column("ASR Model", key="model", width=16)
        table.add_column("Stage", key="stage", width=13)
        table.add_column("Show", key="show", width=20)
        table.add_column("Date", key="date", width=10)
        table.add_column("Title", key="title")

        # Add rows
        for idx, item in enumerate(self.items):
            model_name = item.get(self.model_key, "unknown")
            is_complete = item.get(self.status_key, False)

            # Extract processing stage
            processing_stage = item.get("processing_stage", "base")
            stage_display = processing_stage.capitalize()

            # Extract episode metadata
            episode_meta = item.get("episode_meta", {})
            show = episode_meta.get("show", "Unknown")

            # Parse date
            date_str = episode_meta.get("episode_published", "")
            if date_str:
                try:
                    from dateutil import parser as dtparse

                    parsed = dtparse.parse(date_str)
                    date = parsed.strftime("%Y-%m-%d")
                except Exception:
                    date = date_str[:10] if len(date_str) >= 10 else "Unknown"
            else:
                # Fallback to directory name
                directory = item.get("directory")
                date = directory.name if directory else "Unknown"

            title = episode_meta.get("episode_title", "Unknown")

            # Build row
            if self.has_checkmarks:
                check_mark = "✓" if is_complete else ""
                table.add_row(
                    Text(check_mark, style="green"),
                    Text(model_name, style="magenta"),
                    Text(stage_display, style="cyan"),
                    Text(show, style="green"),
                    Text(date, style="blue"),
                    Text(title, style="white"),
                    key=str(idx),
                )
            else:
                table.add_row(
                    Text(model_name, style="magenta"),
                    Text(stage_display, style="cyan"),
                    Text(show, style="green"),
                    Text(date, style="blue"),
                    Text(title, style="white"),
                    key=str(idx),
                )

        # Set focus
        table.focus()

        # Show initial detail
        if self.items:
            self._update_detail_panel(self.items[0])

    def _update_detail_panel(self, item: Dict[str, Any]) -> None:
        """Update detail panel with item information."""
        try:
            detail = self.query_one("#detail-content", Static)
            episode_meta = item.get("episode_meta", {})
            show = episode_meta.get("show", "Unknown")
            date_str = episode_meta.get("episode_published", "")

            # Parse date
            if date_str:
                try:
                    from dateutil import parser as dtparse

                    parsed = dtparse.parse(date_str)
                    date = parsed.strftime("%Y-%m-%d")
                except Exception:
                    date = date_str[:10] if len(date_str) >= 10 else "Unknown"
            else:
                directory = item.get("directory")
                date = directory.name if directory else "Unknown"

            title = episode_meta.get("episode_title", "Unknown")
            directory = item.get("directory", "")
            model = item.get(self.model_key, "unknown")

            content = f"""[bold cyan]{show}[/bold cyan] • {date}
[white]{title}[/white]
[magenta]Model: {model}[/magenta]
[dim]{directory}[/dim]"""

            detail.update(content)
        except Exception:
            pass

    @on(DataTable.RowHighlighted, "#item-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight to update detail panel."""
        try:
            row_key = event.row_key
            if row_key is not None:
                idx = int(row_key.value)
                if 0 <= idx < len(self.items):
                    self.call_later(self._update_detail_panel, self.items[idx])
        except Exception:
            pass

    @on(DataTable.RowSelected, "#item-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key pressed)."""
        self.action_select()

    def action_select(self) -> None:
        """Select current item and exit."""
        table = self.query_one("#item-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.coordinate_to_cell_key(
                Coordinate(table.cursor_row, 0)
            ).row_key
            if row_key is not None:
                idx = int(row_key.value)
                if 0 <= idx < len(self.items):
                    self.selected_item = self.items[idx]
                    self.exit(self.selected_item)

    def action_quit_app(self) -> None:
        """Quit without selection."""
        self.exit(None)


class SimpleProcessingBrowser(App):
    """Simplified episode browser for processing commands (transcode, transcribe, etc)."""

    TITLE = "Select Episode for Processing"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: $background;
    }

    #table-container {
        height: 1fr;
        border: solid $primary;
    }

    DataTable {
        height: 100%;
        background: $background;
    }

    DataTable > .datatable--header {
        text-style: bold;
        background: $boost;
    }

    DataTable > .datatable--cursor {
        background: $secondary 30%;
    }

    DataTable .datatable--even {
        background: $surface 30%;
    }

    DataTable .datatable--odd {
        background: transparent;
    }

    #detail-panel {
        height: 8;
        border-top: solid $primary;
        padding: 1 2;
        background: $panel;
    }

    #detail-content {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("enter", "select", "Select & Continue", show=True),
        Binding("escape", "quit_app", "Cancel", show=True),
    ]

    def __init__(
        self, episodes: List[Dict[str, Any]], show_model_selection: bool = False
    ):
        super().__init__()
        self.episodes = episodes
        self.selected_episode = None
        self.show_model_selection = show_model_selection
        self.selected_model: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False, icon="")
        with Container(id="table-container"):
            yield DataTable(id="episode-table", cursor_type="row", zebra_stripes=True)
        yield Container(
            Static(id="detail-content"),
            id="detail-panel",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#episode-table", DataTable)

        # Add columns
        table.add_column("#", key="num", width=4)
        table.add_column("Status", key="status", width=24)
        table.add_column("Show", key="show", width=20)
        table.add_column("Date", key="date", width=12)
        table.add_column("Title", key="title")

        # Add rows
        for idx, ep in enumerate(self.episodes, start=1):
            # Determine status from episode data
            status = self._get_episode_status(ep)

            table.add_row(
                Text(str(idx), style="cyan"),
                Text(status, style="magenta"),
                Text(ep.get("show", "Unknown"), style="green"),
                Text(ep.get("date", "Unknown"), style="blue"),
                Text(ep.get("title", "Unknown"), style="white"),
                key=str(idx - 1),
            )

        # Set focus
        table.focus()

        # Show initial detail
        if self.episodes:
            self._update_detail_panel(self.episodes[0])

    def _get_episode_status(self, episode: Dict[str, Any]) -> str:
        """Get status string for episode based on available data."""
        # Check for transcripts
        if "transcripts" in episode and episode["transcripts"]:
            models = list(episode["transcripts"].keys())
            return f"✓ {', '.join(models)}"

        # Check if audio_meta exists (for transcode)
        if episode.get("audio_meta"):
            return "✓ Done"

        # Check if is_transcoded flag exists
        if episode.get("is_transcoded"):
            return "✓ Done"

        # Check for transcript files (for align/diarize/preprocess)
        if "transcript_data" in episode or "aligned_data" in episode:
            asr_model = episode.get("asr_model", "unknown")
            return f"✓ {asr_model}"

        return "○ New"

    def _update_detail_panel(self, episode: Dict[str, Any]) -> None:
        """Update detail panel with episode information."""
        try:
            detail = self.query_one("#detail-content", Static)
            show = episode.get("show", "Unknown")
            date = episode.get("date", "Unknown")
            title = episode.get("title", "Unknown")
            directory = episode.get("directory", "")

            content = f"""[bold cyan]{show}[/bold cyan] • {date}
[white]{title}[/white]
[dim]{directory}[/dim]"""

            detail.update(content)
        except Exception:
            pass

    @on(DataTable.RowHighlighted, "#episode-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight to update detail panel."""
        try:
            row_key = event.row_key
            if row_key is not None:
                idx = int(row_key.value)
                if 0 <= idx < len(self.episodes):
                    self.call_later(self._update_detail_panel, self.episodes[idx])
        except Exception:
            pass

    @on(DataTable.RowSelected, "#episode-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key pressed)."""
        self.action_select()

    def action_select(self) -> None:
        """Select current episode and exit."""
        table = self.query_one("#episode-table", DataTable)
        if table.cursor_row is not None:
            row_key = table.coordinate_to_cell_key(
                Coordinate(table.cursor_row, 0)
            ).row_key
            if row_key is not None:
                idx = int(row_key.value)
                if 0 <= idx < len(self.episodes):
                    self.selected_episode = self.episodes[idx]

                    # If model selection should be shown, show it; otherwise exit immediately
                    if self.show_model_selection:
                        self.show_model_modal()
                    else:
                        self.exit(self.selected_episode)

    def show_model_modal(self) -> None:
        """Show ASR model selection modal after episode selection."""

        async def show() -> None:
            from .transcribe_tui import ASRModelModal

            # Get transcribed models from selected episode
            transcribed_models = list(
                self.selected_episode.get("transcripts", {}).keys()
            )

            modal = ASRModelModal(transcribed_models)
            selected_model = await self.push_screen_wait(modal)

            if selected_model is not None:
                # User confirmed model selection - exit with (episode, model)
                self.selected_model = selected_model
                self.exit((self.selected_episode, selected_model))
            # If selected_model is None, user pressed Esc - stay on episode browser (do nothing)

        self.run_worker(show())

    def action_quit_app(self) -> None:
        """Quit without selection."""
        self.exit(None)


def select_episode_for_processing(
    scan_dir: Path,
    title: str = "Select Episode for Processing",
    show_filter: Optional[str] = None,
    episode_scanner: Optional[callable] = None,
    show_model_selection: bool = False,
) -> Optional[Dict[str, Any]]:
    """Select an episode for processing using the Textual TUI.

    Args:
        scan_dir: Directory to scan for episodes
        title: Window title for the browser
        show_filter: Optional show name filter
        episode_scanner: Optional custom scanner function (default: scan_episode_status)
        show_model_selection: If True, show model selection modal and return (episode, model) tuple

    Returns:
        Selected episode dictionary, or (episode, model) tuple if show_model_selection=True, or None if cancelled

    Raises:
        SystemExit: If no episodes found
    """
    import json

    from dateutil import parser as dtparse

    from ..logging import restore_logging, suppress_logging
    from .episode_selector import scan_episode_status

    # Suppress logging during TUI interaction
    suppress_logging()

    try:
        # Use custom scanner if provided, otherwise use default
        if episode_scanner:
            episodes = episode_scanner(scan_dir)
        else:
            episodes = scan_episode_status(scan_dir)

        if not episodes:
            print(f"❌ No episodes found in {scan_dir}")
            raise SystemExit(1)

        # Normalize episode structure - some scanners return different formats
        normalized_episodes = []
        for ep in episodes:
            # If already has top-level show/date/title, use as-is
            if "show" in ep and "date" in ep and "title" in ep:
                normalized_episodes.append(ep)
            else:
                # Extract from episode-meta.json or meta_data
                episode_dir = ep.get("directory")
                if not episode_dir:
                    continue

                # Try to load episode-meta.json
                episode_meta_path = episode_dir / "episode-meta.json"
                if episode_meta_path.exists():
                    try:
                        episode_meta = json.loads(
                            episode_meta_path.read_text(encoding="utf-8")
                        )
                    except Exception:
                        episode_meta = {}
                else:
                    episode_meta = ep.get("meta_data", {})

                # Extract show, date, title
                show_val = episode_meta.get("show", "Unknown")
                date_val = episode_meta.get("episode_published", "")

                # Format date YYYY-MM-DD when possible
                if date_val:
                    try:
                        parsed = dtparse.parse(date_val)
                        date_fmt = parsed.strftime("%Y-%m-%d")
                    except Exception:
                        date_fmt = date_val[:10] if len(date_val) >= 10 else date_val
                else:
                    date_fmt = episode_dir.name

                title_val = episode_meta.get("episode_title", "Unknown")

                # Create normalized episode with top-level keys
                normalized_ep = dict(ep)  # Copy original data
                normalized_ep["show"] = show_val
                normalized_ep["date"] = date_fmt
                normalized_ep["title"] = title_val
                normalized_episodes.append(normalized_ep)

        if not normalized_episodes:
            print(f"❌ No episodes found in {scan_dir}")
            raise SystemExit(1)

        # Optional filter by --show if provided
        if show_filter:
            s_l = show_filter.lower()
            normalized_episodes = [
                e for e in normalized_episodes if s_l in (e.get("show", "").lower())
            ]

        if not normalized_episodes:
            print(f"❌ No episodes found for show '{show_filter}' in {scan_dir}")
            raise SystemExit(1)

        # Sort newest first
        episodes_sorted = sorted(
            normalized_episodes, key=lambda x: (x["date"], x["show"]), reverse=True
        )

        # Run the simplified TUI with custom title
        class CustomProcessingBrowser(SimpleProcessingBrowser):
            TITLE = title

        app = CustomProcessingBrowser(
            episodes_sorted, show_model_selection=show_model_selection
        )
        result = app.run()

        if result is None:
            raise SystemExit(0)

        return result
    finally:
        # Always restore logging after TUI exits
        restore_logging()
