"""Command modules for the podx CLI."""

# Import all command functions
from .analyze import analyze_cmd, deepcast_cmd  # deepcast_cmd is backwards compat alias
from .ask import ask_cmd
from .backfill import backfill_cmd
from .clean import clean_cmd
from .cleanup import cleanup_cmd
from .deprecated import register_deprecated_commands
from .diarize import diarize_cmd
from .export import export_cmd
from .fetch import fetch_cmd
from .models import models_cmd
from .notion import notion_cmd
from .run import run
from .server import server
from .speakers import speakers_cmd
from .transcribe import transcribe_cmd

__all__ = [
    # Core pipeline commands
    "fetch_cmd",
    "transcribe_cmd",
    "diarize_cmd",
    "cleanup_cmd",
    "export_cmd",
    "analyze_cmd",
    "deepcast_cmd",  # Backwards compatibility alias for analyze_cmd
    "models_cmd",
    "notion_cmd",
    "speakers_cmd",
    "backfill_cmd",
    "clean_cmd",
    "ask_cmd",
    # Main orchestration command
    "run",
    # Server
    "server",
    # Registration functions
    "register_deprecated_commands",
]
