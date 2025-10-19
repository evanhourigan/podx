#!/usr/bin/env python3
"""
Example: Using the PodX Service Layer

This example demonstrates how to use the service layer API as an alternative
to the CLI interface. The service layer provides a programmatic interface for
integrating PodX into Python applications, notebooks, or automation scripts.
"""

from pathlib import Path

from podx.services import PipelineConfig, PipelineService


def basic_pipeline_example():
    """Run a basic podcast processing pipeline."""
    print("=" * 60)
    print("Example 1: Basic Pipeline (Fetch + Transcribe)")
    print("=" * 60)

    # Configure pipeline
    config = PipelineConfig(
        show="Lex Fridman Podcast",
        date="2024-10-01",  # Get episode from this date
        model="large-v3-turbo",  # Fast, high-quality transcription
        compute="int8",  # Optimized compute type
        verbose=True,
    )

    # Create service and execute
    service = PipelineService(config)

    def progress_callback(step: str, status: str):
        """Print progress updates."""
        print(f"  [{step}] {status}")

    result = service.execute(progress_callback=progress_callback)

    # Print results
    print(f"\nCompleted in {result.duration:.2f}s")
    print(f"Working directory: {result.workdir}")
    print(f"Steps completed: {', '.join(result.steps_completed)}")
    print(f"Artifacts: {len(result.artifacts)}")


def full_pipeline_example():
    """Run a full pipeline with all features enabled."""
    print("\n" + "=" * 60)
    print("Example 2: Full Pipeline (Align + Diarize + Deepcast)")
    print("=" * 60)

    config = PipelineConfig(
        show="All-In Podcast",
        date="2024-10",  # Latest episode from October
        model="large-v3-turbo",
        align=True,  # Enable word-level alignment
        diarize=True,  # Enable speaker diarization
        deepcast=True,  # Enable AI analysis
        deepcast_model="gpt-4o",
        extract_markdown=True,
        deepcast_pdf=True,
        verbose=False,
    )

    service = PipelineService(config)
    result = service.execute()

    print(f"\nCompleted in {result.duration:.2f}s")
    print("Artifacts generated:")
    for key, path in result.artifacts.items():
        if Path(path).exists():
            size = Path(path).stat().st_size
            print(f"  - {key}: {path} ({size:,} bytes)")


def dual_mode_example():
    """Run dual-mode transcription with precision + recall."""
    print("\n" + "=" * 60)
    print("Example 3: Dual-Mode (Precision + Recall + Consensus)")
    print("=" * 60)

    config = PipelineConfig(
        show="Acquired",
        title_contains="nvidia",  # Find episode about NVIDIA
        model="large-v3",
        dual=True,  # Enable dual-mode (precision + recall)
        preprocess=True,  # Enable preprocessing
        deepcast=True,  # Analyze both tracks
        no_consensus=False,  # Generate consensus
        verbose=True,
    )

    service = PipelineService(config)
    result = service.execute()

    print("\nDual-mode analysis complete!")
    print(f"Duration: {result.duration:.2f}s")
    print(f"Check {result.workdir} for:")
    print("  - transcript-large_v3-precision.json")
    print("  - transcript-large_v3-recall.json")
    print("  - deepcast-precision-*.json")
    print("  - deepcast-recall-*.json")
    print("  - agreement.json")
    print("  - consensus.json")


def youtube_pipeline_example():
    """Process a YouTube video."""
    print("\n" + "=" * 60)
    print("Example 4: YouTube Video Processing")
    print("=" * 60)

    config = PipelineConfig(
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        model="large-v3-turbo",
        align=True,
        deepcast=True,
        deepcast_model="gpt-4o-mini",  # Faster, cheaper model
        extract_markdown=True,
        workdir=Path("./youtube-output"),  # Custom output directory
    )

    service = PipelineService(config)
    result = service.execute()

    print("\nYouTube processing complete!")
    print(f"Saved to: {result.workdir}")


def custom_workdir_example():
    """Use a custom working directory for organization."""
    print("\n" + "=" * 60)
    print("Example 5: Custom Working Directory")
    print("=" * 60)

    # Create organized directory structure
    base_dir = Path.home() / "podcasts" / "lex-fridman" / "2024-10-15"

    config = PipelineConfig(
        show="Lex Fridman Podcast",
        date="2024-10-15",
        workdir=base_dir,  # Explicit working directory
        model="large-v3-turbo",
        align=True,
        diarize=True,
        deepcast=True,
        clean=True,  # Clean up intermediate files
        no_keep_audio=False,  # Keep audio files
    )

    service = PipelineService(config)
    result = service.execute()

    print("\nPipeline complete!")
    print(f"All files saved to: {result.workdir}")
    print(f"Intermediate files cleaned: {config.clean}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PodX Service Layer Examples")
    print("=" * 60)
    print("\nThese examples demonstrate the programmatic API.")
    print("Uncomment the example you want to run:")
    print()

    # Uncomment one example to run:
    # basic_pipeline_example()
    # full_pipeline_example()
    # dual_mode_example()
    # youtube_pipeline_example()
    # custom_workdir_example()

    print("\nTo run an example, uncomment it in the script.")
    print("\nService Layer Benefits:")
    print("  ✓ Programmatic control over pipeline execution")
    print("  ✓ Easy integration into Python applications")
    print("  ✓ Progress callbacks for custom UI/logging")
    print("  ✓ Type-safe configuration with PipelineConfig")
    print("  ✓ Structured results with PipelineResult")
    print("  ✓ Perfect for notebooks, scripts, and automation")
