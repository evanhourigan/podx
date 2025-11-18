"""Transcode command for audio format conversion."""

import click


@click.command(
    "transcode",
    help="Convert audio files to different formats (wav16, mp3, aac)",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def transcode_cmd(ctx):
    """Convert audio files to different formats (wav16, mp3, aac)."""
    # Import and invoke the actual transcode command
    from podx.cli.transcode import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
