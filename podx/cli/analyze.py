#!/usr/bin/env python3
"""CLI wrapper for analyze command.

Simplified v4.0 command that operates on episode directories.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.core.analyze import AnalyzeEngine, AnalyzeError
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.ui import LiveTimer, select_episode_interactive

logger = get_logger(__name__)
console = Console()


def _find_transcript(directory: Path) -> Optional[Path]:
    """Find best transcript file in episode directory.

    Priority: diarized > aligned > base transcript
    """
    # Check for transcript.json first (new standard name)
    transcript = directory / "transcript.json"
    if transcript.exists():
        return transcript

    # Fall back to legacy patterns
    patterns = [
        "transcript-diarized-*.json",
        "diarized-transcript-*.json",
        "transcript-aligned-*.json",
        "transcript-*.json",
    ]

    for pattern in patterns:
        matches = list(directory.glob(pattern))
        if matches:
            # Skip preprocessed files
            for m in matches:
                if "preprocessed" not in m.name:
                    return m

    return None


@click.command()
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--model",
    default="gpt-4o-mini",
    help="AI model for analysis (e.g., gpt-4o, gpt-4o-mini, claude-sonnet-4-5)",
)
@click.option(
    "--type",
    "analysis_type",
    default="general",
    help="Analysis type (general, interview, panel, solo)",
)
def main(path: Optional[Path], model: str, analysis_type: str):
    """Generate AI analysis of a transcript.

    \b
    Arguments:
      PATH    Episode directory (default: current directory)

    Without PATH, shows interactive episode selection.

    \b
    Analysis Types:
      general     Default, works for any podcast
      interview   Guest-focused interview format
      panel       Multiple hosts/guests discussion
      solo        Single host commentary/monologue

    \b
    Models:
      gpt-4o-mini     Fast and affordable (default)
      gpt-4o          Best quality
      claude-sonnet-4-5   Anthropic alternative

    \b
    Examples:
      podx analyze                              # Interactive selection
      podx analyze ./Show/2024-11-24-ep/        # Direct path
      podx analyze . --model gpt-4o             # Current dir, best model
      podx analyze ./ep/ --type interview       # Interview-style analysis

    Requires:
      - Episode must have transcript.json (run 'podx transcribe' first)
      - OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable
    """
    # Interactive mode if no path provided
    if path is None:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)

            path = selected["directory"]
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Resolve path
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find transcript
    transcript_path = _find_transcript(episode_dir)
    if not transcript_path:
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

    # Output path
    analysis_path = episode_dir / "analysis.json"

    # Show what we're doing
    console.print(f"[cyan]Analyzing:[/cyan] {transcript_path.name}")
    console.print(f"[cyan]Model:[/cyan] {model}")
    console.print(f"[cyan]Type:[/cyan] {analysis_type}")

    # Start timer
    timer = LiveTimer("Analyzing")
    timer.start()

    try:
        engine = AnalyzeEngine(
            model=model,
            temperature=0.2,
            max_chars_per_chunk=24000,
        )

        # Build simple system prompt based on type
        type_prompts = {
            "general": "You are an expert podcast analyst. Create a comprehensive summary.",
            "interview": "You are analyzing an interview podcast. Focus on the guest's insights and key takeaways.",
            "panel": "You are analyzing a panel discussion. Track different perspectives and points of agreement/disagreement.",
            "solo": "You are analyzing a solo commentary. Focus on the host's main arguments and conclusions.",
        }
        system_prompt = type_prompts.get(analysis_type, type_prompts["general"])

        md, json_data = engine.analyze(
            transcript=transcript,
            system_prompt=system_prompt,
            map_instructions="Extract key points, notable quotes, and insights from this section.",
            reduce_instructions="Synthesize the section summaries into a cohesive analysis.",
            want_json=True,
        )

    except AnalyzeError as e:
        timer.stop()
        console.print(f"[red]Analysis Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)

    # Stop timer
    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Build output
    result = {
        "markdown": md,
        "analysis_type": analysis_type,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "transcript_path": str(transcript_path),
    }
    if json_data:
        result.update(json_data)

    # Save analysis
    analysis_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Show completion
    console.print(f"\n[green]✓ Analysis complete ({minutes}:{seconds:02d})[/green]")
    if json_data:
        console.print(f"  Key points: {len(json_data.get('key_points', []))}")
        console.print(f"  Quotes: {len(json_data.get('quotes', []))}")
    console.print(f"  Output: {analysis_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
