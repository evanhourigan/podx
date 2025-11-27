#!/usr/bin/env python3
"""CLI wrapper for analyze command.

Simplified v4.0 command that operates on episode directories.
Uses templates system for customizable analysis.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from podx.core.analyze import AnalyzeEngine, AnalyzeError
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.templates.manager import TemplateError, TemplateManager
from podx.ui import select_episode_interactive

logger = get_logger(__name__)


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
    "--template",
    default="general",
    help="Analysis template (see 'podx templates list')",
)
def main(path: Optional[Path], model: str, template: str):
    """Generate AI analysis of a transcript.

    \b
    Arguments:
      PATH    Episode directory (default: current directory)

    Without PATH, shows interactive episode selection.

    \b
    Templates (use 'podx templates list' for full list):
      general             Works for any podcast (default)
      interview-1on1      Host interviewing a single guest
      panel-discussion    Multiple hosts/guests discussing
      solo-commentary     Single host sharing thoughts
      technical-deep-dive In-depth technical discussion

    \b
    Models:
      gpt-4o-mini     Fast and affordable (default)
      gpt-4o          Best quality
      claude-sonnet-4-5   Anthropic alternative

    \b
    Examples:
      podx analyze                                    # Interactive selection
      podx analyze ./Show/2024-11-24-ep/              # Direct path
      podx analyze . --model gpt-4o                   # Current dir, best model
      podx analyze ./ep/ --template panel-discussion  # Panel analysis

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
                click.echo("Selection cancelled")
                sys.exit(0)

            path = selected["directory"]
        except KeyboardInterrupt:
            click.echo("\nCancelled")
            sys.exit(0)

    # Resolve path
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find transcript
    transcript_path = _find_transcript(episode_dir)
    if not transcript_path:
        click.echo(f"podx analyze: no transcript.json found in {episode_dir}", err=True)
        click.echo("Run 'podx transcribe' first", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Load transcript
    try:
        transcript = json.loads(transcript_path.read_text())
    except Exception as e:
        click.echo(f"podx analyze: failed to load transcript: {e}", err=True)
        sys.exit(ExitCode.USER_ERROR)

    if "segments" not in transcript:
        click.echo("podx analyze: transcript.json missing 'segments' field", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Load template
    try:
        manager = TemplateManager()
        tmpl = manager.load(template)
    except TemplateError:
        click.echo(f"podx analyze: template '{template}' not found", err=True)
        click.echo("Use 'podx templates list' to see available templates", err=True)
        sys.exit(ExitCode.USER_ERROR)

    # Output path
    analysis_path = episode_dir / "analysis.json"

    # Show what we're doing
    click.echo(f"Analyzing: {transcript_path.name}")
    click.echo(f"Template: {template}")
    click.echo(f"Model: {model}")

    start_time = time.time()

    try:
        engine = AnalyzeEngine(
            model=model,
            temperature=0.2,
            max_chars_per_chunk=24000,
        )

        # Build transcript text for template
        segments = transcript.get("segments", [])
        transcript_text = "\n".join(
            f"[{s.get('speaker', 'SPEAKER')}] {s.get('text', '')}"
            if s.get("speaker")
            else s.get("text", "")
            for s in segments
        )

        # Count speakers
        speakers = set(s.get("speaker") for s in segments if s.get("speaker"))

        # Build context for template
        context = {
            "transcript": transcript_text,
            "speaker_count": len(speakers) if speakers else 1,
            "duration": int(segments[-1].get("end", 0) // 60) if segments else 0,
        }

        # Render template
        system_prompt, user_prompt = tmpl.render(context)

        md, json_data = engine.analyze(
            transcript=transcript,
            system_prompt=system_prompt,
            map_instructions="Extract key points, notable quotes, and insights from this section.",
            reduce_instructions=user_prompt,
            want_json=True,
        )

    except AnalyzeError as e:
        click.echo(f"podx analyze: {e}", err=True)
        sys.exit(ExitCode.PROCESSING_ERROR)

    # Calculate elapsed time
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Build output
    result = {
        "markdown": md,
        "template": template,
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
    click.echo(f"Analysis complete ({minutes}:{seconds:02d})")
    if json_data:
        click.echo(f"  Key points: {len(json_data.get('key_points', []))}")
        click.echo(f"  Quotes: {len(json_data.get('quotes', []))}")
    click.echo(f"  Output: {analysis_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
