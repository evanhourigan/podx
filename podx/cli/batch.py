"""Batch processing commands for multiple episodes."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.batch import (
    BatchProcessor,
    BatchStatus,
    EpisodeDiscovery,
    EpisodeFilter,
    ProcessingState,
)
from podx.core.diarize import DiarizationEngine
from podx.core.export_legacy import export_transcript
from podx.core.preprocess import TranscriptPreprocessor
from podx.core.transcribe import TranscriptionEngine
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.schemas import AudioMeta

logger = get_logger(__name__)
console = Console()


@click.command(
    name="batch-transcribe",
    help="Batch transcribe multiple episodes",
)
@click.option(
    "--auto-detect",
    is_flag=True,
    help="Auto-detect episodes from directory structure",
)
@click.option(
    "--pattern",
    help="Glob pattern to match episodes (e.g., '*/episode-meta.json', '*.mp3')",
)
@click.option(
    "--show",
    help="Filter by show name",
)
@click.option(
    "--since",
    help="Process episodes since date (YYYY-MM-DD)",
)
@click.option(
    "--date-range",
    help="Process episodes in date range (YYYY-MM-DD:YYYY-MM-DD)",
)
@click.option(
    "--min-duration",
    type=int,
    help="Minimum episode duration in seconds",
)
@click.option(
    "--max-duration",
    type=int,
    help="Maximum episode duration in seconds",
)
@click.option(
    "--model",
    default="large-v3",
    help="Transcription model (default: large-v3)",
)
@click.option(
    "--parallel",
    type=int,
    default=1,
    help="Number of parallel workers (default: 1)",
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    default=True,
    help="Continue processing if one episode fails (default: True)",
)
@click.option(
    "--max-retries",
    type=int,
    default=0,
    help="Maximum retry attempts per episode (default: 0)",
)
@click.option(
    "--retry-delay",
    type=int,
    default=5,
    help="Delay between retries in seconds (default: 5)",
)
@click.option(
    "--base-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Base directory to search (defaults to current directory)",
)
def batch_transcribe(
    auto_detect: bool,
    pattern: Optional[str],
    show: Optional[str],
    since: Optional[str],
    date_range: Optional[str],
    min_duration: Optional[int],
    max_duration: Optional[int],
    model: str,
    parallel: int,
    continue_on_error: bool,
    max_retries: int,
    retry_delay: int,
    base_dir: Optional[Path],
):
    """Batch transcribe multiple episodes.

    Examples:
        # Auto-detect all new episodes
        podx-batch-transcribe --auto-detect

        # Specific pattern
        podx-batch-transcribe --pattern "*/episode-meta.json"

        # Filter by show and date
        podx-batch-transcribe --show "Lex Fridman" --since 2024-01-01

        # Parallel processing
        podx-batch-transcribe --auto-detect --parallel 4

        # With retries
        podx-batch-transcribe --auto-detect --max-retries 3 --retry-delay 10
    """
    console.print("[bold blue]Batch Transcribe[/bold blue]\n")

    # Parse filters
    filters = EpisodeFilter(
        show=show,
        since=since,
        date_range=tuple(date_range.split(":")) if date_range else None,
        min_duration=min_duration,
        max_duration=max_duration,
        pattern=pattern,
    )

    # Discover episodes
    discovery = EpisodeDiscovery(base_dir=base_dir or Path.cwd())
    episodes = discovery.discover_episodes(auto_detect=auto_detect, filters=filters)

    # Filter to only episodes with valid audio
    episodes = discovery.filter_by_audio_path(episodes)

    if not episodes:
        console.print("[yellow]No episodes found matching criteria[/yellow]")
        sys.exit(ExitCode.USER_ERROR)

    # Initialize batch processor
    processor = BatchProcessor(
        parallel_workers=parallel,
        continue_on_error=continue_on_error,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )

    # Initialize batch status tracker
    batch_status = BatchStatus()

    # Add episodes to tracking
    for episode in episodes:
        episode_key = batch_status.add_episode(episode)
        batch_status.update_episode(
            episode_key, "transcribe", ProcessingState.IN_PROGRESS
        )

    # Define transcription function
    def transcribe_episode(episode):
        episode_key = episode.get("directory") or episode.get("title", "unknown")

        try:
            # Create AudioMeta
            audio_path = Path(episode["audio_path"])
            audio_meta = AudioMeta(audio_path=str(audio_path))

            # Transcribe
            engine = TranscriptionEngine(model=model)
            transcript = engine.transcribe(audio_meta)

            # Save transcript
            output_dir = Path(episode.get("directory", audio_path.parent))
            output_file = output_dir / "transcript.json"
            output_file.write_text(transcript.model_dump_json(indent=2))

            # Update status
            batch_status.update_episode(
                episode_key, "transcribe", ProcessingState.COMPLETED
            )

            return transcript

        except Exception as e:
            # Update status
            batch_status.update_episode(
                episode_key, "transcribe", ProcessingState.FAILED, str(e)
            )
            raise

    # Process batch
    results = processor.process_batch(
        episodes, transcribe_episode, "Batch Transcription"
    )

    # Show final status
    console.print()
    batch_status.display_status_table()

    # Exit with appropriate code
    exit_code = processor.get_exit_code(results)
    sys.exit(exit_code)


@click.command(
    name="batch-pipeline",
    help="Run full pipeline on multiple episodes",
)
@click.option(
    "--auto-detect",
    is_flag=True,
    help="Auto-detect episodes from directory structure",
)
@click.option(
    "--pattern",
    help="Glob pattern to match episodes",
)
@click.option(
    "--show",
    help="Filter by show name",
)
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
    "--parallel",
    type=int,
    default=1,
    help="Number of parallel workers",
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    default=True,
    help="Continue if one episode fails",
)
@click.option(
    "--steps",
    default="transcribe,diarize,preprocess,analyze,export",
    help="Pipeline steps (comma-separated)",
)
@click.option(
    "--export-formats",
    default="txt,srt,md",
    help="Export formats (comma-separated)",
)
@click.option(
    "--base-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Base directory to search",
)
def batch_pipeline(
    auto_detect: bool,
    pattern: Optional[str],
    show: Optional[str],
    model: str,
    llm_model: str,
    parallel: int,
    continue_on_error: bool,
    steps: str,
    export_formats: str,
    base_dir: Optional[Path],
):
    """Run full pipeline on multiple episodes.

    Examples:
        # Full pipeline for all new episodes
        podx-batch-pipeline --auto-detect

        # Custom steps
        podx-batch-pipeline --auto-detect --steps transcribe,diarize,export

        # With specific models
        podx-batch-pipeline --auto-detect --model large-v3 --llm-model gpt-4o

        # Parallel processing
        podx-batch-pipeline --auto-detect --parallel 2
    """
    console.print("[bold blue]Batch Pipeline[/bold blue]\n")

    # Parse steps
    pipeline_steps = [s.strip() for s in steps.split(",")]
    formats = [f.strip() for f in export_formats.split(",")]

    # Parse filters
    filters = EpisodeFilter(show=show, pattern=pattern)

    # Discover episodes
    discovery = EpisodeDiscovery(base_dir=base_dir or Path.cwd())
    episodes = discovery.discover_episodes(auto_detect=auto_detect, filters=filters)
    episodes = discovery.filter_by_audio_path(episodes)

    if not episodes:
        console.print("[yellow]No episodes found[/yellow]")
        sys.exit(ExitCode.USER_ERROR)

    # Initialize processor
    processor = BatchProcessor(
        parallel_workers=parallel, continue_on_error=continue_on_error
    )

    # Initialize status tracker
    batch_status = BatchStatus()
    for episode in episodes:
        batch_status.add_episode(episode)

    # Define pipeline function
    def run_pipeline(episode):
        episode_key = episode.get("directory") or episode.get("title", "unknown")
        audio_path = Path(episode["audio_path"])
        output_dir = Path(episode.get("directory", audio_path.parent))

        transcript = None

        try:
            # Step 1: Transcribe
            if "transcribe" in pipeline_steps:
                batch_status.update_episode(
                    episode_key, "transcribe", ProcessingState.IN_PROGRESS
                )

                audio_meta = AudioMeta(audio_path=str(audio_path))
                engine = TranscriptionEngine(model=model)
                transcript = engine.transcribe(audio_meta)

                # Save transcript
                output_file = output_dir / "transcript.json"
                output_file.write_text(transcript.model_dump_json(indent=2))

                batch_status.update_episode(
                    episode_key, "transcribe", ProcessingState.COMPLETED
                )

            # Load existing transcript if not transcribing
            if transcript is None:
                transcript_file = output_dir / "transcript.json"
                if transcript_file.exists():
                    import json

                    with open(transcript_file) as f:
                        transcript_data = json.load(f)
                else:
                    raise ValueError("No transcript found")
            else:
                transcript_data = transcript.model_dump()

            # Step 2: Diarize
            if "diarize" in pipeline_steps:
                batch_status.update_episode(
                    episode_key, "diarize", ProcessingState.IN_PROGRESS
                )

                diarize_engine = DiarizationEngine()
                transcript_data = diarize_engine.diarize(audio_path, transcript_data)

                output_file = output_dir / "diarized-transcript.json"
                import json

                output_file.write_text(json.dumps(transcript_data, indent=2))

                batch_status.update_episode(
                    episode_key, "diarize", ProcessingState.COMPLETED
                )

            # Step 3: Preprocess
            if "preprocess" in pipeline_steps:
                batch_status.update_episode(
                    episode_key, "preprocess", ProcessingState.IN_PROGRESS
                )

                preprocessor = TranscriptPreprocessor()
                transcript_data = preprocessor.preprocess(
                    transcript_data, merge_segments=True, restore_punctuation=True
                )

                output_file = output_dir / "preprocessed-transcript.json"
                import json

                output_file.write_text(json.dumps(transcript_data, indent=2))

                batch_status.update_episode(
                    episode_key, "preprocess", ProcessingState.COMPLETED
                )

            # Step 4: Analyze
            if "analyze" in pipeline_steps or "deepcast" in pipeline_steps:
                batch_status.update_episode(
                    episode_key, "analyze", ProcessingState.IN_PROGRESS
                )

                try:
                    from podx.core.analyze import AnalyzeEngine

                    analyze_engine = AnalyzeEngine(llm_model=llm_model)
                    analysis_notes, metadata = analyze_engine.analyze(transcript_data)

                    # Save analysis notes
                    output_file = output_dir / "analysis-notes.md"
                    output_file.write_text(analysis_notes)

                    # Add to transcript
                    transcript_data["analysis_notes"] = analysis_notes
                    if metadata:
                        transcript_data["analysis_metadata"] = metadata

                    batch_status.update_episode(
                        episode_key, "analyze", ProcessingState.COMPLETED
                    )

                except ImportError:
                    logger.warning("Analysis requires LLM dependencies")
                    batch_status.update_episode(
                        episode_key,
                        "analyze",
                        ProcessingState.FAILED,
                        "Missing LLM dependencies",
                    )

            # Step 5: Export
            if "export" in pipeline_steps:
                batch_status.update_episode(
                    episode_key, "export", ProcessingState.IN_PROGRESS
                )

                export_transcript(
                    transcript_data=transcript_data,
                    output_dir=output_dir,
                    base_name=audio_path.stem,
                    formats=formats,
                    title=episode.get("title", audio_path.stem),
                )

                batch_status.update_episode(
                    episode_key, "export", ProcessingState.COMPLETED
                )

            return transcript_data

        except Exception:
            logger.exception(f"Pipeline failed for {episode.get('title')}")
            raise

    # Process batch
    results = processor.process_batch(episodes, run_pipeline, "Batch Pipeline")

    # Show final status
    console.print()
    batch_status.display_status_table()

    # Exit
    exit_code = processor.get_exit_code(results)
    sys.exit(exit_code)


@click.command(
    name="batch-status",
    help="Show batch processing status",
)
@click.option(
    "--export",
    type=click.Path(path_type=Path),
    help="Export status to file (JSON or CSV)",
)
@click.option(
    "--clear-completed",
    is_flag=True,
    help="Clear completed episodes from tracking",
)
def batch_status_cmd(export: Optional[Path], clear_completed: bool):
    """Show batch processing status.

    Examples:
        # Show status table
        podx-batch-status

        # Export to JSON
        podx-batch-status --export status.json

        # Export to CSV
        podx-batch-status --export status.csv

        # Clear completed episodes
        podx-batch-status --clear-completed
    """
    batch_status = BatchStatus()

    if clear_completed:
        batch_status.clear_completed()
        return

    if export:
        if export.suffix == ".json":
            batch_status.export_json(export)
        elif export.suffix == ".csv":
            batch_status.export_csv(export)
        else:
            console.print("[red]Unsupported export format. Use .json or .csv[/red]")
            sys.exit(ExitCode.USER_ERROR)
    else:
        batch_status.display_status_table()


if __name__ == "__main__":
    # For development/testing
    batch_transcribe()
