"""Post-analysis Q&A command."""

import click


@click.command(
    "ask",
    help="Ask a question about an episode transcript",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def ask_cmd(ctx):
    """Ask a question about an episode transcript."""
    from podx.cli.ask import main as actual_command

    actual_command.main(args=ctx.args, standalone_mode=False)
