#!/usr/bin/env python3
"""CLI wrapper for deepcast command.

Thin Click wrapper that uses core.deepcast.DeepcastEngine for map-reduce execution.
Handles CLI arguments, prompt templates, podcast config, interactive mode, and I/O.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click

from podx.core.deepcast import (
    DeepcastEngine,
    DeepcastError,
    segments_to_plain_text,
    split_into_chunks,
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

# Interactive browser imports (optional)
try:
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Import UI components
try:
    from podx.ui import (
        DeepcastBrowser,
        LiveTimer,
        flatten_episodes_to_rows,
        scan_deepcastable_episodes,
    )
except ImportError:
    DeepcastBrowser = None  # type: ignore
    flatten_episodes_to_rows = None  # type: ignore
    scan_deepcastable_episodes = None  # type: ignore
    LiveTimer = None  # type: ignore

from podx.podcast_config import get_podcast_config
from podx.prompt_templates import (
    ENHANCED_JSON_SCHEMA,
    PodcastType,
    build_enhanced_variant,
    detect_podcast_type,
    get_template,
    map_to_canonical,
)
from podx.utils import sanitize_model_name
from podx.yaml_config import get_podcast_yaml_config

# Canonical deepcast types presented to users
CANONICAL_TYPES: list[PodcastType] = [
    PodcastType.INTERVIEW_GUEST_FOCUSED,  # interview_guest_focused
    PodcastType.PANEL_DISCUSSION,         # multi_guest_panel
    PodcastType.SOLO_COMMENTARY,          # host_analysis_mode
    PodcastType.GENERAL,                  # general
]


# Alias deepcast types that inject prompt hints but map to canonical templates
# These are convenient names users can pass via --type or YAML; internally we
# canonicalize to one of the four core types while augmenting the prompt.
ALIAS_TYPES: dict[str, dict[str, Any]] = {
    "host_moderated_panel": {
        "canonical": PodcastType.PANEL_DISCUSSION,
        "prompt": (
            "- Use the HOST's topic introductions as section headings.\n"
            "- Under each section, synthesize panelists' viewpoints (agreements, disagreements, notable quotes).\n"
            "- Attribute quotes with speaker labels; include timestamps when useful."
        ),
    },
    "cohost_commentary": {
        "canonical": PodcastType.PANEL_DISCUSSION,
        "prompt": (
            "- Treat both hosts as equal participants (no host/guest framing).\n"
            "- Synthesize joint reasoning, back-and-forth refinements, and final takeaways.\n"
            "- Emphasize consensus vs. divergences; include brief quotes with timestamps."
        ),
    },
}


# utils
def generate_deepcast_filename(
    asr_model: str,
    ai_model: str,
    deepcast_type: str,
    extension: str = "json",
    with_timestamp: bool = True,
) -> str:
    """Generate deepcast filename: deepcast-{asr}-{ai}-{type}[-YYYYMMDD-HHMMSS].{ext}"""
    asr_safe = asr_model.replace(".", "_").replace("-", "_")
    ai_safe = sanitize_model_name(ai_model)
    type_safe = deepcast_type.replace(".", "_").replace("-", "_")
    ts = (
        "-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        if with_timestamp
        else ""
    )
    return f"deepcast-{asr_safe}-{ai_safe}-{type_safe}{ts}.{extension}"


def read_stdin_or_file(inp: Optional[Path]) -> Dict[str, Any]:
    if inp:
        raw = inp.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        raise SystemExit("Provide transcript JSON via --in or stdin.")

    return json.loads(raw)


# prompting
SYSTEM_BASE = "You are a meticulous editorial assistant for podcast transcripts."


def build_episode_header(transcript: Dict[str, Any]) -> str:
    """Build episode metadata header from transcript.

    Prefer pipeline metadata field names, fallback to older/alternative names.
    """
    show_name = transcript.get("show") or transcript.get("show_name", "Unknown Show")
    episode_title = (
        transcript.get("episode_title") or transcript.get("title") or "Unknown Episode"
    )
    release_date = (
        transcript.get("episode_published")
        or transcript.get("release_date")
        or "Unknown Date"
    )

    return f"""# {show_name}
## {episode_title}
**Released:** {release_date}

---

