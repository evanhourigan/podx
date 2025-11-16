"""CLI command for cost estimation.

Estimates costs before running expensive operations like transcription and deepcast.
Helps users understand the financial impact of processing audio files.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from podx.domain.exit_codes import ExitCode
from podx.monitoring import CostEstimator

console = Console()


def get_audio_duration(audio_path: Path) -> Optional[float]:
    """Get audio duration in seconds using ffprobe.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds, or None if ffprobe fails
    """
    try:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())

    except Exception:
        pass

    return None


@click.command(help="Estimate costs for processing audio files")
@click.argument(
    "audio_file",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--duration",
    type=float,
    help="Audio duration in minutes (if file not provided)",
)
@click.option(
    "--asr-provider",
    type=click.Choice(["local", "openai"]),
    default="local",
    help="Transcription provider (default: local)",
)
@click.option(
    "--llm-model",
    default="gpt-4o",
    help="LLM model for deepcast (default: gpt-4o)",
)
@click.option(
    "--llm-provider",
    type=click.Choice(["openai", "anthropic", "openrouter"]),
    help="LLM provider (auto-detected if not specified)",
)
@click.option(
    "--include-preprocessing",
    is_flag=True,
    help="Include LLM preprocessing costs",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output as JSON",
)
def main(
    audio_file: Optional[Path],
    duration: Optional[float],
    asr_provider: str,
    llm_model: str,
    llm_provider: Optional[str],
    include_preprocessing: bool,
    json_output: bool,
):
    """
    Estimate costs for processing audio files.

    Provides cost estimates for:
    - Transcription (Whisper API vs local)
    - Deepcast/LLM processing
    - Full pipeline costs

    Examples:
        # Estimate from audio file
        podx estimate podcast.mp3

        # Estimate with specific models
        podx estimate podcast.mp3 --asr-provider openai --llm-model claude-3-sonnet

        # Estimate from duration (no file)
        podx estimate --duration 83.5 --llm-model gpt-4o-mini

        # JSON output
        podx estimate podcast.mp3 --json
    """
    estimator = CostEstimator()

    # Get duration
    if audio_file:
        duration_seconds = get_audio_duration(audio_file)
        if duration_seconds is None:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": "Could not determine audio duration. Install ffmpeg or use --duration.",
                            "type": "duration_error",
                        }
                    )
                )
            else:
                console.print(
                    "[red]Error:[/red] Could not determine audio duration. "
                    "Install ffmpeg or use --duration."
                )
            sys.exit(ExitCode.USER_ERROR)
        duration_minutes = duration_seconds / 60
    elif duration:
        duration_minutes = duration
        duration_seconds = duration * 60
    else:
        if json_output:
            print(
                json.dumps(
                    {
                        "error": "Provide either AUDIO_FILE or --duration",
                        "type": "validation_error",
                    }
                )
            )
        else:
            console.print("[red]Error:[/red] Provide either AUDIO_FILE or --duration")
        sys.exit(ExitCode.USER_ERROR)

    # Estimate costs
    estimate = estimator.estimate_from_audio_file(
        duration_seconds=duration_seconds,
        asr_provider=asr_provider,
        llm_model=llm_model,
        include_preprocessing=include_preprocessing,
    )

    costs = estimate["costs"]

    # Output
    if json_output:
        # JSON output
        output = {
            "duration_minutes": estimate["duration_minutes"],
            "estimated_transcript_chars": estimate["estimated_transcript_chars"],
            "asr_provider": asr_provider,
            "llm_model": llm_model,
            "llm_provider": llm_provider,
            "costs": costs,
        }
        print(json.dumps(output, indent=2))
    else:
        # Rich formatted output
        console.print("\n[bold cyan]Cost Estimate[/bold cyan]")
        console.print("=" * 50)

        if audio_file:
            console.print(f"[bold]Audio File:[/bold] {audio_file.name}")

        # Duration
        hours = int(duration_minutes // 60)
        mins = int(duration_minutes % 60)
        secs = int(duration_seconds % 60)
        if hours > 0:
            duration_str = f"{hours}h {mins}m {secs}s"
        else:
            duration_str = f"{mins}m {secs}s"
        console.print(f"[bold]Duration:[/bold] {duration_str}")

        # Models
        console.print(f"[bold]ASR Provider:[/bold] {asr_provider}")
        console.print(f"[bold]LLM Model:[/bold] {llm_model}")
        if llm_provider:
            console.print(f"[bold]LLM Provider:[/bold] {llm_provider}")

        # Cost breakdown table
        console.print("\n[bold]Cost Breakdown:[/bold]")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Stage", style="cyan")
        table.add_column("Cost (USD)", justify="right", style="green")

        table.add_row("Transcription", estimator.format_cost(costs["transcription"]))

        if include_preprocessing and costs["preprocessing"] > 0:
            table.add_row(
                "Preprocessing", estimator.format_cost(costs["preprocessing"])
            )

        table.add_row("Deepcast", estimator.format_cost(costs["deepcast"]))
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{estimator.format_cost(costs['total'])}[/bold]",
        )

        console.print(table)

        # Notes
        console.print("\n[dim]Notes:[/dim]")
        if asr_provider == "local":
            console.print(
                "[dim]- Transcription is free (local inference, electricity not included)[/dim]"
            )
        console.print(
            "[dim]- Costs are estimates based on typical usage patterns[/dim]"
        )
        console.print(
            "[dim]- Actual costs may vary based on text complexity and model updates[/dim]"
        )
        console.print("")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
