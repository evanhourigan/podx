"""Notion command for uploading content to Notion databases."""
import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "notion",
    help="Shim: run podx-notion with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def notion_cmd(ctx):
    """Upload processed content to Notion databases."""
    code = run_passthrough(["podx-notion"] + ctx.args)
    sys.exit(code)