"""


def build_prompt_variant(has_time: bool, has_spk: bool) -> str:
    time_text = (
        "- When quoting, include [HH:MM:SS] timecodes from the nearest preceding segment.\n"
        if has_time
        else "- When quoting, omit timecodes because they are not available.\n"
    )
    spk_text = (
        "- Preserve speaker labels like [SPEAKER_00] or actual names if provided; otherwise omit.\n"
        if has_spk
        else "- Speaker labels are not available; write neutrally.\n"
    )

    return textwrap.dedent(
        f"""
    Write concise, information-dense notes from a podcast transcript.

    {time_text}
    {spk_text}

    Output high-quality Markdown with these sections (only include a section if content exists):

    # Episode Summary (6-12 sentences)
    ## Key Points (bulleted list of 12-24 items, each two to three sentences, with relevant context also specified in addition to the sentences.)
    ## Gold Nuggets (medium sized bulleted list of 6-12 items of surprising/novel insights, these should be also two sentences but specify relevant context as well.)
    ## Notable Quotes (each on its own line; include timecodes and speakers when available)
    ## Action Items / Resources (bullets)
    ## Timestamps Outline (10-20 coarse checkpoints)

    Be faithful to the text; do not invent facts. Prefer short paragraphs and crisp bullets.
    If jargon or proper nouns appear, keep them verbatim.
    """
    ).strip()


MAP_INSTRUCTIONS = textwrap.dedent(
    """
Extract key information from this transcript CHUNK.

Return:
- 3-6 Key Points
- 2-5 Gold Nuggets
- 3-10 Notable Quotes (increased to capture more key insights and gold nuggets)
- Any Action Items / Resources

Return a tight Markdown; do not include a global summary—chunk only.
"""
).strip()

REDUCE_INSTRUCTIONS = textwrap.dedent(
    """
Synthesize these chunk-level notes into a single, cohesive Markdown brief.

Deduplicate and organize cleanly. Follow the earlier rules for structure and formatting.
"""
).strip()

JSON_SCHEMA_HINT = textwrap.dedent(
    """
After the Markdown, also prepare a concise JSON object with this structure:

{
  "summary": "string",
  "key_points": ["string"],
  "gold_nuggets": ["string"],
  "quotes": [{"quote": "string", "time": "string", "speaker": "string"}],
  "actions": ["string"],
  "outline": [{"label": "string", "time": "string"}]
}

