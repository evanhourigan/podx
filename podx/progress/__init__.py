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

# Import legacy functions from old progress.py (TODO: migrate these)
import importlib.util
import os
_legacy_path = os.path.join(os.path.dirname(__file__), "..", "progress.py")
_spec = importlib.util.spec_from_file_location("legacy_progress", _legacy_path)
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
print_podx_header = _legacy.print_podx_header
PodxProgress = _legacy.PodxProgress

__all__ = [
    # Base
    "ProgressReporter",
    "ProgressStep",
    "ProgressEvent",
    # Implementations
    "ConsoleProgressReporter",
    "APIProgressReporter",
    "SilentProgressReporter",
    # Legacy (from progress.py)
    "print_podx_header",
    "PodxProgress",
]
