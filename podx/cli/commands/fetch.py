"""Fetch command for podcast episode retrieval."""
import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "fetch",
    help="Find and download podcast episodes by show name or RSS URL",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],  # Disable Click's --help handling
    },
)
@click.pass_context
def fetch_cmd(ctx):
    """Find and download podcast episodes by show name or RSS URL."""
    code = run_passthrough(["podx-fetch"] + ctx.args)
    sys.exit(code)
