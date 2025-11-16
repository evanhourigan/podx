#!/usr/bin/env python3
"""PodX CLI - Main entry point for podcast processing pipeline.

This module provides the main CLI interface for podx, orchestrating all
podcast processing commands through a unified interface.
"""
from __future__ import annotations

import sys

# Use rich-click for colorized --help when available
try:  # pragma: no cover
    import click  # type: ignore
    import rich_click  # type: ignore

    # Style configuration (approximate the standard color convention)
    rc = rich_click.rich_click
    rc.STYLE_HEADING = "bold bright_green"
    rc.STYLE_USAGE = "bold white"
    rc.STYLE_COMMAND = "bold white"
    rc.STYLE_METAVAR = "yellow"
    rc.STYLE_SWITCH = "bright_black"  # flags
    rc.STYLE_OPTION = "bright_black"  # flags
    rc.STYLE_ARGUMENT = "yellow"  # flag arguments
    rc.STYLE_HELP = "white"
    rc.GROUP_ARGUMENTS_OPTIONS = True
    rc.MAX_WIDTH = 100

    BaseGroup = rich_click.RichGroup
except Exception:  # pragma: no cover
    import click  # type: ignore

    BaseGroup = click.Group

# Import all command modules
from podx.cli.commands import (
    config_command,
    deepcast_cmd,
    diarize_cmd,
    export_cmd,
    fetch_cmd,
    models_cmd,
    notion_cmd,
    preprocess_shim,
    register_config_group,
    register_deprecated_commands,
    run,
    transcode_cmd,
    transcribe_cmd,
)
from podx.logging import setup_logging

# Initialize logging
setup_logging()


class PodxGroup(BaseGroup):
    """Custom group to hide deprecated commands from help."""

    def list_commands(self, ctx):  # type: ignore[override]
        commands = super().list_commands(ctx)
        # Filter hidden and deprecated workflow aliases from help
        hidden_names = {"quick", "analyze", "publish"}
        return [name for name in commands if name not in hidden_names]


@click.group(cls=PodxGroup)
def main():
    """Podx — composable podcast pipeline

    Core idea: small tools that do one thing well and compose cleanly.

    Core commands (composable):
      fetch, transcode, transcribe, preprocess, diarize, export, deepcast, notion

    Orchestrator:
      run  — drive the pipeline end‑to‑end with flags (or interactive mode)

    Tips:
    - Use 'podx COMMAND --help' for details on each tool
    - All tools read JSON from stdin and write JSON to stdout so you can pipe them
    - See README.md for usage examples
    """
    pass


# Register main orchestration command
main.add_command(run, name="run")

# Register simple passthrough commands
main.add_command(fetch_cmd, name="fetch")
main.add_command(transcode_cmd, name="transcode")
main.add_command(transcribe_cmd, name="transcribe")
main.add_command(diarize_cmd, name="diarize")
main.add_command(export_cmd, name="export")
main.add_command(deepcast_cmd, name="deepcast")
main.add_command(models_cmd, name="models")
main.add_command(notion_cmd, name="notion")
main.add_command(preprocess_shim, name="preprocess")

# Register utility commands
main.add_command(config_command, name="config")

# Register deprecated commands (hidden from help)
register_deprecated_commands(main, run)

# Register config subcommands group
register_config_group(main)


# ============================================================================
# Standalone Entry Points
# ============================================================================


def run_main():
    """Entry point for podx-run standalone command."""
    # Invoke the main CLI with 'run' subcommand and pass all args
    sys.argv = ["podx", "run"] + sys.argv[1:]
    main()


if __name__ == "__main__":
    main()
