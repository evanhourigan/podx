"""Diarize command for speaker identification."""

import click


@click.command(
    "diarize",
    help="Add speaker identification to transcripts using WhisperX",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def diarize_cmd(ctx):
    """Add speaker identification to transcripts using WhisperX."""
    # Import and invoke the actual diarize command
    from podx.cli.diarize import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
