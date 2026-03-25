"""Speaker identification command."""

import click


@click.command(
    "speakers",
    help="Identify speakers in a diarized transcript",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def speakers_cmd(ctx):
    """Identify speakers in a diarized transcript."""
    from podx.cli.speakers import main as actual_command

    actual_command.main(args=ctx.args, standalone_mode=False)
