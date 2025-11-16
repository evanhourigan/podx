"""Export command for transcript format conversion."""

import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "export",
    help="Export transcripts to various formats (TXT, SRT, VTT, MD)",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def export_cmd(ctx):
    """Export transcripts to various formats (TXT, SRT, VTT, MD)."""
    code = run_passthrough(["podx-export"] + ctx.args)
    sys.exit(code)
