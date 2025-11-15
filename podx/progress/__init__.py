"""Progress reporting abstraction for CLI, TUI, and API contexts.

This module provides a unified interface for reporting progress across different
execution contexts (command-line, terminal UI, web API).

Usage:
    from podx.progress import ConsoleProgressReporter, SilentProgressReporter, APIProgressReporter

    # For CLI
    progress = ConsoleProgressReporter()
    progress.start_task("Processing", total_steps=5)
    progress.update_step("Step 1 complete", step=1)
    progress.complete_task("Done!")

    # For web API (with event streaming)
    progress = APIProgressReporter()
    progress.start_task("Processing")
    progress.update_step("Working...")
    events = progress.get_events()  # Get all events for SSE/WebSocket

    # For testing
    progress = SilentProgressReporter()
"""

from .api import APIProgressReporter, ProgressEvent
from .base import ProgressReporter, ProgressStep
from .console import ConsoleProgressReporter
from .silent import SilentProgressReporter

__all__ = [
    # Base
    "ProgressReporter",
    "ProgressStep",
    "ProgressEvent",
    # Implementations
    "ConsoleProgressReporter",
    "APIProgressReporter",
    "SilentProgressReporter",
]
