"""Simplified episode browser for processing commands (transcode, transcribe, etc)."""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dateutil import parser as dtparse
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Static


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
            from ..transcribe_tui import ASRModelModal

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
    episode_scanner: Optional[Callable] = None,
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
    from ..logging import restore_logging, suppress_logging
    from ..episode_selector import scan_episode_status

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
