#!/usr/bin/env python3
"""PodX CLI - Main entry point for podcast processing pipeline.

This module provides the main CLI interface for podx, orchestrating all
podcast processing commands through a unified interface.
"""
from __future__ import annotations

import sys

# Use plain click for UNIX-style errors without fancy formatting
import click  # type: ignore

BaseGroup = click.Group

# Initialize logging BEFORE any imports that might log
from podx.logging import setup_logging  # noqa: E402

setup_logging()

# Import missing commands for v3.0 CLI restructure
from podx.cli import (  # noqa: E402 - Must import after logging setup
    analyze,
    init,
    templates,
)

# Import all command modules
from podx.cli.commands import (  # noqa: E402 - Must import after logging setup
    deepcast_cmd,
    diarize_cmd,
    export_cmd,
    fetch_cmd,
    models_cmd,
    notion_cmd,
    register_deprecated_commands,
    run,
    server,
    transcribe_cmd,
)

# Import simplified config command
from podx.cli import config  # noqa: E402


class PodxGroup(BaseGroup):
    """Custom group to hide deprecated commands from help."""

    def list_commands(self, ctx):  # type: ignore[override]
        commands = super().list_commands(ctx)
        # Filter hidden and deprecated workflow aliases from help
        hidden_names = {"quick", "analyze", "publish"}
        return [name for name in commands if name not in hidden_names]


@click.group(cls=PodxGroup, context_settings={"max_content_width": 120})
def main():
    """Podx — podcast processing pipeline

    \b
    Core commands:
      fetch       Download podcast episodes
      transcribe  Transcribe audio to text
      diarize     Add speaker labels to transcript
      analyze     Generate AI analysis (formerly deepcast)
      export      Export transcript/analysis to various formats
      notion      Publish to Notion

    \b
    Utilities:
      models      List AI models with pricing
      config      Manage configuration
      init        Setup wizard for new users
      templates   Manage analysis templates
      run         Full pipeline orchestrator

    \b
    Tips:
      Use 'podx COMMAND --help' for details on each command
      Run 'podx init' for first-time setup
    """
    pass


# Register main orchestration command
main.add_command(run, name="run")

# Register core pipeline commands
main.add_command(fetch_cmd, name="fetch")
main.add_command(transcribe_cmd, name="transcribe")
main.add_command(diarize_cmd, name="diarize")
main.add_command(export_cmd, name="export")
main.add_command(deepcast_cmd, name="deepcast")  # Backwards compat alias for analyze
main.add_command(models_cmd, name="models")
main.add_command(notion_cmd, name="notion")

# Register utility commands
main.add_command(config.main, name="config")

# Register deprecated commands (hidden from help)
register_deprecated_commands(main, run)

# ============================================================================
# Additional commands
# ============================================================================

# Register standalone commands
main.add_command(init.main, name="init")
main.add_command(analyze.main, name="analyze")
main.add_command(templates.main, name="templates")

# Register server command group (v3.0 - Web API Server)
main.add_command(server, name="server")


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
