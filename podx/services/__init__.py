"""Service layer for podx pipeline orchestration.

This package contains business logic extracted from orchestrate.py to improve
testability, maintainability, and enable alternative interfaces (API, library).

The service layer provides:
- **CommandBuilder**: Fluent API for building CLI commands
- **StepExecutor**: Low-level command execution with JSON I/O
- **PipelineService**: High-level pipeline orchestration
- **AsyncStepExecutor**: Async command execution for concurrent operations
- **AsyncPipelineService**: Async pipeline with concurrent step execution

Usage Examples:
    # Synchronous API
    >>> from podx.services import CommandBuilder
    >>> cmd = CommandBuilder("podx-transcribe").add_option("--model", "large-v3").build()

    >>> from podx.services import StepExecutor
    >>> executor = StepExecutor(verbose=True)
    >>> result = executor.fetch(show="My Podcast")

    >>> from podx.services import PipelineService, PipelineConfig
    >>> config = PipelineConfig(show="My Podcast", align=True, deepcast=True)
    >>> service = PipelineService(config)
    >>> result = service.execute()

    # Asynchronous API
    >>> from podx.services import AsyncPipelineService, PipelineConfig
    >>> config = PipelineConfig(show="My Podcast", deepcast=True)
    >>> service = AsyncPipelineService(config)
    >>> result = await service.execute()

    # Batch processing with concurrency control
    >>> configs = [PipelineConfig(show=f"Podcast {i}") for i in range(10)]
    >>> results = await AsyncPipelineService.process_batch(configs, max_concurrent=3)
"""

from .async_pipeline_service import AsyncPipelineService
from .async_step_executor import AsyncStepExecutor
from .command_builder import CommandBuilder
from .pipeline_service import PipelineConfig, PipelineResult, PipelineService
from .step_executor import StepExecutor

__all__ = [
    "AsyncPipelineService",
    "AsyncStepExecutor",
    "CommandBuilder",
    "PipelineConfig",
    "PipelineResult",
    "PipelineService",
    "StepExecutor",
]
