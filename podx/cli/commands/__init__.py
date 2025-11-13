"""Command modules for the podx CLI."""

# Import all command functions
from .config import config_command, register_config_group
from .deepcast import deepcast_cmd
from .deprecated import register_deprecated_commands
from .diarize import diarize_cmd
from .export import export_cmd
from .fetch import fetch_cmd
from .models import models_cmd
from .notion import notion_cmd
from .preprocess import preprocess_shim
from .run import run
from .transcribe import transcribe_cmd
from .transcode import transcode_cmd

__all__ = [
    # Simple passthrough commands
    "fetch_cmd",
    "transcode_cmd",
    "transcribe_cmd",
    "diarize_cmd",
    "export_cmd",
    "deepcast_cmd",
    "models_cmd",
    "notion_cmd",
    "preprocess_shim",
    # Utility commands
    "config_command",
    # Main orchestration command
    "run",
    # Registration functions for complex commands
    "register_deprecated_commands",
    "register_config_group",
]
