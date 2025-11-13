"""Reusable Textual widget for browsing and selecting items with pagination.

This widget replaces the old Rich-based InteractiveBrowser pattern with a proper
Textual TUI that provides keyboard navigation, pagination, and selection.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import DataTable, Footer, Header, Static


class SelectionBrowserApp(App[Optional[Dict[str, Any]]]):
    """Generic selection browser app with DataTable and pagination.

    This replaces the old InteractiveBrowser (Rich + input()) pattern with proper
    Textual TUI. Provides keyboard navigation, pagination, and selection.

    Usage:
        columns = [("Title", "title", 40), ("Date", "date", 12)]
        items = [{"title": "Item 1", "date": "2024-01-01"}, ...]

        app = SelectionBrowserApp(
            items=items,
            columns=columns,
            title="Select Item",
            item_name="item"
        )
        selected = app.run()
    """

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #main-container {
        width: 100%;
        height: 100%;
    }

    #browser-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding: 1;
        background: $panel;
    }

    #table-container {
        width: 100%;
        height: 1fr;
        border: solid $primary;
    }

    #info-bar {
        text-align: center;
        padding: 1;
        background: $panel;
        color: $text-muted;
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
        Binding("enter", "select", "Select", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(
        self,
        items: List[Dict[str, Any]],
        columns: List[Tuple[str, str, int]],
        title: str = "Select Item",
        item_name: str = "item",
        format_cell: Optional[Callable[[str, Any, Dict[str, Any]], Text]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize selection browser.

        Args:
            items: List of item dictionaries to display
            columns: List of (column_name, key, width) tuples defining table structure
            title: Browser window title
            item_name: Name of items for display (e.g., "episode", "transcript")
            format_cell: Optional function(column_key, value, item) -> Text for custom cell formatting
        """
        super().__init__(*args, **kwargs)
        self.items = items
        self.columns = columns
        self.browser_title = title
        self.item_name = item_name
        self.format_cell = format_cell or self._default_format_cell

    def _default_format_cell(
        self, column_key: str, value: Any, item: Dict[str, Any]
    ) -> Text:
        """Default cell formatter - just convert to string."""
        return Text(str(value) if value is not None else "", style="white")

    def compose(self) -> ComposeResult:
        """Compose the browser layout."""
        yield Header()
        with Vertical(id="main-container"):
            yield Static(self.browser_title, id="browser-title")
            with Container(id="table-container"):
                yield DataTable(
                    id="selection-table", cursor_type="row", zebra_stripes=True
                )
            yield Static(
                f"↑↓: Navigate • Enter: Select {self.item_name} • Esc: Cancel",
                id="info-bar",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table on mount."""
        table = self.query_one("#selection-table", DataTable)

        # Add columns with colored headers
        # Standard color mapping for common column names
        header_colors = {
            "Status": "bold cyan",
            "Show": "bold magenta",
            "Date": "bold green",
            "Title": "bold white",
            "ASR Model": "bold cyan",
            "Stage": "bold yellow",
        }

        for col_name, col_key, col_width in self.columns:
            # Use colored header if available, otherwise default to bold white
            header_style = header_colors.get(col_name, "bold white")
            header_text = Text(col_name, style=header_style)
            table.add_column(header_text, key=col_key, width=col_width)

        # Add rows
        for item in self.items:
            row_cells = []
            for col_name, col_key, col_width in self.columns:
                value = item.get(col_key)
                cell_text = self.format_cell(col_key, value, item)
                row_cells.append(cell_text)
            table.add_row(*row_cells)

        # Focus table
        table.focus()

    def action_select(self) -> None:
        """Select current item and exit."""
        table = self.query_one("#selection-table", DataTable)
        if table.cursor_row >= len(self.items):
            return

        selected_item = self.items[table.cursor_row]
        self.exit(selected_item)

    def action_cancel(self) -> None:
        """Cancel and exit with None."""
        self.exit(None)


def show_selection_browser(
    items: List[Dict[str, Any]],
    columns: List[Tuple[str, str, int]],
    title: str = "Select Item",
    item_name: str = "item",
    format_cell: Optional[Callable[[str, Any, Dict[str, Any]], Text]] = None,
) -> Optional[Dict[str, Any]]:
    """Show selection browser and return selected item.

    Convenience function that creates and runs SelectionBrowserApp.

    Args:
        items: List of item dictionaries to display
        columns: List of (column_name, key, width) tuples defining table structure
        title: Browser window title
        item_name: Name of items for display (e.g., "episode", "transcript")
        format_cell: Optional function(column_key, value, item) -> Text for custom cell formatting

    Returns:
        Selected item dict, or None if cancelled
    """
    app = SelectionBrowserApp(
        items=items,
        columns=columns,
        title=title,
        item_name=item_name,
        format_cell=format_cell,
    )
    return app.run()
