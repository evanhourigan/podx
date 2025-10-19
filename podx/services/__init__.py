"""Service layer for podx pipeline orchestration.

This package contains business logic extracted from orchestrate.py to improve
testability, maintainability, and enable alternative interfaces (API, library).
"""

from .command_builder import CommandBuilder

__all__ = [
    "CommandBuilder",
]
