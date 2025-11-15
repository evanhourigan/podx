"""Base classes and interfaces for progress reporting."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ProgressStep:
    """A single step in a multi-step task.

    Attributes:
        name: Step name/description
        status: Step status (pending, running, completed, failed)
        progress: Optional progress percentage (0.0-1.0)
        message: Optional status message
        metadata: Optional metadata dict
    """

    name: str
    status: str = "pending"  # pending, running, completed, failed
    progress: Optional[float] = None  # 0.0 to 1.0
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProgressReporter(ABC):
    """Abstract base class for progress reporting.

    Provides a unified interface for reporting progress across different
    execution contexts (CLI, TUI, web API).
    """

    @abstractmethod
    def start_task(self, task_name: str, total_steps: Optional[int] = None) -> None:
        """Start a new task.

        Args:
            task_name: Name/description of the task
            total_steps: Optional total number of steps (for progress bar)
        """
        pass

    @abstractmethod
    def update_step(
        self,
        message: str,
        step: Optional[int] = None,
        progress: Optional[float] = None,
    ) -> None:
        """Update progress for current step.

        Args:
            message: Progress message
            step: Optional step number (if total_steps was provided)
            progress: Optional progress percentage (0.0-1.0)
        """
        pass

    @abstractmethod
    def complete_step(self, message: str, duration: Optional[float] = None) -> None:
        """Mark current step as complete.

        Args:
            message: Completion message
            duration: Optional duration in seconds
        """
        pass

    @abstractmethod
    def fail_step(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark current step as failed.

        Args:
            message: Failure message
            error: Optional exception that caused failure
        """
        pass

    @abstractmethod
    def complete_task(self, message: str, duration: Optional[float] = None) -> None:
        """Mark entire task as complete.

        Args:
            message: Completion message
            duration: Optional total duration in seconds
        """
        pass

    @abstractmethod
    def fail_task(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark entire task as failed.

        Args:
            message: Failure message
            error: Optional exception that caused failure
        """
        pass

    # Convenience methods for common patterns

    def report(self, message: str) -> None:
        """Report a simple progress message (convenience method).

        Args:
            message: Progress message

        Note:
            This is equivalent to update_step(message) but more concise.
            Use for simple progress updates without step tracking.
        """
        self.update_step(message)

    def log(self, message: str, level: str = "info") -> None:
        """Log a message without affecting progress tracking.

        Args:
            message: Log message
            level: Log level (info, warning, error, debug)

        Note:
            Default implementation calls update_step, but implementations
            can override to handle logging separately.
        """
        self.update_step(f"[{level.upper()}] {message}")
