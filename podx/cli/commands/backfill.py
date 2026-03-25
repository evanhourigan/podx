"""Backfill command for batch re-analysis and Notion publishing."""

import click


@click.command(
    "backfill",
    help="Batch re-analyze episodes and publish to Notion",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def backfill_cmd(ctx):
    """Batch re-analyze episodes and publish to Notion."""
    from podx.cli.backfill import main as actual_command

    actual_command.main(args=ctx.args, standalone_mode=False)