Return the JSON after the Markdown, separated by a line containing: ---JSON---
"""
).strip()


def select_deepcast_type(row: Dict[str, Any], console: Console) -> Optional[str]:
    """Prompt user to select deepcast type."""
    # Get default type from config if available
    episode = row["episode"]
    show_name = episode.get("show", "")
    default_type = None

    # Try to get default from podcast config
    try:
        from .podcast_config import get_podcast_config
        config = get_podcast_config(show_name)
        if config and hasattr(config, 'default_type'):
            default_type = config.default_type
    except Exception:
        pass

    # If no config default, use "general"
    if not default_type:
        default_type = "general"

    # List canonical deepcast types plus friendly aliases
    all_types = [t.value for t in CANONICAL_TYPES] + list(ALIAS_TYPES.keys())

    console.print("\n[bold cyan]Select a deepcast type:[/bold cyan]")
    for idx, dtype in enumerate(all_types, start=1):
        marker = " ← Default" if dtype == default_type else ""
        console.print(f"  {idx:2}  {dtype}{marker}")

    choice = input(f"\n👉 Select deepcast type (1-{len(all_types)}) or Q to cancel: ").strip()

    if choice.upper() in ["Q", "QUIT", "EXIT"]:
        return None

    if not choice:
        return default_type

    try:
        selection = int(choice)
        if 1 <= selection <= len(all_types):
            return all_types[selection - 1]
        else:
            console.print(f"[red]Invalid choice. Using default: {default_type}[/red]")
            return default_type
    except ValueError:
        console.print(f"[red]Invalid input. Using default: {default_type}[/red]")
        return default_type


def select_ai_model(console: Console) -> Optional[str]:
    """Prompt user to select AI model."""
    default_model = "gpt-4.1-mini"

    choice = input(f"\n👉 Select AI model (e.g. gpt-4.1, gpt-4o, claude-4-sonnet; default: {default_model}) or Q to cancel: ").strip()

    if choice.upper() in ["Q", "QUIT", "EXIT"]:
        return None

    return choice if choice else default_model


def _build_prompt_display(
    system: str, template: Any, chunks: List[str], want_json: bool, mode: str = "all"
) -> str:
    """Build a formatted display of prompts that would be sent to the LLM.

    Args:
        system: The system prompt
        template: The prompt template
        chunks: List of text chunks
        want_json: Whether JSON output is requested
        mode: Display mode - "all" shows all prompts, "system_only" shows only system prompt

    Returns:
        Formatted string displaying the requested prompts
    """
    lines = []
    lines.append("=" * 80)
    lines.append("SYSTEM PROMPT (used for all API calls)")
    lines.append("=" * 80)
    lines.append(system)
    lines.append("")

    # If system_only mode, stop here
    if mode == "system_only":
        lines.append("=" * 80)
        lines.append("END OF PROMPTS")
        lines.append("=" * 80)
        return "\n".join(lines)

    # Otherwise, show all prompts (mode == "all")
    lines.append("=" * 80)
    lines.append(f"MAP PHASE PROMPTS ({len(chunks)} chunks)")
    lines.append("=" * 80)
    lines.append("")

    for i, chunk in enumerate(chunks):
        lines.append("-" * 80)
        lines.append(f"MAP PROMPT {i+1}/{len(chunks)}")
        lines.append("-" * 80)
        prompt = f"{template.map_instructions}\n\nChunk {i+1}/{len(chunks)}:\n\n{chunk}"
        lines.append(prompt)
        lines.append("")

    lines.append("=" * 80)
    lines.append("REDUCE PHASE PROMPT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"{template.reduce_instructions}\n\nChunk notes:\n\n")
    lines.append(
        "[NOTE: In actual execution, this would contain the LLM responses from all map phase calls]"
    )
    lines.append("")

    if want_json:
        lines.append("")
        lines.append("JSON SCHEMA REQUEST:")
        lines.append("-" * 80)
        lines.append(ENHANCED_JSON_SCHEMA)

    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF PROMPTS")
    lines.append("=" * 80)

    return "\n".join(lines)


# main pipeline
def deepcast(
    transcript: Dict[str, Any],
    model: str,
    temperature: float,
    max_chars_per_chunk: int,
    want_json: bool,
    podcast_type: Optional[PodcastType] = None,
    show_prompt_only: Optional[str] = None,
    extra_system_instructions: Optional[str] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Enhanced deepcast pipeline with intelligent prompt selection.

    Args:
        transcript: Transcript data to analyze
        model: OpenAI model name
        temperature: Model temperature
        max_chars_per_chunk: Max characters per chunk for map phase
        want_json: Whether to request JSON output
        podcast_type: Type of podcast for specialized analysis
        show_prompt_only: If set to "all" or "system_only", return prompts without calling API

    Returns:
        Tuple of (markdown_output, json_data) or (prompts_display, None) if show_prompt_only is set
    """
    segs = transcript.get("segments") or []
    has_time = any("start" in s and "end" in s for s in segs)
    has_spk = any("speaker" in s for s in segs)

    # Calculate episode duration for adaptive scaling
    episode_duration_minutes = None
    if segs and has_time:
        try:
            last_segment = max(segs, key=lambda s: s.get("end", 0))
            episode_duration_minutes = int(last_segment.get("end", 0) / 60)
        except (ValueError, TypeError):
            pass

    # Convert to plain text
    text = segments_to_plain_text(segs, has_time, has_spk)
    if not text.strip():
        text = transcript.get("text", "")
    if not text.strip():
        raise SystemExit("No transcript text found in input")

    # Check for podcast-specific configuration (YAML first, then JSON)
    show_name = transcript.get("show") or transcript.get("show_name", "")
    yaml_config = get_podcast_yaml_config(show_name) if show_name else None
    json_config = get_podcast_config(show_name) if show_name else None

    # Auto-detect podcast type if not specified, with config override (YAML takes precedence)
    if podcast_type is None:
        if yaml_config and yaml_config.analysis and yaml_config.analysis.type:
            podcast_type = yaml_config.analysis.type
        elif json_config and json_config.podcast_type:
            podcast_type = json_config.podcast_type
        else:
            podcast_type = detect_podcast_type(transcript)

    # Canonicalize type to one of the three core templates
    podcast_type = map_to_canonical(podcast_type)
    template = get_template(podcast_type)

    # Use enhanced prompts with duration-aware scaling
    system_prompt = template.system_prompt

    # Add custom prompt additions from config (YAML takes precedence)
    if yaml_config and yaml_config.analysis and yaml_config.analysis.custom_prompts:
        system_prompt += f"\n\n{yaml_config.analysis.custom_prompts}"
    elif json_config and json_config.custom_prompt_additions:
        system_prompt += f"\n\n{json_config.custom_prompt_additions}"

    # If YAML selected an alias type, inject its extra guidance too
    try:
        if yaml_config and getattr(yaml_config, "analysis", None):
            y_type = getattr(yaml_config.analysis, "type", None)
            if isinstance(y_type, str) and y_type in ALIAS_TYPES:
                system_prompt += f"\n\n{ALIAS_TYPES[y_type]['prompt']}"
    except Exception:
        pass

    # Add any ad-hoc extra instructions (e.g., from alias types)
    if extra_system_instructions:
        system_prompt += f"\n\n{extra_system_instructions}"

    system = (
        system_prompt
        + "\n"
        + build_enhanced_variant(
            has_time, has_spk, podcast_type, episode_duration_minutes
        )
    )

    # If show_prompt_only, build and return prompts without calling API
    if show_prompt_only is not None:
        chunks = split_into_chunks(text, max_chars_per_chunk)
        prompt_display = _build_prompt_display(
            system, template, chunks, want_json, show_prompt_only
        )
        return prompt_display, None

    # Use core deepcast engine (pure business logic)
    try:
        engine = DeepcastEngine(
            model=model,
            temperature=temperature,
            max_chars_per_chunk=max_chars_per_chunk,
        )
        md, json_data = engine.deepcast(
            transcript=transcript,
            system_prompt=system,
            map_instructions=template.map_instructions,
            reduce_instructions=template.reduce_instructions,
            want_json=want_json,
            json_schema=ENHANCED_JSON_SCHEMA if want_json else None,
        )
    except DeepcastError as e:
        raise SystemExit(str(e))

    # Add episode header to markdown
    return build_episode_header(transcript) + md, json_data


