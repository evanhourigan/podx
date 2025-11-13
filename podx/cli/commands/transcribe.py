"""Transcribe command for speech-to-text conversion."""
import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "transcribe",
    help="Convert audio to text using Whisper ASR models",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def transcribe_cmd(ctx):
    """Convert audio to text using Whisper ASR models."""
    code = run_passthrough(["podx-transcribe"] + ctx.args)
    sys.exit(code)
