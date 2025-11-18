"""Models command for AI model information and pricing."""

import click


@click.command(
    "models",
    help="List AI models with pricing and estimate deepcast cost",
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
    # Import and invoke the actual models command
    from podx.cli.models import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
