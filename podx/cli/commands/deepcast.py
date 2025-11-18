"""Deepcast command for AI-powered transcript analysis."""

import click


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
    # Import and invoke the actual deepcast command
    from podx.cli.deepcast import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
