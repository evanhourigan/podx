"""Standardized exit codes for PodX CLI commands.

Following POSIX conventions and common CLI practices.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes for PodX CLI commands."""

    SUCCESS = 0
    """Command completed successfully."""

    USER_ERROR = 1
    """User error: invalid arguments, file not found, invalid input."""

    SYSTEM_ERROR = 2
    """System error: network failure, disk full, permission denied."""

    PROCESSING_ERROR = 3
    """Processing error: transcription failed, diarization error, API failure."""

    INTERRUPTED = 130
    """User interrupted with SIGINT (Ctrl+C)."""


def exit_with_code(code: ExitCode) -> None:
    """Exit with the specified exit code.

    Args:
        code: The exit code to use.
    """
    import sys

    sys.exit(code)
