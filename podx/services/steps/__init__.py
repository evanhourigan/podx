"""Pipeline step executors using Strategy pattern.

Each step executor implements the PipelineStep protocol, enabling:
- Single Responsibility: Each step has one job
- Open/Closed: Easy to add new steps without modifying existing ones
- Testability: Each step can be tested in isolation
- Resumability: Steps can detect existing artifacts and skip execution
"""

from .base import PipelineStep, StepContext, StepResult
from .cleanup_step import CleanupStep
from .deepcast_step import DeepcastStep
from .enhancement_step import EnhancementStep
from .export_step import ExportStep
from .fetch_step import FetchStep
from .notion_step import NotionStep
from .transcribe_step import TranscribeStep

__all__ = [
    # Base
    "PipelineStep",
    "StepContext",
    "StepResult",
    # Steps
    "FetchStep",
    "TranscribeStep",
    "EnhancementStep",
    "DeepcastStep",
    "ExportStep",
    "NotionStep",
    "CleanupStep",
]
