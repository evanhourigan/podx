"""Interactive episode browser using Textual with cursor navigation and detail panel."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Static

from .modals.fetch_modal import FetchModal


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
