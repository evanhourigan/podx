"""Models command for AI model information and pricing."""
import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "models",
    help="Shim: run podx-models with the given arguments",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def models_cmd(ctx):
    """List AI models with pricing and estimate deepcast cost."""
    code = run_passthrough(["podx-models"] + ctx.args)
    sys.exit(code)
