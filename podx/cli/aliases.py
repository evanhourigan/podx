"""Command aliases and shortcuts for common podx operations.

Provides convenient shortcuts for frequently used command combinations:
- podx quick: Fast transcription with minimal features
- podx full: Complete pipeline (transcribe + diarize + preprocess + deepcast + export)
- podx hq: High-quality processing
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console

from podx.core.transcribe import TranscriptionEngine
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger

console = Console()
logger = get_logger(__name__)


@click.group(
    help="Quick command aliases for common workflows",
    invoke_without_command=True,
)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Quick aliases for common podx workflows."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command(name="quick", help="Fast transcription (base model, txt only)")
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file")
def quick(audio_file: Path, output: Optional[Path]) -> None:
    """Quick transcription with base model and txt export only.

    Equivalent to:
        podx-transcribe <audio> --model base --no-diarize
        podx-export <transcript> --format txt

    Examples:
        podx quick podcast.mp3
        podx quick podcast.mp3 -o output.txt
    """
    from podx.core.export_legacy import export_transcript

    console.print("[bold blue]Quick Mode:[/bold blue] Fast transcription (base model)")
    console.print(f"File: {audio_file}")

    try:
        # Transcribe with base model
        console.print("\n[cyan]Transcribing...[/cyan]")
        engine = TranscriptionEngine(model="base")
        transcript_dict = engine.transcribe(audio_file)

        # Export to txt
        output_path = output or audio_file.with_suffix(".txt")
        console.print(f"\n[cyan]Exporting to {output_path}...[/cyan]")

        export_transcript(
            transcript=transcript_dict,
            output_dir=output_path.parent,
            base_name=output_path.stem,
            formats=["txt"],
        )

        console.print(f"\n[green]✓[/green] Complete: {output_path}")
        sys.exit(ExitCode.SUCCESS)

    except Exception as e:
        console.print(f"\n[red]✗ Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)


@main.command(name="full", help="Complete pipeline (transcribe → diarize → preprocess → analyze)")
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--model",
    default="large-v3",
    help="ASR model (default: large-v3)",
)
@click.option(
    "--llm-model",
    default="gpt-4o-mini",
    help="LLM model for analysis (default: gpt-4o-mini)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: same as audio file)",
)
def full(
    audio_file: Path,
    model: str,
    llm_model: str,
    output_dir: Optional[Path],
) -> None:
    """Run complete pipeline: transcribe → diarize → preprocess → analyze → export.

    Equivalent to:
        podx-transcribe <audio> --model large-v3
        podx-diarize <transcript>
        podx-preprocess <transcript>
        podx-analyze <transcript> --llm-model gpt-4o-mini
        podx-export <transcript> --formats txt,srt,md

    Examples:
        podx full podcast.mp3
        podx full podcast.mp3 --model large-v3 --llm-model gpt-4o
        podx full podcast.mp3 -o ./output
    """
    from podx.core.diarize import DiarizationEngine
    from podx.core.export_legacy import export_transcript
    from podx.core.preprocess import TranscriptPreprocessor

    console.print("[bold blue]Full Pipeline:[/bold blue] Complete processing")
    console.print(f"File: {audio_file}")
    console.print(f"ASR Model: {model}")
    console.print(f"LLM Model: {llm_model}")

    output_directory = output_dir or audio_file.parent

    try:
        # Step 1: Transcribe
        console.print("\n[bold cyan]Step 1/5:[/bold cyan] Transcribing...")
        engine = TranscriptionEngine(model=model)
        transcript_dict: Dict[str, Any] = engine.transcribe(audio_file)
        console.print("[green]✓[/green] Transcription complete")

        # Step 2: Diarize
        console.print("\n[bold cyan]Step 2/5:[/bold cyan] Diarizing...")
        diarize_engine = DiarizationEngine()
        transcript_with_speakers = diarize_engine.diarize(
            audio_path=audio_file,
            transcript_segments=transcript_dict.get("segments", []),
        )
        console.print("[green]✓[/green] Diarization complete")

        # Step 3: Preprocess
        console.print("\n[bold cyan]Step 3/5:[/bold cyan] Preprocessing...")
        preprocessor = TranscriptPreprocessor(
            merge=True,
            normalize=True,
            restore=True,
        )
        preprocessed = preprocessor.preprocess(transcript_with_speakers)
        console.print("[green]✓[/green] Preprocessing complete")

        # Step 4: Analyze
        console.print("\n[bold cyan]Step 4/5:[/bold cyan] Running analysis...")
        try:
            from podx.core.analyze import AnalyzeEngine

            analyze_engine = AnalyzeEngine(model=llm_model)
            analysis_notes, metadata = analyze_engine.analyze(
                preprocessed,
                system_prompt="You are a podcast analyst.",
                map_instructions="Analyze this transcript segment.",
                reduce_instructions="Synthesize the analysis.",
            )

            # Add analysis to transcript
            preprocessed["analysis_notes"] = analysis_notes
            if metadata:
                preprocessed["analysis_metadata"] = metadata

            console.print("[green]✓[/green] Analysis complete")
        except ImportError:
            console.print("[yellow]⚠ Warning:[/yellow] Analysis requires LLM dependencies")
            console.print("Install with: pip install podx[llm]")
        except Exception as e:
            console.print(f"[yellow]⚠ Warning:[/yellow] Analysis failed: {e}")

        # Step 5: Export
        console.print("\n[bold cyan]Step 5/5:[/bold cyan] Exporting...")
        export_transcript(
            transcript=preprocessed,
            output_dir=output_directory,
            base_name=audio_file.stem,
            formats=["txt", "srt", "md"],
        )
        console.print("[green]✓[/green] Export complete")

        console.print("\n[green]✓ Pipeline complete![/green]")
        console.print(f"Output directory: {output_directory}")

        sys.exit(ExitCode.SUCCESS)

    except Exception as e:
        console.print(f"\n[red]✗ Error:[/red] {e}")
        logger.exception("Full pipeline failed")
        sys.exit(ExitCode.PROCESSING_ERROR)


@main.command(name="hq", help="High-quality processing (large-v3 + all features)")
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory",
)
def hq(audio_file: Path, output_dir: Optional[Path]) -> None:
    """High-quality processing with best models and all features.

    Equivalent to:
        podx full <audio> --model large-v3 --llm-model gpt-4o

    Examples:
        podx hq podcast.mp3
        podx hq podcast.mp3 -o ./high-quality-output
    """
    # Just call the full command with high-quality settings
    from click.testing import CliRunner

    runner = CliRunner()
    args = [str(audio_file), "--model", "large-v3", "--llm-model", "gpt-4o"]
    if output_dir:
        args.extend(["--output-dir", str(output_dir)])

    result = runner.invoke(full, args)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
