"""Fetch command for podcast episode retrieval."""

import click


@click.command(
    "fetch",
    help="Find and download podcast episodes by show name or RSS URL",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def fetch_cmd(ctx):
    """Find and download podcast episodes by show name or RSS URL."""
    # Import and invoke the actual fetch command
    from podx.cli.fetch import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