@click.command()
@click.option(
    "--input",
    "-i",
    "inp",
    type=click.Path(exists=True, path_type=Path),
    help="Input transcript JSON file",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output unified JSON file (contains both summary and brief)",
)
@click.option(
    "--model",
    default=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1"),
    help="OpenAI model (gpt-4.1, gpt-4.1-mini) [default: gpt-4.1]",
)
@click.option(
    "--temperature",
    default=lambda: float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
    type=float,
    help="Model temperature [default: 0.2]",
)
@click.option(
    "--chunk-chars",
    default=24000,
    type=int,
    help="Approximate chars per chunk [default: 24000]",
)
@click.option(
    "--extract-markdown",
    is_flag=True,
    help="Also write raw markdown to a separate .md file",
)
@click.option(
    "--pdf",
    "export_pdf",
    is_flag=True,
    help="Also write a PDF rendering of the markdown (requires pandoc)",
)
@click.option(
    "--type",
    "podcast_type_str",
    type=click.Choice([t.value for t in CANONICAL_TYPES] + list(ALIAS_TYPES.keys())),
    help="Podcast type (canonical or alias): interview_guest_focused | panel_discussion | solo_commentary | general | host_moderated_panel | cohost_commentary",
)
@click.option(
    "--meta",
    type=click.Path(exists=True, path_type=Path),
    help="Episode metadata JSON file (to populate show name, episode title, date)",
)
@click.option(
    "--show-prompt",
    type=click.Choice(["all", "system_only"], case_sensitive=False),
    is_flag=False,
    flag_value="all",
    default=None,
    help="Display the LLM prompts that would be sent (without actually calling the LLM) and exit. "
    "Options: 'all' (default, shows all prompts) or 'system_only' (shows only system prompt)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select episodes for deepcast",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for episodes (default: current directory)",
)
def main(
    inp: Optional[Path],
    output: Optional[Path],
    model: str,
    temperature: float,
    chunk_chars: int,
    extract_markdown: bool,
    export_pdf: bool,
    podcast_type_str: Optional[str],
    meta: Optional[Path],
    show_prompt: Optional[str],
    interactive: bool,
    scan_dir: Path,
):
    """
    podx-deepcast: turn transcripts into a polished Markdown brief (and optional JSON) with summaries key points quotes timestamps and speaker labels when available
    """
    # Handle interactive mode
    if interactive:
        from podx.ui import select_episode_with_tui

        # Step 1: Select episode using TUI
        try:
            episode, episode_meta = select_episode_with_tui(
                scan_dir=Path(scan_dir),
                show_filter=None,
            )
        except SystemExit:
            print("❌ Episode selection cancelled")
            sys.exit(0)

        if not episode:
            print("❌ Episode selection cancelled")
            sys.exit(0)

        # Find available transcripts for this episode
        episode_dir = episode["directory"]
        available_transcripts = []
        transcript_patterns = [
            "transcript-diarized-*.json",
            "diarized-transcript-*.json",
            "transcript-aligned-*.json",
            "aligned-transcript-*.json",
            "transcript-*.json"
        ]

        for pattern in transcript_patterns:
            for transcript_file in episode_dir.glob(pattern):
                filename = transcript_file.stem
                # Skip non-transcript files
                if any(keyword in filename for keyword in ["preprocessed"]):
                    continue
                available_transcripts.append(transcript_file)
                break  # Take first match for this pattern

        if not available_transcripts:
            print(f"❌ No transcripts found for episode: {episode.get('title', 'Unknown')}")
            sys.exit(1)

        # Use the most processed transcript (diarized > aligned > base)
        inp = available_transcripts[0]

        # Extract ASR model from filename
        filename = inp.stem
        asr_model_raw = "unknown"
        if filename.startswith("transcript-diarized-"):
            asr_model_raw = filename[len("transcript-diarized-"):]
        elif filename.startswith("diarized-transcript-"):
            asr_model_raw = filename[len("diarized-transcript-"):]
        elif filename.startswith("transcript-aligned-"):
            asr_model_raw = filename[len("transcript-aligned-"):]
        elif filename.startswith("aligned-transcript-"):
            asr_model_raw = filename[len("aligned-transcript-"):]
        elif filename.startswith("transcript-"):
            asr_model_raw = filename[len("transcript-"):]

        # Step 2: Select deepcast type
        print("\n📝 Select deepcast type:")
        show_name = episode.get("show", "")
        default_type = "general"

        # Try to get default from podcast config
        try:
            config_obj = get_podcast_config(show_name)
            if config_obj and hasattr(config_obj, 'default_type'):
                default_type = config_obj.default_type
        except Exception:
            pass

        all_types = [t.value for t in CANONICAL_TYPES] + list(ALIAS_TYPES.keys())
        for idx, dtype in enumerate(all_types, start=1):
            marker = " ← Default" if dtype == default_type else ""
            print(f"  {idx:2}  {dtype}{marker}")

        choice = input(f"\n👉 Select deepcast type (1-{len(all_types)}, Enter for default, Q to cancel): ").strip()

        if choice.upper() in ["Q", "QUIT", "EXIT"]:
            print("❌ Deepcast type selection cancelled")
            sys.exit(0)

        if not choice:
            deepcast_type = default_type
        else:
            try:
                selection = int(choice)
                if 1 <= selection <= len(all_types):
                    deepcast_type = all_types[selection - 1]
                else:
                    print(f"⚠️  Invalid choice. Using default: {default_type}")
                    deepcast_type = default_type
            except ValueError:
                print(f"⚠️  Invalid input. Using default: {default_type}")
                deepcast_type = default_type

        # Step 3: Select AI model
        default_model = "gpt-4.1-mini"
        choice = input(f"\n👉 Select AI model (e.g. gpt-4.1, gpt-4o, claude-4-sonnet; Enter for {default_model}, Q to cancel): ").strip()

        if choice.upper() in ["Q", "QUIT", "EXIT"]:
            print("❌ AI model selection cancelled")
            sys.exit(0)

        ai_model = choice if choice else default_model
        model = ai_model  # Override the default model parameter

        # Step 4: Check if deepcast already exists and confirm overwrite
        output_filename = generate_deepcast_filename(asr_model_raw, ai_model, deepcast_type, "json", with_timestamp=True)
        output = episode_dir / output_filename

        if output.exists():
            print(f"\n⚠️  Deepcast already exists: {output.name}")
            confirm = input("Re-run deepcast anyway? (yes/no, Q to quit): ").strip().lower()
            if confirm in ["q", "quit", "exit"]:
                print("❌ Deepcast cancelled")
                sys.exit(0)
            if confirm not in ["yes", "y"]:
                print("❌ Deepcast cancelled")
                sys.exit(0)

        # Step 5: Ask about markdown generation
        md_choice = input("\n👉 Generate markdown output file? y/N or Q to cancel: ").strip().lower()
        if md_choice in ["q", "quit", "exit"]:
            print("❌ Deepcast cancelled")
            sys.exit(0)
        extract_markdown = md_choice in ["yes", "y"]

        # Step 5b: Ask about PDF generation unless already requested via --pdf
        if not export_pdf:
            pdf_choice = input("\n👉 Also generate a PDF (via pandoc)? y/N or Q to cancel: ").strip().lower()
            if pdf_choice in ["q", "quit", "exit"]:
                print("❌ Deepcast cancelled")
                sys.exit(0)
            export_pdf = pdf_choice in ["yes", "y"]

        # Load the transcript file (already found earlier)
        if not inp or not inp.exists():
            print("❌ Transcript file not found")
            sys.exit(1)

        transcript = json.loads(inp.read_text(encoding="utf-8"))
        podcast_type_str = deepcast_type
    else:
        # Non-interactive mode: validate arguments
        if show_prompt is None and not output:
            raise SystemExit("--output must be provided (unless using --show-prompt or --interactive)")

        transcript = read_stdin_or_file(inp)
    want_json = True  # Always generate JSON for unified output

    # Load and merge episode metadata if provided
    if meta:
        episode_meta = json.loads(meta.read_text())
        # Merge metadata into transcript for show name, episode title, etc.
        transcript.update(
            {
                "show": episode_meta.get("show", transcript.get("show")),
                "episode_title": episode_meta.get(
                    "episode_title", transcript.get("episode_title")
                ),
                "episode_published": episode_meta.get(
                    "episode_published", transcript.get("episode_published")
                ),
                "episode_description": episode_meta.get(
                    "episode_description", transcript.get("episode_description")
                ),
            }
        )

    # Convert podcast type string to enum
    podcast_type = None
    alias_used: Optional[str] = None
    extra_instructions: Optional[str] = None
    if podcast_type_str:
        if podcast_type_str in ALIAS_TYPES:
            alias_used = podcast_type_str
            alias_cfg = ALIAS_TYPES[podcast_type_str]
            podcast_type = alias_cfg["canonical"]
            extra_instructions = alias_cfg["prompt"]
        else:
            podcast_type = PodcastType(podcast_type_str)

    # Handle --show-prompt mode: display prompts and exit
    if show_prompt is not None:
        prompt_display, _ = deepcast(
            transcript,
            model,
            temperature,
            chunk_chars,
            want_json,
            podcast_type,
            show_prompt_only=show_prompt,
            extra_system_instructions=extra_instructions,
        )
        print(prompt_display)
        return

    # Check for OpenAI library before proceeding
    if OpenAI is None:
        if interactive and RICH_AVAILABLE:
            console = Console()
            console.print("\n[red]❌ Error: OpenAI library not installed[/red]")
            console.print("[yellow]Install with: pip install openai[/yellow]")
        raise SystemExit("Install OpenAI: pip install openai")

    # Normal execution mode
    # Start live timer in interactive mode
    timer = None
    if interactive and RICH_AVAILABLE:
        console = Console()
        timer = LiveTimer("Generating deepcast")
        timer.start()

    try:
        md, json_data = deepcast(
            transcript,
            model,
            temperature,
            chunk_chars,
            want_json,
            podcast_type,
            extra_system_instructions=extra_instructions,
        )
    except SystemExit:
        if timer:
            timer.stop()
        raise
    except Exception as e:
        if timer:
            timer.stop()
        if interactive and RICH_AVAILABLE:
            console.print(f"\n[red]❌ Error during deepcast generation: {e}[/red]")
        raise

    # Stop timer and show completion message in interactive mode
    if timer:
        elapsed = timer.stop()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        console.print(f"[green]✓ Deepcast completed in {minutes}:{seconds:02d}[/green]")

    # Determine transcript variant (diarized > aligned > base)
    transcript_variant = "base"
    if transcript.get("segments") and len(transcript["segments"]) > 0:
        first_seg = transcript["segments"][0]
        if first_seg.get("speaker"):
            transcript_variant = "diarized"
        elif first_seg.get("words"):
            transcript_variant = "aligned"

    # If alias not provided via CLI, detect alias from YAML config so we can record it
    if alias_used is None:
        try:
            show_name = transcript.get("show") or transcript.get("show_name", "")
            yaml_cfg = get_podcast_yaml_config(show_name) if show_name else None
            if (
                yaml_cfg
                and getattr(yaml_cfg, "analysis", None)
                and getattr(yaml_cfg.analysis, "type", None) in ALIAS_TYPES
            ):
                alias_used = yaml_cfg.analysis.type  # type: ignore[attr-defined]
        except Exception:
            pass

    # Unified JSON output
    unified = {
        "markdown": md,
        "metadata": transcript,  # Original transcript metadata
        "deepcast_metadata": {
            "model": model,
            "temperature": temperature,
            "podcast_type": podcast_type.value if podcast_type else "general",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "asr_model": transcript.get("asr_model"),  # Store ASR model from transcript
            "transcript_variant": transcript_variant,  # Store transcript type
            "deepcast_type": podcast_type.value if podcast_type else "general",  # Explicit type field
            "deepcast_alias": alias_used or None,
        },
    }
    if json_data:
        unified.update(json_data)  # Merge structured analysis

    # Determine output path
    # For non-interactive mode, user can provide explicit output or we can derive it
    # For now, keep requiring output parameter (interactive mode will set it)
    if output:
        json_output = output
    else:
        # This shouldn't happen in current CLI (output is required), but prepare for interactive
        asr_model_str = transcript.get("asr_model", "unknown")
        deepcast_type_str = podcast_type.value if podcast_type else "general"
        json_filename = generate_deepcast_filename(asr_model_str, model, deepcast_type_str, "json")
        json_output = Path(json_filename)

    # Save to file
    json_output.write_text(
        json.dumps(unified, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Extract markdown to separate file if requested
    if extract_markdown:
        asr_model_str = transcript.get("asr_model", "unknown")
        deepcast_type_str = podcast_type.value if podcast_type else "general"
        md_filename = generate_deepcast_filename(asr_model_str, model, deepcast_type_str, "md", with_timestamp=True)
        markdown_file = json_output.parent / md_filename if json_output.parent.name else Path(md_filename)
        # Add metadata as HTML comment at the top
        metadata_comment = f"<!-- Metadata: ASR={asr_model_str}, AI={model}, Type={deepcast_type_str}, Transcript={transcript_variant} -->\n\n"
        markdown_with_metadata = metadata_comment + md
        markdown_file.write_text(markdown_with_metadata, encoding="utf-8")

    # Optionally export a PDF using pandoc (reads markdown from memory)
    if export_pdf:
        asr_model_str = transcript.get("asr_model", "unknown")
        deepcast_type_str = podcast_type.value if podcast_type else "general"
        pdf_filename = generate_deepcast_filename(asr_model_str, model, deepcast_type_str, "pdf", with_timestamp=True)
        pdf_file = json_output.parent / pdf_filename if json_output.parent.name else Path(pdf_filename)

        pandoc_path = shutil.which("pandoc")
        if not pandoc_path:
            print("⚠️  pandoc not found. Install with: brew install pandoc", file=sys.stderr)
        else:
            try:
                # Feed markdown via stdin to pandoc
                subprocess.run(
                    [pandoc_path, "-f", "markdown", "-t", "pdf", "-o", str(pdf_file)],
                    input=md,
                    text=True,
                    check=True,
                )
                # Success handled in final completion message below
                pass
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to generate PDF with pandoc: {e}", file=sys.stderr)

    # Print to stdout (for pipelines) - but not in interactive mode
    if not interactive:
        print(json.dumps(unified, ensure_ascii=False))
    else:
        # In interactive mode, show detailed completion message
        print("\n✅ Deepcast complete")
        print(f"   Type: {deepcast_type}")
        print(f"   AI Model: {model}")
        print("   Outputs:")
        print(f"      🤖 JSON: {json_output}")
        if extract_markdown:
            print(f"      📄 Markdown: {markdown_file}")
        if export_pdf and pdf_file.exists():
            print(f"      📕 PDF: {pdf_file}")


if __name__ == "__main__":
    main()
