"""Base protocol and types for pipeline step executors.

Following the Strategy pattern, each pipeline step implements the PipelineStep
protocol, enabling consistent execution, testing, and composition.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class StepContext:
    """Shared context passed between pipeline steps.

    Contains configuration, paths, and accumulated results from previous steps.
    """

    # Configuration
    config: Dict[str, Any]

    # Paths
    working_dir: Path

    # Accumulated results
    metadata: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)

    # Latest transcript tracking
    latest_transcript: Optional[Dict[str, Any]] = None
    latest_transcript_name: Optional[str] = None

    # Audio tracking
    audio_metadata: Optional[Dict[str, Any]] = None
    transcoded_audio_path: Optional[Path] = None
    original_audio_path: Optional[Path] = None


@dataclass
class StepResult:
    """Result of a pipeline step execution.

    Provides type-safe success/failure handling with optional data payload.
    """

    success: bool
    message: str
    duration: float = 0.0
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def ok(
        cls, message: str, duration: float = 0.0, data: Optional[Dict[str, Any]] = None
    ) -> "StepResult":
        """Create a successful result."""
        return cls(success=True, message=message, duration=duration, data=data)

    @classmethod
    def fail(cls, message: str, error: str, duration: float = 0.0) -> "StepResult":
        """Create a failed result."""
        return cls(success=False, message=message, duration=duration, error=error)

    @classmethod
    def skip(cls, message: str) -> "StepResult":
        """Create a skipped result (treated as success with 0 duration)."""
        return cls(success=True, message=message, duration=0.0)


class PipelineStep(ABC):
    """Abstract base class for pipeline step executors.

    Each step is responsible for:
    1. Executing a specific pipeline operation
    2. Updating the shared context with results
    3. Reporting progress via the progress tracker
    4. Supporting resume/skip logic when artifacts exist
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get human-readable step name for display."""
        pass

    @abstractmethod
    def execute(self, context: StepContext, progress: Any, verbose: bool = False) -> StepResult:
        """Execute this pipeline step.

        Args:
            context: Shared pipeline context (modified in place)
            progress: Progress tracker for UI updates
            verbose: Enable verbose logging

        Returns:
            StepResult indicating success/failure and any data produced
        """
        pass

    def should_skip(self, context: StepContext) -> tuple[bool, Optional[str]]:
        """Check if this step should be skipped (resume support).

        Args:
            context: Current pipeline context

        Returns:
            Tuple of (should_skip, skip_reason)
        """
        return False, None
