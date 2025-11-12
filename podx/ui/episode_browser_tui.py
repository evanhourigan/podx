"""Interactive episode browser using Textual with cursor navigation and detail panel."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .apps import EpisodeBrowserTUI
from .apps.simple_processing import select_episode_for_processing

# Re-export for backwards compatibility
__all__ = [
    "EpisodeBrowserTUI",
    "select_episode_with_config",
    "select_episode_with_tui",
    "select_episode_for_processing",
]


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
