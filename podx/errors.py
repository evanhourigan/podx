#!/usr/bin/env python3
"""
Error handling and retry utilities for podx.
"""

import logging
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import get_config
from .logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class PodxError(Exception):
    """Base exception for podx-specific errors."""

    pass


class ValidationError(PodxError):
    """Raised when data validation fails."""

    pass


class NetworkError(PodxError):
    """Raised when network operations fail."""

    pass


class AudioError(PodxError):
    """Raised when audio processing fails."""

    pass


class AIError(PodxError):
    """Raised when AI/LLM operations fail."""

    pass


def with_retries(
    stop_after: Optional[int] = None,
    wait_multiplier: float = 1.0,
    wait_min: float = 4.0,
    wait_max: float = 10.0,
    retry_on: Tuple[Type[Exception], ...] = (
        requests.exceptions.RequestException,
        NetworkError,
    ),
) -> Callable[[F], F]:
    """
    Decorator to add retry logic to functions.

    Args:
        stop_after: Maximum number of attempts (defaults to config)
        wait_multiplier: Exponential backoff multiplier
        wait_min: Minimum wait time between retries
        wait_max: Maximum wait time between retries
        retry_on: Exception types to retry on
    """
    config = get_config()
    if stop_after is None:
        stop_after = config.max_retries

    def decorator(func: F) -> F:
        @retry(
            stop=stop_after_attempt(stop_after),
            wait=wait_exponential(multiplier=wait_multiplier, min=wait_min, max=wait_max),
            retry=retry_if_exception_type(retry_on),
            before_sleep=before_sleep_log(logger, logging.WARNING),  # type: ignore[arg-type]
        )
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if isinstance(e, retry_on):
                    logger.warning("Retryable error occurred", error=str(e), function=func.__name__)
                    raise NetworkError(f"Network operation failed: {e}") from e
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def validate_file_exists(path: Union[str, Path], description: str = "File") -> Path:
    """
    Validate that a file exists and return Path object.

    Args:
        path: File path to validate
        description: Human-readable description for error messages

    Returns:
        Path object if file exists

    Raises:
        ValidationError: If file doesn't exist
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise ValidationError(f"{description} not found: {path}")
    if not path_obj.is_file():
        raise ValidationError(f"{description} is not a file: {path}")
    return path_obj


def validate_directory_exists(path: Union[str, Path], create: bool = False) -> Path:
    """
    Validate that a directory exists, optionally creating it.

    Args:
        path: Directory path to validate
        create: Whether to create the directory if it doesn't exist

    Returns:
        Path object if directory exists

    Raises:
        ValidationError: If directory doesn't exist and create=False
    """
    path_obj = Path(path)
    if not path_obj.exists():
        if create:
            path_obj.mkdir(parents=True, exist_ok=True)
            logger.debug("Created directory", path=str(path_obj))
        else:
            raise ValidationError(f"Directory not found: {path}")
    elif not path_obj.is_dir():
        raise ValidationError(f"Path is not a directory: {path}")
    return path_obj
