"""Disk cleanup command for episode directories."""

import click


@click.command(
    "clean",
    help="Clean up episode directories after Notion publish",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def clean_cmd(ctx):
    """Clean up episode directories after Notion publish."""
    from podx.cli.clean import main as actual_command

    actual_command.main(args=ctx.args, standalone_mode=False)
