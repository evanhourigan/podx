"""API-based progress reporter for web applications.

This reporter stores progress updates in a queue that can be consumed
by web API endpoints for real-time progress streaming via SSE or WebSocket.
"""

import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Deque, Optional

from .base import ProgressReporter


@dataclass
class ProgressEvent:
    """A progress event for API consumption.

    Attributes:
        timestamp: Event timestamp (seconds since epoch)
        event_type: Type of event (task_start, step_update, step_complete, etc.)
        message: Progress message
        task_name: Optional task name
        step: Optional current step number
        total_steps: Optional total steps
        progress: Optional progress percentage (0.0-1.0)
        duration: Optional duration in seconds
        error: Optional error message
    """

    timestamp: float
    event_type: str
    message: str
    task_name: Optional[str] = None
    step: Optional[int] = None
    total_steps: Optional[int] = None
    progress: Optional[float] = None
    duration: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class APIProgressReporter(ProgressReporter):
    """Progress reporter that stores events in a queue for API consumption.

    Events can be consumed by web API endpoints for streaming to clients
    via Server-Sent Events (SSE) or WebSocket.

    Example:
        >>> progress = APIProgressReporter(maxlen=100)
        >>> progress.start_task("Processing", total_steps=3)
        >>> progress.update_step("Step 1", step=1)
        >>> progress.complete_task("Done!")
        >>>
        >>> # Consume events
        >>> for event in progress.get_events():
        ...     print(event.to_dict())
    """

    def __init__(self, maxlen: int = 1000):
        """Initialize API progress reporter.

        Args:
            maxlen: Maximum number of events to store (older events are dropped)
        """
        self.events: Deque[ProgressEvent] = deque(maxlen=maxlen)
        self.current_task: Optional[str] = None
        self.current_step: int = 0
        self.total_steps: Optional[int] = None

    def _add_event(
        self,
        event_type: str,
        message: str,
        step: Optional[int] = None,
        progress: Optional[float] = None,
        duration: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Add an event to the queue."""
        event = ProgressEvent(
            timestamp=time.time(),
            event_type=event_type,
            message=message,
            task_name=self.current_task,
            step=step,
            total_steps=self.total_steps,
            progress=progress,
            duration=duration,
            error=error,
        )
        self.events.append(event)

    def start_task(self, task_name: str, total_steps: Optional[int] = None) -> None:
        """Start a new task."""
        self.current_task = task_name
        self.current_step = 0
        self.total_steps = total_steps
        self._add_event("task_start", f"Started: {task_name}")

    def update_step(
        self,
        message: str,
        step: Optional[int] = None,
        progress: Optional[float] = None,
    ) -> None:
        """Update progress for current step."""
        if step is not None:
            self.current_step = step
        self._add_event("step_update", message, step=step, progress=progress)

    def complete_step(self, message: str, duration: Optional[float] = None) -> None:
        """Mark current step as complete."""
        self._add_event("step_complete", message, duration=duration)

    def fail_step(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark current step as failed."""
        error_msg = str(error) if error else None
        self._add_event("step_fail", message, error=error_msg)

    def complete_task(self, message: str, duration: Optional[float] = None) -> None:
        """Mark entire task as complete."""
        self._add_event("task_complete", message, duration=duration)

    def fail_task(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark entire task as failed."""
        error_msg = str(error) if error else None
        self._add_event("task_fail", message, error=error_msg)

    def get_events(self, since: Optional[float] = None) -> list[ProgressEvent]:
        """Get all events, optionally filtered by timestamp.

        Args:
            since: Optional timestamp - only return events after this time

        Returns:
            List of progress events
        """
        if since is None:
            return list(self.events)
        return [e for e in self.events if e.timestamp > since]

    def clear_events(self) -> None:
        """Clear all stored events."""
        self.events.clear()

    def get_latest_event(self) -> Optional[ProgressEvent]:
        """Get the most recent event.

        Returns:
            Latest progress event or None if no events
        """
        return self.events[-1] if self.events else None
