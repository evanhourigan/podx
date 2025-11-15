"""Silent progress reporter for testing and background tasks."""

from typing import Optional

from .base import ProgressReporter


class SilentProgressReporter(ProgressReporter):
    """Progress reporter that does nothing.

    Useful for testing or when progress reporting is not desired.
    Implements the ProgressReporter interface but doesn't output anything.
    """

    def __init__(self, track_calls: bool = False):
        """Initialize silent progress reporter.

        Args:
            track_calls: If True, tracks all calls for testing assertions
        """
        self.track_calls = track_calls
        self.calls: list[tuple[str, str, dict]] = []  # (method, message, kwargs)

    def start_task(self, task_name: str, total_steps: Optional[int] = None) -> None:
        """Start a new task (no-op)."""
        if self.track_calls:
            self.calls.append(
                ("start_task", task_name, {"total_steps": total_steps})
            )

    def update_step(
        self,
        message: str,
        step: Optional[int] = None,
        progress: Optional[float] = None,
    ) -> None:
        """Update progress for current step (no-op)."""
        if self.track_calls:
            self.calls.append(
                ("update_step", message, {"step": step, "progress": progress})
            )

    def complete_step(self, message: str, duration: Optional[float] = None) -> None:
        """Mark current step as complete (no-op)."""
        if self.track_calls:
            self.calls.append(("complete_step", message, {"duration": duration}))

    def fail_step(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark current step as failed (no-op)."""
        if self.track_calls:
            self.calls.append(("fail_step", message, {"error": error}))

    def complete_task(self, message: str, duration: Optional[float] = None) -> None:
        """Mark entire task as complete (no-op)."""
        if self.track_calls:
            self.calls.append(("complete_task", message, {"duration": duration}))

    def fail_task(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark entire task as failed (no-op)."""
        if self.track_calls:
            self.calls.append(("fail_task", message, {"error": error}))

    def reset(self) -> None:
        """Reset call tracking.

        Useful when reusing reporter across multiple tests.
        """
        self.calls = []
