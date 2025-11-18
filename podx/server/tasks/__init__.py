"""Background tasks for PodX server.

This package contains background tasks that run alongside the main application,
such as file cleanup and maintenance operations.
"""

from podx.server.tasks.cleanup import run_cleanup_task

__all__ = ["run_cleanup_task"]
