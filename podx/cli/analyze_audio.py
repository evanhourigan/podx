"""CLI command for audio quality analysis."""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from podx.core.audio_quality import AudioQualityAnalyzer
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger

logger = get_logger(__name__)
console = Console()


@click.command(
    name="analyze-audio",
    help="Analyze audio quality and recommend settings",
)
@click.argument(
    "audio_file",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--export",
    type=click.Path(path_type=Path),
    help="Export results to file (JSON)",
)
def main(audio_file: Path, output_json: bool, export: Path):
    """Analyze audio quality and recommend optimal settings.

    Analyzes audio file to detect quality issues and suggests optimal
    transcription settings including model selection and preprocessing options.

    Examples:
        # Analyze audio file
        podx-analyze-audio podcast.mp3

        # Output as JSON
        podx-analyze-audio podcast.mp3 --json

        # Export to file
        podx-analyze-audio podcast.mp3 --export analysis.json
    """
    try:
        # Analyze audio
        analyzer = AudioQualityAnalyzer()
        analysis = analyzer.analyze(audio_file)

        # Output format
        if output_json:
            # JSON output
            print(json.dumps(analysis, indent=2))
        elif export:
            # Export to file
            with open(export, "w") as f:
                json.dump(analysis, f, indent=2)
            console.print(f"[green]Analysis exported to {export}[/green]")
        else:
            # Rich formatted output
            _display_analysis(analysis)

        sys.exit(ExitCode.SUCCESS)

    except Exception as e:
        logger.exception("Audio analysis failed")
        console.print(f"[red]Error analyzing audio:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)


def _display_analysis(analysis: dict) -> None:
    """Display analysis results with Rich formatting.

    Args:
        analysis: Analysis results dictionary
    """
    quality = analysis["quality"]
    recommendations = analysis["recommendations"]

    # Header
    console.print("\n[bold blue]Audio Quality Analysis[/bold blue]")
    console.print("=" * 60)

    # Basic info
    console.print(f"\n[bold]File:[/bold] {analysis['audio_path']}")
    console.print(
        f"[bold]Duration:[/bold] {_format_duration(analysis['duration_seconds'])}"
    )
    console.print(f"[bold]Sample Rate:[/bold] {analysis['sample_rate']} Hz")

    # Quality metrics table
    console.print("\n[bold]Quality Metrics:[/bold]")
    metrics_table = Table(show_header=True)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="white")
    metrics_table.add_column("Rating", style="green")

    # SNR
    snr = quality["snr_db"]
    snr_rating = _rate_snr(snr)
    metrics_table.add_row("Signal-to-Noise Ratio", f"{snr:.1f} dB", snr_rating)

    # Dynamic range
    dr = quality["dynamic_range_db"]
    dr_rating = _rate_dynamic_range(dr)
    metrics_table.add_row("Dynamic Range", f"{dr:.1f} dB", dr_rating)

    # Clipping
    clipping = quality["clipping_ratio"] * 100
    clipping_rating = _rate_clipping(quality["clipping_ratio"])
    metrics_table.add_row("Clipping", f"{clipping:.2f}%", clipping_rating)

    # Silence
    silence = quality["silence_ratio"] * 100
    silence_rating = _rate_silence(quality["silence_ratio"])
    metrics_table.add_row("Silence", f"{silence:.1f}%", silence_rating)

    # Speech content
    speech = quality["speech_ratio"] * 100
    speech_rating = _rate_speech(quality["speech_ratio"])
    metrics_table.add_row("Speech Content", f"{speech:.1f}%", speech_rating)

    console.print(metrics_table)

    # Recommendations
    console.print("\n[bold]Recommendations:[/bold]")
    console.print(f"  [cyan]Model:[/cyan] {recommendations['model']}")
    console.print(
        f"  [cyan]VAD Filter:[/cyan] {'Recommended' if recommendations['vad_filter'] else 'Not needed'}"
    )

    # Suggestions
    if recommendations["suggestions"]:
        console.print("\n[bold]Suggestions:[/bold]")
        for suggestion in recommendations["suggestions"]:
            icon = _get_suggestion_icon(suggestion["type"])
            console.print(f"  {icon} {suggestion['message']}")
            console.print(f"    [dim]→ {suggestion['recommendation']}[/dim]")

    # Suggested command
    console.print("\n[bold]Suggested Command:[/bold]")
    model = recommendations["model"]
    vad_flag = " --vad-filter" if recommendations["vad_filter"] else ""
    suggested_cmd = f"podx-transcribe {analysis['audio_path']} --model {model}{vad_flag}"
    console.print(Panel(suggested_cmd, border_style="cyan"))
    console.print()


def _format_duration(seconds: float) -> str:
    """Format duration as HH:MM:SS.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def _rate_snr(snr: float) -> str:
    """Rate SNR quality.

    Args:
        snr: SNR in dB

    Returns:
        Rating string
    """
    if snr > 30:
        return "[green]Excellent[/green]"
    elif snr > 20:
        return "[green]Good[/green]"
    elif snr > 10:
        return "[yellow]Fair[/yellow]"
    else:
        return "[red]Poor[/red]"


def _rate_dynamic_range(dr: float) -> str:
    """Rate dynamic range.

    Args:
        dr: Dynamic range in dB

    Returns:
        Rating string
    """
    if dr > 20:
        return "[green]Good[/green]"
    elif dr > 10:
        return "[yellow]Fair[/yellow]"
    else:
        return "[red]Low[/red]"


def _rate_clipping(ratio: float) -> str:
    """Rate clipping level.

    Args:
        ratio: Clipping ratio (0.0 to 1.0)

    Returns:
        Rating string
    """
    if ratio < 0.001:
        return "[green]Minimal[/green]"
    elif ratio < 0.01:
        return "[yellow]Moderate[/yellow]"
    else:
        return "[red]High[/red]"


def _rate_silence(ratio: float) -> str:
    """Rate silence level.

    Args:
        ratio: Silence ratio (0.0 to 1.0)

    Returns:
        Rating string
    """
    if ratio < 0.15:
        return "[green]Low[/green]"
    elif ratio < 0.5:
        return "[yellow]Moderate[/yellow]"
    else:
        return "[yellow]High[/yellow]"


def _rate_speech(ratio: float) -> str:
    """Rate speech content.

    Args:
        ratio: Speech ratio (0.0 to 1.0)

    Returns:
        Rating string
    """
    if ratio > 0.7:
        return "[green]High[/green]"
    elif ratio > 0.3:
        return "[green]Moderate[/green]"
    else:
        return "[yellow]Low[/yellow]"


def _get_suggestion_icon(suggestion_type: str) -> str:
    """Get icon for suggestion type.

    Args:
        suggestion_type: Type of suggestion

    Returns:
        Icon string
    """
    icons = {
        "success": "[green]✓[/green]",
        "info": "[cyan]ℹ[/cyan]",
        "warning": "[yellow]⚠[/yellow]",
        "error": "[red]✗[/red]",
    }
    return icons.get(suggestion_type, "[blue]•[/blue]")


if __name__ == "__main__":
    main()
