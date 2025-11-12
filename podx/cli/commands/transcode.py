"""Transcode command for audio format conversion."""
import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "transcode",
    help="Shim: run podx-transcode with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def transcode_cmd(ctx):
    """Convert audio files to different formats (wav16, mp3, aac)."""
    code = run_passthrough(["podx-transcode"] + ctx.args)
    sys.exit(code)
