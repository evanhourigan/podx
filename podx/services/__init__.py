"""Service layer for podx pipeline orchestration.

This package contains business logic extracted from orchestrate.py to improve
testability, maintainability, and enable alternative interfaces (API, library).

The service layer provides:
- **CommandBuilder**: Fluent API for building CLI commands
- **StepExecutor**: Low-level command execution with JSON I/O
- **PipelineService**: High-level pipeline orchestration
- **AsyncStepExecutor**: Async command execution for concurrent operations
- **AsyncPipelineService**: Async pipeline with concurrent step execution
- **Step Executors**: Focused, single-responsibility pipeline steps (Strategy pattern)

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

    # Direct step executor usage (new in Phase 6)
    >>> from podx.services.steps import FetchStep, StepContext
    >>> context = StepContext(config={"show": "My Podcast"}, working_dir=Path("."))
    >>> step = FetchStep()
    >>> result = step.execute(context, progress, verbose=True)
"""

from ..domain import PipelineConfig, PipelineResult
from .async_pipeline_service import AsyncPipelineService
from .async_step_executor import AsyncStepExecutor
from .command_builder import CommandBuilder
from .pipeline_service import PipelineService
from .step_executor import StepExecutor

# New focused step executors (Phase 6)
from .steps import (
    CleanupStep,
    DeepcastStep,
    EnhancementStep,
    ExportStep,
    FetchStep,
    NotionStep,
    PipelineStep,
    StepContext,
    StepResult,
    TranscribeStep,
)

__all__ = [
    # Legacy services
    "AsyncPipelineService",
    "AsyncStepExecutor",
    "CommandBuilder",
    "PipelineConfig",
    "PipelineResult",
    "PipelineService",
    "StepExecutor",
    # Step executors (Phase 6)
    "PipelineStep",
    "StepContext",
    "StepResult",
    "FetchStep",
    "TranscribeStep",
    "EnhancementStep",
    "DeepcastStep",
    "ExportStep",
    "NotionStep",
    "CleanupStep",
]
