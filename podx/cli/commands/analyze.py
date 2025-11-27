"""Analyze command for AI-powered transcript analysis."""

import click


@click.command(
    "analyze",
    help="AI-powered transcript analysis and summarization",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def analyze_cmd(ctx):
    """AI-powered transcript analysis and summarization."""
    # Import and invoke the actual analyze command
    from podx.cli.analyze import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)


# Backwards compatibility alias
deepcast_cmd = analyze_cmd
