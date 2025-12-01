"""Cleanup command for transcript text processing."""

import click


@click.command(
    "cleanup",
    help="Clean up transcript text for readability and improved LLM analysis",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def cleanup_cmd(ctx):
    """Clean up transcript text for readability and improved LLM analysis."""
    # Import and invoke the actual cleanup command
    from podx.cli.cleanup import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
