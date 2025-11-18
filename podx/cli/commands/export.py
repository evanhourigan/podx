"""Export command for transcript format conversion."""

import click


@click.command(
    "export",
    help="Export transcripts to various formats (TXT, SRT, VTT, MD)",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.pass_context
def export_cmd(ctx):
    """Export transcripts to various formats (TXT, SRT, VTT, MD)."""
    # Import and invoke the actual export command
    from podx.cli.export import main as actual_command

    # Invoke the Click command with the current context's arguments
    # This uses Click's invocation API to properly forward arguments
    actual_command.main(args=ctx.args, standalone_mode=False)
