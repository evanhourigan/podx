"""Analyze command shim - forwards to main analyze module."""

import click


@click.command("analyze")
@click.argument("path", required=False)
@click.option("--model", default="gpt-4o-mini", help="AI model for analysis")
@click.option("--type", "analysis_type", default="general", help="Analysis type")
@click.pass_context
def analyze_cmd(ctx, path, model, analysis_type):
    """Generate AI analysis of a transcript."""
    from podx.cli.analyze import main as analyze_main

    # Build args list
    args = []
    if path:
        args.append(path)
    if model != "gpt-4o-mini":
        args.extend(["--model", model])
    if analysis_type != "general":
        args.extend(["--type", analysis_type])

    analyze_main.main(args=args, standalone_mode=False)


# Backwards compatibility alias - hidden from help, shows deprecation warning when used
@click.command("deepcast", hidden=True)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def deepcast_cmd(ctx, args):
    """DEPRECATED: Use 'podx analyze' instead."""
    from rich.console import Console

    console = Console()
    console.print(
        "[yellow]Warning:[/yellow] 'podx deepcast' is deprecated. " "Use 'podx analyze' instead."
    )
    console.print()

    # Forward to analyze
    from podx.cli.analyze import main as analyze_main

    analyze_main.main(args=list(args), standalone_mode=False)
