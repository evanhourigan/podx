"""Interactive episode browser using Textual with cursor navigation and detail panel."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static


class FetchModal(ModalScreen[Optional[Tuple[Dict[str, Any], Dict[str, Any]]]]):
    """Modal screen for fetching episodes from RSS feeds."""

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
        height: 30%;
        border: solid $accent;
        padding: 1;
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
        Binding("enter", "fetch_selected", "Fetch", show=True),
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
        show_name = event.value.strip()
        if not show_name:
            return

        self.show_name = show_name
        status = self.query_one("#status-message", Static)
        status.update(f"🔍 Searching for '{show_name}'...")

        # Run the search asynchronously
        self.search_and_load(show_name)

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

            # Parse RSS feed
            import feedparser

            feed = feedparser.parse(feed_url)

            if not feed.entries:
                self.app.call_from_thread(self._show_error, "No episodes found in RSS feed")
                return

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

                episode = {
                    "title": entry.title,
                    "published": entry.published if hasattr(entry, "published") else "Unknown",
                    "description": entry.summary if hasattr(entry, "summary") else "",
                    "audio_url": audio_url,
                    "duration": duration,
                    "link": entry.link if hasattr(entry, "link") else "",
                    "feed_url": feed_url,
                }

                episodes.append(episode)

            self.rss_episodes = episodes
            self.app.call_from_thread(self._populate_table)

        except Exception as e:
            self.app.call_from_thread(self._show_error, f"Error loading episodes: {str(e)}")

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
            from ..fetch import fetch_episode

            # Prepare episode info
            episode_info = {
                "title": episode.get("title", "Unknown"),
                "published": episode.get("published", "Unknown"),
                "audio_url": episode.get("audio_url"),
                "feed_url": episode.get("feed_url"),
            }

            # Fetch the episode
            result = fetch_episode(
                show_name=self.show_name or "Unknown",
                rss_url=self.feed_url or "",
                episode_info=episode_info,
                output_dir=str(self.scan_dir),
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
        Binding("q", "quit_app", "Quit", show=True),
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
        yield Header()
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
                # Episode was fetched, add it to the list and select it
                episode, meta = result
                self.episodes.insert(0, episode)  # Add to beginning
                self._refresh_table()
                # Select the newly added episode (now at index 0)
                table = self.query_one("#episode-table", DataTable)
                table.move_cursor(row=0)
                # Update detail panel after a short delay to ensure screen is ready
                self.call_later(lambda: self._update_detail_panel(0))

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
