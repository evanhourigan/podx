"""Diarize command for speaker identification."""
import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "diarize",
    help="Shim: run podx-diarize with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def diarize_cmd(ctx):
    """Add speaker identification to transcripts using WhisperX."""
    code = run_passthrough(["podx-diarize"] + ctx.args)
    sys.exit(code)
