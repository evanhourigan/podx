"""Interactive episode browser using Textual with cursor navigation and detail panel."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static
from rich.text import Text


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

    #episode-table-container {
        height: 60%;
        border: solid $primary;
        margin-bottom: 1;
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

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="fetch-container"):
            with Vertical(id="search-container"):
                yield Label("Search for a podcast show:", id="search-label")
                yield Input(placeholder="Enter show name and press Enter...", id="search-input")
                yield Static("", id="status-message")
            with Vertical(id="episode-table-container"):
                yield DataTable(id="fetch-episode-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="fetch-detail-container"):
                yield Static("Episode Details", id="fetch-detail-title")
                yield Static("Select a show to see episodes", id="fetch-detail-content")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the modal on mount."""
        from rich.text import Text

        # Focus the search input
        self.query_one("#search-input", Input).focus()

        # Set up the table
        table = self.query_one("#fetch-episode-table", DataTable)
        table.add_column(Text("Date", style="bold green"), width=12)
        table.add_column(Text("Title", style="bold white"), width=60)
        table.add_column(Text("Duration", style="bold cyan"), width=10)

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
            self.feed_url = input_value if input_value.startswith("http") else f"https://{input_value}"
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
                            duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
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
            self.app.call_from_thread(self._show_error, f"Error loading episodes: {str(e)}")

    @work(exclusive=True, thread=True)
    def search_and_load(self, show_name: str) -> None:
        """Search for show and load episodes.

        Args:
            show_name: Name of the show to search for
        """
        try:
            # Find RSS feed
            from ..fetch import find_feed_for_show

            feed_url = find_feed_for_show(show_name)
            if not feed_url:
                self.app.call_from_thread(self._show_error, f"Could not find RSS feed for '{show_name}'")
                return

            self.feed_url = feed_url

            # Parse feed and load episodes
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

    def _populate_table(self) -> None:
        """Populate the episode table with RSS episodes."""
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
        return text[:max_len - 1] + "…"

    @on(DataTable.RowHighlighted, "#fetch-episode-table")
    def on_fetch_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update detail panel when cursor moves in fetch table."""
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
        details.append(f"[bold cyan]Published:[/bold cyan] {ep.get('published', 'Unknown')}")

        duration = ep.get("duration")
        if duration:
            duration_str = format_duration(duration)
            details.append(f"[bold cyan]Duration:[/bold cyan] {duration_str}")

        description = ep.get("description", "")
        if description:
            # Strip HTML tags
            import re
            description = re.sub(r'<[^>]+>', '', description)
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
            self.app.call_from_thread(self._show_error, f"Error fetching episode: {str(e)}")

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
        Binding("enter", "select", "Select & Continue", show=True),
        Binding("escape", "quit_app", "Cancel", show=True),
    ]

    def __init__(
        self,
        episodes: List[Dict[str, Any]],
        scan_dir: Path,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize episode browser.

        Args:
            episodes: List of episode dictionaries
            scan_dir: Directory episodes were scanned from
        """
        super().__init__(*args, **kwargs)
        self.episodes = episodes
        self.scan_dir = scan_dir
        self.selected_episode: Optional[Dict[str, Any]] = None

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header(show_clock=False, icon="")
        with Vertical(id="main-container"):
            with Vertical(id="table-container"):
                yield DataTable(id="episode-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="detail-container"):
                yield Static("Episode Details", id="detail-title")
                yield Static("", id="detail-content")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the data table on mount."""
        from rich.text import Text

        table = self.query_one("#episode-table", DataTable)

        # Add columns with colors
        table.add_column(Text("Show", style="bold magenta"), width=18)
        table.add_column(Text("Date", style="bold green"), width=12)
        table.add_column(Text("Title", style="bold white"), width=50)
        table.add_column(Text("ASR", style="bold cyan"), width=4)
        table.add_column(Text("Aln", style="bold yellow"), width=4)
        table.add_column(Text("Diar", style="bold blue"), width=4)
        table.add_column(Text("Deep", style="bold red"), width=4)
        table.add_column(Text("Proc", style="bold bright_magenta"), width=5)
        table.add_column(Text("Last Run", style="bold dim"), width=17)

        # Add rows
        for ep in self.episodes:
            num_transcripts = len(ep.get("transcripts", []))
            num_aligned = len(ep.get("aligned", []))
            num_diarized = len(ep.get("diarized", []))
            num_deepcasts = len(ep.get("deepcasts", []))

            # Format counts (show number or dash)
            asr_val = str(num_transcripts) if num_transcripts > 0 else "-"
            aln_val = "✓" if num_aligned > 0 else "○"
            diar_val = "✓" if num_diarized > 0 else "○"
            deep_val = str(num_deepcasts) if num_deepcasts > 0 else "-"

            proc_flags = ep.get("processing_flags", "")
            last_run = ep.get("last_run", "")

            # Only show last_run if there are actual processing files
            has_processing = (
                num_transcripts > 0 or num_aligned > 0 or num_diarized > 0 or num_deepcasts > 0
            )
            last_run_display = last_run if (has_processing and last_run) else "-"

            table.add_row(
                Text(ep.get("show", "Unknown"), style="magenta"),
                Text(ep.get("date", "Unknown"), style="green"),
                Text(self._truncate(ep.get("title", "Unknown"), 48), style="white"),
                Text(asr_val, style="cyan"),
                Text(aln_val, style="yellow"),
                Text(diar_val, style="blue"),
                Text(deep_val, style="red"),
                Text(proc_flags or "-", style="bright_magenta"),
                Text(last_run_display, style="white"),
            )

        # Focus the table
        table.focus()

        # Update detail panel for first episode if available
        if self.episodes:
            self._update_detail_panel(0)

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[:max_len - 1] + "…"

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
        details = []
        details.append(f"[bold cyan]Show:[/bold cyan] {ep.get('show', 'Unknown')}")
        details.append(f"[bold cyan]Title:[/bold cyan] {ep.get('title', 'Unknown')}")
        details.append(f"[bold cyan]Date:[/bold cyan] {ep.get('date', 'Unknown')}")

        # Get processing artifacts
        transcripts = ep.get("transcripts", [])
        aligned = ep.get("aligned", [])
        diarized = ep.get("diarized", [])
        deepcasts = ep.get("deepcasts", [])
        has_consensus = ep.get("has_consensus", False)

        # Extract ASR models from transcript filenames
        if transcripts:
            models = set()
            for t in transcripts:
                # Extract model name from filename like "transcript-large-v3.json"
                name = t.name
                if name.startswith("transcript-") and name.endswith(".json"):
                    model = name[11:-5]  # Remove "transcript-" and ".json"
                    models.add(model)
            if models:
                models_str = ", ".join(sorted(models))
                details.append(f"[bold cyan]ASR Models:[/bold cyan] {models_str} ({len(transcripts)} total)")
            else:
                details.append(f"[bold cyan]ASR Models:[/bold cyan] {len(transcripts)} transcript{'s' if len(transcripts) > 1 else ''}")

        # Aligned transcripts
        if aligned:
            details.append(f"[bold cyan]Aligned:[/bold cyan] Yes ({len(aligned)} file{'s' if len(aligned) > 1 else ''})")

        # Diarized transcripts
        if diarized:
            details.append(f"[bold cyan]Diarized:[/bold cyan] Yes ({len(diarized)} file{'s' if len(diarized) > 1 else ''})")

        # Deepcast outputs
        if deepcasts:
            details.append(f"[bold cyan]Deepcast:[/bold cyan] {len(deepcasts)} output{'s' if len(deepcasts) > 1 else ''}")

        # Processing flags expanded
        proc_flags = ep.get("processing_flags", "")
        if proc_flags:
            flag_names = []
            if "P" in proc_flags:
                flag_names.append("Preprocessed")
            if "A" in proc_flags:
                flag_names.append("Aligned")
            if "D" in proc_flags:
                flag_names.append("Diarized")
            if "Q" in proc_flags:
                flag_names.append("Agreement/QA")
            if flag_names:
                details.append(f"[bold cyan]Processing Flags:[/bold cyan] {', '.join(flag_names)}")

        # Consensus
        if has_consensus:
            details.append("[bold cyan]Consensus:[/bold cyan] Yes")

        # Last run - only show if there are actual processing files
        last_run = ep.get("last_run", "")
        if transcripts or aligned or diarized or deepcasts:
            details.append(f"[bold cyan]Last Run:[/bold cyan] {last_run or '[dim]Unknown[/dim]'}")
        else:
            details.append("[bold cyan]Last Run:[/bold cyan] [dim]Never processed[/dim]")

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

        # Load full metadata from file
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

        table = self.query_one("#episode-table", DataTable)
        table.clear()

        # Re-add all rows
        for ep in self.episodes:
            num_transcripts = len(ep.get("transcripts", []))
            num_aligned = len(ep.get("aligned", []))
            num_diarized = len(ep.get("diarized", []))
            num_deepcasts = len(ep.get("deepcasts", []))

            # Format counts
            asr_val = str(num_transcripts) if num_transcripts > 0 else "-"
            aln_val = "✓" if num_aligned > 0 else "○"
            diar_val = "✓" if num_diarized > 0 else "○"
            deep_val = str(num_deepcasts) if num_deepcasts > 0 else "-"

            proc_flags = ep.get("processing_flags", "")
            last_run = ep.get("last_run", "")

            # Only show last_run if there are actual processing files
            has_processing = (
                num_transcripts > 0 or num_aligned > 0 or num_diarized > 0 or num_deepcasts > 0
            )
            last_run_display = last_run if (has_processing and last_run) else "-"

            table.add_row(
                Text(ep.get("show", "Unknown"), style="magenta"),
                Text(ep.get("date", "Unknown"), style="green"),
                Text(self._truncate(ep.get("title", "Unknown"), 48), style="white"),
                Text(asr_val, style="cyan"),
                Text(aln_val, style="yellow"),
                Text(diar_val, style="blue"),
                Text(deep_val, style="red"),
                Text(proc_flags or "-", style="bright_magenta"),
                Text(last_run_display, style="white"),
            )

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.exit((None, None))


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
    from .episode_selector import scan_episode_status

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
    episodes_sorted = sorted(episodes, key=lambda x: (x["date"], x["show"]), reverse=True)

    # Run the TUI
    app = EpisodeBrowserTUI(episodes_sorted, scan_dir)
    result = app.run()

    if result == (None, None):
        raise SystemExit(0)

    return result


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
                # Automatically trigger search
                modal.search_and_load(self.show_name)

            result = await self.push_screen_wait(modal)
            if result:
                # Episode was fetched
                _, meta = result
                self.result = meta
                self.exit(meta)
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

    def __init__(self, items: List[Dict[str, Any]], model_key: str = "asr_model", status_key: str = "is_aligned"):
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
        table.add_column("Show", key="show", width=20)
        table.add_column("Date", key="date", width=10)
        table.add_column("Title", key="title")

        # Add rows
        for idx, item in enumerate(self.items):
            model_name = item.get(self.model_key, "unknown")
            is_complete = item.get(self.status_key, False)

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
                    Text(show, style="green"),
                    Text(date, style="blue"),
                    Text(title, style="white"),
                    key=str(idx),
                )
            else:
                table.add_row(
                    Text(model_name, style="magenta"),
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

    def __init__(self, episodes: List[Dict[str, Any]]):
        super().__init__()
        self.episodes = episodes
        self.selected_episode = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False, icon="")
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
                    self.exit(self.selected_episode)

    def action_quit_app(self) -> None:
        """Quit without selection."""
        self.exit(None)


def select_episode_for_processing(
    scan_dir: Path,
    title: str = "Select Episode for Processing",
    show_filter: Optional[str] = None,
    episode_scanner: Optional[callable] = None,
) -> Optional[Dict[str, Any]]:
    """Select an episode for processing using the Textual TUI.

    Args:
        scan_dir: Directory to scan for episodes
        title: Window title for the browser
        show_filter: Optional show name filter
        episode_scanner: Optional custom scanner function (default: scan_episode_status)

    Returns:
        Selected episode dictionary, or None if cancelled

    Raises:
        SystemExit: If no episodes found
    """
    import json

    from dateutil import parser as dtparse

    from .episode_selector import scan_episode_status

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

    app = CustomProcessingBrowser(episodes_sorted)
    result = app.run()

    if result is None:
        raise SystemExit(0)

    return result
