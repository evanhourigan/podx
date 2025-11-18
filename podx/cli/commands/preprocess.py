"""Preprocess command shim."""

import click


@click.command(
    "preprocess",
    help="Run preprocessing on transcripts (merge/normalize/restore)",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def preprocess_shim(ctx):
    """Run preprocessing on transcripts (merge/normalize/restore)."""
    # Import and invoke the actual preprocess command
    from podx.cli.preprocess import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
