"""Browser for model-level processing commands (align, diarize, preprocess)."""

from typing import Any, Dict, List

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Static


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
        height: 10;
        border: solid $accent;
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

        table.add_column(Text("ASR Model", style="bold cyan"), key="model", width=16)
        table.add_column(Text("Stage", style="bold yellow"), key="stage", width=13)
        table.add_column(Text("Show", style="bold magenta"), key="show", width=20)
        table.add_column(Text("Date", style="bold green"), key="date", width=10)
        table.add_column(Text("Title", style="bold white"), key="title")

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
