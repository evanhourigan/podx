"""Notion command for uploading content to Notion databases."""

import click


@click.command(
    "notion",
    help="Upload processed content to Notion databases",
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
    # Import and invoke the actual notion command
    from podx.cli.notion import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
