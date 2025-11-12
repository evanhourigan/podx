"""Standalone fetch browser for interactive podcast episode fetching."""

from pathlib import Path
from typing import Any, Dict, Optional

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static

from ..modals.fetch_modal import FetchModal


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
