"""Base class for interactive browser UIs with pagination."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

try:
    import rich  # noqa: F401

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..ui_styles import make_console


class InteractiveBrowser(ABC):
    """Abstract base class for interactive browsers with pagination.

    Provides standard navigation (N/P/Q/number), pagination, and selection
    confirmation. Subclasses must implement display_page() to render their
    specific table layout.

    Usage:
        class MyBrowser(InteractiveBrowser):
            def display_page(self) -> None:
                # Create and print table with items[start:end]
                pass

            def _get_item_title(self, item: Dict[str, Any]) -> str:
                return item.get("title", "Unknown")

        browser = MyBrowser(items, items_per_page=10)
        selected = browser.browse()
    """

    def __init__(
        self,
        items: List[Dict[str, Any]],
        items_per_page: int = 10,
        item_name: str = "item",
    ):
        """Initialize browser with items and pagination settings.

        Args:
            items: List of items to browse
            items_per_page: Number of items per page
            item_name: Name of items for messages (e.g., "episode", "transcript")
        """
        self.items = items
        self.items_per_page = items_per_page
        self.item_name = item_name
        self.console = make_console() if RICH_AVAILABLE else None
        self.current_page = 0
        self.total_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)

    @abstractmethod
    def display_page(self) -> None:
        """Display current page with table and navigation options.

        This method must be implemented by subclasses to render their
        specific table layout. The page items are available via:

            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.items))
            page_items = self.items[start_idx:end_idx]

        Must handle the case where self.console is None (RICH not available).
        """
        pass

    def _get_item_title(self, item: Dict[str, Any]) -> str:
        """Get title/name of item for selection confirmation.

        Override this method to customize the title extraction logic.

        Args:
            item: The selected item

        Returns:
            Title string to display in confirmation message
        """
        return item.get("title", "Unknown")

    def get_user_input(self) -> Optional[Dict[str, Any]]:
        """Get user input and return selected item or None.

        Returns:
            - Dict: Selected item (non-empty dict)
            - {}: Empty dict signals page change (continue browsing)
            - None: User quit (Q/quit/exit)
        """
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

                # Item selection
                try:
                    selection = int(user_input)
                    if 1 <= selection <= len(self.items):
                        selected_item = self.items[selection - 1]
                        if self.console:
                            title = self._get_item_title(selected_item)
                            self.console.print(f"✅ Selected: [green]{title}[/green]")
                        return selected_item
                    else:
                        if self.console:
                            self.console.print(
                                f"[red]❌ Invalid choice. Please select 1-{len(self.items)}[/red]"
                            )
                except ValueError:
                    pass

                # Invalid input
                if self.console:
                    self.console.print(
                        "[red]❌ Invalid input. Please enter a number.[/red]"
                    )

            except (KeyboardInterrupt, EOFError):
                if self.console:
                    self.console.print("\n👋 Goodbye!")
                return None

    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop. Returns selected item or None.

        Returns:
            - Dict: The selected item
            - None: User quit without selecting
        """
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

            # Non-empty dict means item selected
            return result
