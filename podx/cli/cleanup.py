"""CLI wrapper for cleanup command.

Simplified v4.0 command for transcript text cleanup.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.core.preprocess import PreprocessError, TranscriptPreprocessor
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.ui import (
    LiveTimer,
    apply_speaker_names,
    has_generic_speaker_ids,
    identify_speakers_interactive,
    select_episode_interactive,
)

logger = get_logger(__name__)
console = Console()


def _check_openai_key() -> bool:
    """Check if OPENAI_API_KEY is set."""
    import os

    return bool(os.getenv("OPENAI_API_KEY"))


@click.command(context_settings={"max_content_width": 120})
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--no-restore",
    is_flag=True,
    help="Skip LLM restoration (free, local processing only)",
)
@click.option(
    "--no-skip-ads",
    is_flag=True,
    help="Keep advertisement segments (default: filter them out)",
)
def main(path: Optional[Path], no_restore: bool, no_skip_ads: bool):
    """Clean up transcript text for readability and improved LLM analysis.

    \b
    Arguments:
      PATH    Episode directory (default: current directory)

    Without PATH, shows interactive episode selection.

    \b
    Processing:
      - Filters out advertisement segments via LLM (unless --no-skip-ads)
      - Identifies speakers interactively (if diarized with SPEAKER_XX labels)
      - Merges short adjacent segments into readable paragraphs
      - Normalizes whitespace and punctuation spacing
      - Restores proper punctuation/capitalization via LLM (unless --no-restore)

    \b
    Options:
      --no-restore    Skip LLM restoration (free, local processing only)
      --no-skip-ads   Keep advertisement segments (default: filter them out)

    \b
    Notes:
      - Episode must have transcript.json (run 'podx transcribe' first)
      - Run after 'podx diarize' if you want speaker labels preserved
      - LLM features use OpenAI API (~$0.03/hr), requires OPENAI_API_KEY
      - Ad filtering is tied to restore (--no-restore also skips ad filtering)

    \b
    Examples:
      podx cleanup                              # Interactive selection
      podx cleanup ./Show/2024-11-24-ep/        # Direct path, with restore + ad filtering
      podx cleanup . --no-restore               # Current dir, skip all LLM features
      podx cleanup . --no-skip-ads              # Keep ads, but still restore punctuation
    """
    # Track if we're in interactive mode
    interactive_mode = path is None

    # Interactive mode if no path provided
    if interactive_mode:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
                require="transcript",
                title="Select episode to cleanup",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)

            path = selected["directory"]

            # Warn if already cleaned
            if selected.get("cleaned"):
                console.print(
                    "\n[yellow]This transcript has already been cleaned.[/yellow]"
                )
                console.print("[dim]Re-cleaning will overwrite the current text.[/dim]")
                try:
                    confirm = input("Continue? [y/N] ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Cancelled[/dim]")
                    sys.exit(0)
                if confirm not in ("y", "yes"):
                    console.print("[dim]Cancelled[/dim]")
                    sys.exit(0)

            # Ask about restore in interactive mode (if not already specified)
            if not no_restore:
                if not _check_openai_key():
                    console.print(
                        "\n[yellow]OPENAI_API_KEY not set[/yellow] - skipping LLM restore"
                    )
                    no_restore = True
                else:
                    try:
                        restore_choice = (
                            input(
                                "Restore punctuation? Uses LLM for cleaner output (~$0.02/hr) [Y/n]: "
                            )
                            .strip()
                            .lower()
                        )
                    except (KeyboardInterrupt, EOFError):
                        console.print("\n[dim]Cancelled[/dim]")
                        sys.exit(0)
                    if restore_choice in ("n", "no"):
                        no_restore = True

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Resolve path
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print(f"[red]Error:[/red] No transcript.json found in {episode_dir}")
        console.print("[dim]Run 'podx transcribe' first[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    # Load transcript
    try:
        transcript = json.loads(transcript_path.read_text())
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load transcript: {e}")
        sys.exit(ExitCode.USER_ERROR)

    if "segments" not in transcript:
        console.print("[red]Error:[/red] transcript.json missing 'segments' field")
        sys.exit(ExitCode.USER_ERROR)

    # Speaker identification for diarized transcripts
    # Only prompt in interactive mode if transcript has generic SPEAKER_XX labels
    do_identify_speakers = False
    if (
        interactive_mode
        and transcript.get("diarized")
        and has_generic_speaker_ids(transcript["segments"])
    ):
        try:
            identify_choice = (
                input(
                    "Identify speakers? (recommended for diarized transcripts) [Y/n]: "
                )
                .strip()
                .lower()
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)
        do_identify_speakers = identify_choice not in ("n", "no")

    # Run speaker identification if requested
    speaker_map: dict = {}
    if do_identify_speakers:
        try:
            speaker_map = identify_speakers_interactive(transcript["segments"])
            if speaker_map:
                # Apply names to transcript
                transcript["segments"] = apply_speaker_names(
                    transcript["segments"], speaker_map
                )
                console.print(
                    f"[green]✓ Identified {len(speaker_map)} speaker(s)[/green]"
                )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Speaker identification cancelled[/dim]")
            # Continue with cleanup using original speaker IDs

    # Check for restore without API key (non-interactive mode)
    do_restore = not no_restore
    # Ad filtering is tied to restore - only skip ads if restore is enabled and not explicitly disabled
    do_skip_ads = do_restore and not no_skip_ads

    if do_restore and not _check_openai_key():
        console.print(
            "[red]Error:[/red] OPENAI_API_KEY not set (required for LLM features)"
        )
        console.print(
            "Run with --no-restore for local-only cleanup, or set your API key:"
        )
        console.print("  export OPENAI_API_KEY=your-key-here")
        sys.exit(ExitCode.USER_ERROR)

    # Show what we're doing
    console.print(f"[cyan]Cleaning up:[/cyan] {transcript_path.name}")
    console.print(f"[cyan]Segments:[/cyan] {len(transcript['segments'])}")
    console.print(f"[cyan]Skip ads:[/cyan] {'yes' if do_skip_ads else 'no'}")
    console.print("[cyan]Merge:[/cyan] yes")
    console.print("[cyan]Normalize:[/cyan] yes")
    console.print(f"[cyan]Restore:[/cyan] {'yes' if do_restore else 'no'}")

    # Start timer
    timer = LiveTimer("Cleaning up")
    timer.start()

    try:
        preprocessor = TranscriptPreprocessor(
            merge=True,
            normalize=True,
            restore=do_restore,
            skip_ads=do_skip_ads,
            max_gap=1.0,
            max_len=800,
            restore_model="gpt-4o-mini",
        )
        result = preprocessor.preprocess(transcript)

    except PreprocessError as e:
        timer.stop()
        console.print(f"[red]Cleanup Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)

    # Stop timer
    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Preserve existing metadata
    original_keys = [
        "audio_path",
        "language",
        "asr_model",
        "asr_provider",
        "decoder_options",
        "diarized",
    ]
    for key in original_keys:
        if key in transcript:
            result[key] = transcript[key]

    # Set cleanup state flags
    result["cleaned"] = True
    result["restored"] = do_restore

    # Save updated transcript
    transcript_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Show completion
    original_count = len(transcript["segments"])
    merged_count = len(result["segments"])
    ads_removed = result.get("ads_removed", 0)
    console.print(f"\n[green]✓ Cleanup complete ({minutes}:{seconds:02d})[/green]")
    console.print(f"  Segments: {original_count} → {merged_count}")
    if ads_removed > 0:
        console.print(f"  Ads removed: {ads_removed}")
    console.print(f"  Updated: {transcript_path}")


if __name__ == "__main__":
    main()
