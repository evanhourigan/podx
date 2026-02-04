#!/usr/bin/env python3
"""CLI wrapper for analyze command.

Simplified v4.0 command that operates on episode directories.
Uses templates system for customizable analysis.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.core.analyze import AnalyzeEngine, AnalyzeError
from podx.core.classify import classify_episode
from podx.core.quotes import generate_quote_id, render_quotes_markdown, validate_quotes_verbatim
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.prompt_templates import ENHANCED_JSON_SCHEMA
from podx.templates.manager import TemplateError, TemplateManager
from podx.ui import (
    LiveTimer,
    get_llm_models_help,
    get_templates_help,
    prompt_with_help,
    select_episode_interactive,
    show_confirmation,
    validate_llm_model,
    validate_template,
)

logger = get_logger(__name__)
console = Console()

# Default model for analysis
DEFAULT_MODEL = "openai:gpt-5.2"
DEFAULT_TEMPLATE = "general"
DEFAULT_MAP_INSTRUCTIONS = "Extract key points, notable quotes, and insights from this section."


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


def _get_available_templates() -> list[str]:
    """Get list of available template names."""
    try:
        manager = TemplateManager()
        return manager.list_templates()
    except Exception:
        return []


@click.command(context_settings={"max_content_width": 120})
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--model",
    default=None,
    help=f"AI model for analysis (default: {DEFAULT_MODEL})",
)
@click.option(
    "--template",
    default=None,
    help=f"Analysis template (default: {DEFAULT_TEMPLATE})",
)
def main(path: Optional[Path], model: Optional[str], template: Optional[str]):
    """Generate AI analysis of a transcript.

    \b
    Arguments:
      PATH    Episode directory (default: current directory)

    Without PATH, shows interactive episode selection.

    \b
    Models (use 'podx models' for full list):
      openai:gpt-5.2               Latest, highest quality
      openai:gpt-5.1               Previous generation
      openai:gpt-5-mini            Fast and affordable
      openai:gpt-4o                Multimodal capable
      anthropic:claude-opus-4-5    Anthropic highest quality
      anthropic:claude-sonnet-4-5  Anthropic alternative

    \b
    Templates (use 'podx templates' for full list):
      general             Works for any podcast
      interview-1on1      Host interviewing a single guest
      panel-discussion    Multiple hosts/guests discussing
      solo-commentary     Single host sharing thoughts
      technical-deep-dive In-depth technical discussion

    \b
    Examples:
      podx analyze                                         # Interactive selection
      podx analyze ./Show/2024-11-24-ep/                   # Direct path
      podx analyze . --model openai:gpt-4o                 # Current dir, best model
      podx analyze ./ep/ --template panel-discussion       # Panel analysis

    \b
    Notes:
      - Episode must have transcript.json (run 'podx transcribe' first)
      - Requires OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable
    """
    # Get defaults
    default_model = DEFAULT_MODEL
    default_template = DEFAULT_TEMPLATE

    # Track if we're in interactive mode (no PATH provided)
    interactive_mode = path is None

    # Interactive mode if no path provided
    if interactive_mode:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
                require="transcript",
                title="Select episode to analyze",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)

            path = selected["directory"]

            # Warn if this template's analysis already exists
            ep_dir = Path(selected["directory"])
            if template == DEFAULT_TEMPLATE:
                existing_analysis = ep_dir / "analysis.json"
            else:
                existing_analysis = ep_dir / f"analysis.{template}.json"

            if existing_analysis.exists():
                console.print("\n[yellow]This episode already has an analysis.[/yellow]")
                console.print("[dim]Re-analyzing will overwrite the existing file.[/dim]")
                try:
                    confirm = input("Continue? [y/N] ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Cancelled[/dim]")
                    sys.exit(0)
                if confirm not in ("y", "yes"):
                    console.print("[dim]Cancelled[/dim]")
                    sys.exit(0)
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Resolve path (path is guaranteed to be set by now - either from arg or interactive)
    assert path is not None
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

    # Load episode metadata if available
    episode_meta = {}
    meta_path = episode_dir / "episode-meta.json"
    if meta_path.exists():
        try:
            episode_meta = json.loads(meta_path.read_text())
        except Exception:
            pass  # Non-fatal, we'll use defaults

    # Interactive prompts for options (only in interactive mode)
    if interactive_mode:
        # Model prompt/confirmation
        if model is not None:
            show_confirmation("Model", model)
        else:
            model = prompt_with_help(
                help_text=get_llm_models_help(),
                prompt_label="Model",
                default=default_model,
                validator=validate_llm_model,
                error_message="Invalid model. See list above for valid options.",
            )

        # Template prompt/confirmation
        if template is not None:
            show_confirmation("Template", template)
        else:
            template = prompt_with_help(
                help_text=get_templates_help(),
                prompt_label="Template",
                default=default_template,
                validator=validate_template,
                error_message="Invalid template. See list above for valid options.",
            )
    else:
        # Non-interactive: use defaults if not specified
        if model is None:
            model = default_model
        if template is None:
            template = default_template

    # Load template
    try:
        manager = TemplateManager()
        tmpl = manager.load(template)
    except TemplateError:
        console.print(f"[red]Error:[/red] Template '{template}' not found")
        console.print("[dim]Use 'podx templates list' to see available templates[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    # Output path — template-specific to avoid overwriting
    if template == DEFAULT_TEMPLATE:
        analysis_path = episode_dir / "analysis.json"
    else:
        analysis_path = episode_dir / f"analysis.{template}.json"

    # Show what we're doing
    console.print(f"[cyan]Analyzing:[/cyan] {transcript_path.name}")
    console.print(f"[cyan]Template:[/cyan] {template}")
    console.print(f"[cyan]Model:[/cyan] {model}")

    # Start timer
    timer = LiveTimer("Analyzing")
    timer.start()

    try:
        # Parse model string (provider:model_name format)
        provider_name = "openai"
        model_name = model
        if ":" in model:
            provider_name, model_name = model.split(":", 1)

        engine = AnalyzeEngine(
            model=model_name,
            provider_name=provider_name,
            temperature=0.2,
            max_chars_per_chunk=24000,
        )

        # Build transcript text for template
        segments = transcript.get("segments", [])
        transcript_text = "\n".join(
            (
                f"[{s.get('speaker', 'SPEAKER')}] {s.get('text', '')}"
                if s.get("speaker")
                else s.get("text", "")
            )
            for s in segments
        )

        # Count speakers and build speaker list
        speaker_set = set(s.get("speaker") for s in segments if s.get("speaker"))
        speaker_count = len(speaker_set) if speaker_set else 1
        speakers_str = ", ".join(sorted(speaker_set)) if speaker_set else "Unknown"

        # Get episode date
        date_str = episode_meta.get("episode_published", "")
        if date_str:
            try:
                from dateutil import parser as dtparse

                parsed = dtparse.parse(date_str)
                date_str = parsed.strftime("%Y-%m-%d")
            except Exception:
                date_str = date_str[:10] if len(date_str) >= 10 else date_str

        # Build context for template with all possible variables
        context = {
            "transcript": transcript_text,
            "speaker_count": speaker_count,
            "speakers": speakers_str,
            "duration": int(segments[-1].get("end", 0) // 60) if segments else 0,
            "title": episode_meta.get("episode_title", episode_dir.name),
            "show": episode_meta.get("show", "Unknown"),
            "date": date_str or "Unknown",
            "description": episode_meta.get("episode_description", ""),
        }

        # Render template
        system_prompt, user_prompt = tmpl.render(context)

        md, json_data = engine.analyze(
            transcript=transcript,
            system_prompt=system_prompt,
            map_instructions=(tmpl.map_instructions or DEFAULT_MAP_INSTRUCTIONS),
            reduce_instructions=user_prompt,
            want_json=True,
            json_schema=(tmpl.json_schema or ENHANCED_JSON_SCHEMA),
        )

    except AnalyzeError as e:
        timer.stop()
        console.print(f"[red]Analysis Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)

    # For wants_json_only: if the LLM returned pure JSON (no ---JSON--- separator),
    # the engine returns it as `md` with json_data=None. Parse it here.
    if tmpl.wants_json_only and json_data is None:
        try:
            json_data = json.loads(md)
            md = ""  # Will be rendered from JSON below
        except (json.JSONDecodeError, TypeError):
            pass  # Leave md as-is if it's not valid JSON

    # Stop timer
    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Post-processing for quote-miner: verbatim validation + quote_id
    if tmpl.wants_json_only and json_data and "quotes" in json_data:
        json_data["quotes"] = validate_quotes_verbatim(json_data["quotes"], transcript_text)
        for q in json_data["quotes"]:
            q["quote_id"] = generate_quote_id(q)

    # For wants_json_only templates, render markdown from JSON
    if tmpl.wants_json_only and json_data:
        md = render_quotes_markdown(json_data, episode_meta)

    # Build structured output with episode metadata
    duration_minutes = int(segments[-1].get("end", 0) // 60) if segments else 0
    result = {
        "episode": {
            "title": episode_meta.get("episode_title", episode_dir.name),
            "show": episode_meta.get("show", "Unknown"),
            "published": episode_meta.get("episode_published", ""),
            "description": episode_meta.get("episode_description", ""),
            "duration_minutes": duration_minutes,
        },
        "template": template,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "transcript_path": str(transcript_path),
        "results": json_data or {},
        "markdown": md,
    }

    # Save analysis
    analysis_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write episode classification artifact
    try:
        classification = classify_episode(transcript, episode_meta)
        classification_path = episode_dir / "episode-classification.json"
        classification_path.write_text(
            json.dumps(classification, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass  # Non-fatal: classification is advisory

    # Show completion
    console.print(f"\n[green]✓ Analysis complete ({minutes}:{seconds:02d})[/green]")
    results = result.get("results", {})
    if results.get("key_points"):
        console.print(f"  Key points: {len(results['key_points'])}")
    if results.get("quotes"):
        quotes = results["quotes"]
        verbatim_count = sum(1 for q in quotes if q.get("verbatim"))
        console.print(f"  Quotes: {len(quotes)} ({verbatim_count} verbatim)")
    console.print(f"  Output: {analysis_path}")

    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
