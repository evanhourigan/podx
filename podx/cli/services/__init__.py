"""Services for CLI orchestration and command execution.

This package provides utilities for building and executing pipeline commands,
managing configuration, and coordinating multi-step workflows.
"""

from podx.services.command_builder import CommandBuilder

from .command_runner import run_command, run_passthrough
from .config_builder import build_pipeline_config
from .pipeline_steps import (
    build_episode_metadata_display,
    display_pipeline_config,
    execute_cleanup,
    execute_deepcast,
    execute_enhancement,
    execute_export_final,
    execute_export_formats,
    execute_fetch,
    execute_notion_upload,
    execute_transcribe,
    handle_interactive_mode,
    print_results_summary,
)

__all__ = [
    "CommandBuilder",
    "build_episode_metadata_display",
    "build_pipeline_config",
    "display_pipeline_config",
    "execute_cleanup",
    "execute_deepcast",
    "execute_enhancement",
    "execute_export_final",
    "execute_export_formats",
    "execute_fetch",
    "execute_notion_upload",
    "execute_transcribe",
    "handle_interactive_mode",
    "print_results_summary",
    "run_command",
    "run_passthrough",
]
