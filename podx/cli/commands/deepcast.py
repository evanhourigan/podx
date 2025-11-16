"""Deepcast command for AI-powered transcript analysis."""

import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "deepcast",
    help="AI-powered transcript analysis and summarization",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def deepcast_cmd(ctx):
    """AI-powered transcript analysis and summarization."""
    code = run_passthrough(["podx-deepcast"] + ctx.args)
    sys.exit(code)
