"""Transcribe command for speech-to-text conversion."""

import click


@click.command(
    "transcribe",
    help="Convert audio to text using Whisper ASR models",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def transcribe_cmd(ctx):
    """Convert audio to text using Whisper ASR models."""
    # Import and invoke the actual transcribe command
    from podx.cli.transcribe import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
