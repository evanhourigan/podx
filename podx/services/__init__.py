"""Service layer for podx pipeline orchestration.

This package contains business logic extracted from orchestrate.py to improve
testability, maintainability, and enable alternative interfaces (API, library).

The service layer provides:
- **CommandBuilder**: Fluent API for building CLI commands
- **StepExecutor**: Low-level command execution with JSON I/O
- **PipelineService**: High-level pipeline orchestration

Usage Examples:
    # Using CommandBuilder directly
    >>> from podx.services import CommandBuilder
    >>> cmd = CommandBuilder("podx-transcribe").add_option("--model", "large-v3").build()

    # Using StepExecutor for individual steps
    >>> from podx.services import StepExecutor
    >>> executor = StepExecutor(verbose=True)
    >>> result = executor.fetch(show="My Podcast")

    # Using PipelineService for full pipeline
    >>> from podx.services import PipelineService, PipelineConfig
    >>> config = PipelineConfig(show="My Podcast", align=True, deepcast=True)
    >>> service = PipelineService(config)
    >>> result = service.execute()
"""

from .command_builder import CommandBuilder
from .pipeline_service import PipelineConfig, PipelineResult, PipelineService
from .step_executor import StepExecutor

__all__ = [
    "CommandBuilder",
    "PipelineConfig",
    "PipelineResult",
    "PipelineService",
    "StepExecutor",
]
