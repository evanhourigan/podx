#!/usr/bin/env python3
"""
Structured logging configuration for podx.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, Processor

from .config import get_config


def add_log_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add log level to event dict."""
    if method_name == "info":
        event_dict["level"] = "INFO"
    elif method_name == "debug":
        event_dict["level"] = "DEBUG"
    elif method_name == "warning":
        event_dict["level"] = "WARNING"
    elif method_name == "error":
        event_dict["level"] = "ERROR"
    elif method_name == "critical":
        event_dict["level"] = "CRITICAL"
    return event_dict


def setup_logging() -> None:
    """Configure structured logging based on configuration."""
    config = get_config()

    # Configure stdlib logging - use stderr to avoid interfering with JSON stdout
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, config.log_level),
    )

    # Configure processors based on format
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if config.log_format == "json":
        processors.extend(
            [
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ]
        )
    else:
        # Console format
        processors.extend(
            [
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "podx") -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


def suppress_logging() -> None:
    """Suppress all logging output (for TUI mode).

    Call this before entering TUI/interactive mode to prevent log messages
    from corrupting the TUI display.
    """
    # Disable all stdlib logging handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(logging.NullHandler())
    root_logger.setLevel(logging.CRITICAL + 1)  # Above CRITICAL

    # Disable structlog output
    logging.disable(logging.CRITICAL)


def restore_logging() -> None:
    """Restore normal logging output after TUI mode exits."""
    # Re-enable logging
    logging.disable(logging.NOTSET)

    # Re-run setup to restore handlers
    setup_logging()
