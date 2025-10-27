"""Core business logic modules for PodX.

This package contains pure processing logic with no UI or CLI dependencies.
Each module can be tested independently and used by different interfaces
(CLI, TUI studio, web API, etc.).

Architecture principles:
- No imports from ui/ or cli/
- No Click decorators or CLI concerns
- Use callbacks for progress reporting
- Return typed data models
- Testable without mocking
"""

__all__ = [
    "transcode",
    "fetch",
    "preprocess",
    "transcribe",
    "diarize",
    "deepcast",
]
