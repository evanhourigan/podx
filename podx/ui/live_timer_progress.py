"""Progress reporter that displays status in a LiveTimer."""

from typing import Optional

from ..progress.base import ProgressReporter
from .live_timer import LiveTimer


class LiveTimerProgressReporter(ProgressReporter):
    """Progress reporter that updates a LiveTimer with status messages.

    Wraps a LiveTimer instance to display real-time progress updates
    during long-running operations like cloud transcription.

    Example:
        >>> timer = LiveTimer("Transcribing")
        >>> progress = LiveTimerProgressReporter(timer)
        >>> timer.start()
        >>> # Pass progress to TranscriptionEngine
        >>> engine = TranscriptionEngine(model="runpod:large-v3", progress=progress)
        >>> result = engine.transcribe(audio_path)
        >>> timer.stop()
    """

    def __init__(self, timer: LiveTimer):
        """Initialize with a LiveTimer instance.

        Args:
            timer: LiveTimer to update with progress messages
        """
        self.timer = timer
        self._current_task: Optional[str] = None

    def start_task(self, task_name: str, total_steps: Optional[int] = None) -> None:
        """Start a new task.

        Args:
            task_name: Name/description of the task
            total_steps: Optional total number of steps (ignored for timer display)
        """
        self._current_task = task_name
        self.timer.update_message(task_name)

    def update_step(
        self,
        message: str,
        step: Optional[int] = None,
        progress: Optional[float] = None,
    ) -> None:
        """Update progress with a new step.

        Args:
            message: Progress message to display
            step: Optional current step number (ignored)
            progress: Optional progress percentage (ignored for timer display)
        """
        # Cloud polling messages contain '...' with elapsed time — show as substatus
        if "..." in message and "(" in message:
            activity = message.split("...")[0].strip() + "..."
            self.timer.update_message(activity)
            self.timer.update_substatus(message)
        else:
            self.timer.update_message(message)
            self.timer.update_substatus(None)

    def report(self, message: str) -> None:
        """Simple string callback for cloud progress with substatus support.

        Splits messages with '...' into activity + substatus detail.
        """
        if "..." in message:
            activity = message.split("...")[0].strip() + "..."
            self.timer.update_message(activity)
            self.timer.update_substatus(message)
        else:
            self.timer.update_message(message)
            self.timer.update_substatus(None)

    def complete_step(self, message: str, duration: Optional[float] = None) -> None:
        """Mark current step as complete.

        Args:
            message: Completion message
            duration: Optional duration in seconds (ignored)
        """
        self.timer.update_message(message)

    def fail_step(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark current step as failed.

        Args:
            message: Failure message
            error: Optional exception (ignored)
        """
        self.timer.update_message(f"Failed: {message}")

    def complete_task(self, message: str, duration: Optional[float] = None) -> None:
        """Mark task as complete.

        Args:
            message: Completion message (ignored, timer handles this)
            duration: Optional duration in seconds (ignored)
        """
        # Timer's stop() method handles completion display
        pass

    def fail_task(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark task as failed.

        Args:
            message: Error message (displayed briefly before timer stops)
            error: Optional exception (ignored)
        """
        self.timer.update_message(f"Error: {message}")
