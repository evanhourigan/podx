#!/usr/bin/env python3
"""
podx-deepcast: Reads a Transcript JSON (base/aligned/diarized) and produces a rich Markdown brief and optional structured JSON using the OpenAI API via a chunked map-reduce flow.

Detects:
- timestamps? (segments with start/end) -> include timecodes in output
- speakers? (segments have 'speaker') -> include speaker labels when available
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import textwrap
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

# Interactive browser imports (optional)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .podcast_config import get_podcast_config
from .prompt_templates import (
    ENHANCED_JSON_SCHEMA,
    PodcastType,
    build_enhanced_variant,
    detect_podcast_type,
    get_template,
)
from .yaml_config import get_podcast_yaml_config


# utils
def sanitize_model_name(model: str) -> str:
    """Convert AI model name to filename-safe format (dots and hyphens to underscores)."""
    return model.replace(".", "_").replace("-", "_")


def generate_deepcast_filename(
    asr_model: str, ai_model: str, deepcast_type: str, extension: str = "json"
) -> str:
    """Generate deepcast filename in new format: deepcast-{asr}-{ai}-{type}.{ext}"""
    asr_safe = asr_model.replace(".", "_").replace("-", "_")
    ai_safe = sanitize_model_name(ai_model)
    type_safe = deepcast_type.replace(".", "_").replace("-", "_")
    return f"deepcast-{asr_safe}-{ai_safe}-{type_safe}.{extension}"


class LiveTimer:
    """Display a live timer that updates every second in the console."""

    def __init__(self, message: str = "Running"):
        self.message = message
        self.start_time = None
        self.stop_flag = threading.Event()
        self.thread = None

    def _format_time(self, seconds: int) -> str:
        """Format seconds as M:SS."""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"

    def _run(self):
        """Run the timer loop."""
        while not self.stop_flag.is_set():
            elapsed = int(time.time() - self.start_time)
            # Use \r to overwrite the line
            print(f"\r{self.message} ({self._format_time(elapsed)})", end="", flush=True)
            time.sleep(1)

    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        elapsed = time.time() - self.start_time
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=2)
        # Clear the line
        print("\r" + " " * 80 + "\r", end="", flush=True)
        return elapsed


def _truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def parse_deepcast_metadata(deepcast_file: Path) -> Dict[str, str]:
    """
    Parse metadata from deepcast file (JSON first, then filename).
    Returns dict with 'asr_model', 'ai_model', 'deepcast_type', 'transcript_variant'.
    """
    metadata = {
        "asr_model": "unknown",
        "ai_model": "unknown",
        "deepcast_type": "unknown",
        "transcript_variant": "unknown"
    }
    
    # Try to read from JSON file first
    try:
        data = json.loads(deepcast_file.read_text(encoding="utf-8"))
        deepcast_meta = data.get("deepcast_metadata", {})
        if deepcast_meta:
            metadata["asr_model"] = deepcast_meta.get("asr_model", "unknown")
            metadata["ai_model"] = deepcast_meta.get("model", "unknown")
            metadata["deepcast_type"] = deepcast_meta.get("deepcast_type", "unknown")
            metadata["transcript_variant"] = deepcast_meta.get("transcript_variant", "unknown")
            return metadata
    except Exception:
        pass
    
    # Fall back to filename parsing
    # New format: deepcast-{asr}-{ai}-{type}.json
    # Legacy format: deepcast-{ai}.json
    filename = deepcast_file.stem
    
    if filename.count("-") >= 3:  # New format
        parts = filename.split("-", 3)  # Split into at most 4 parts: "deepcast", asr, ai, type
        if len(parts) == 4:
            metadata["asr_model"] = parts[1].replace("_", "-")
            metadata["ai_model"] = parts[2].replace("_", ".")
            metadata["deepcast_type"] = parts[3].replace("_", "-")
    elif filename.startswith("deepcast-"):  # Legacy format
        ai_model = filename[len("deepcast-"):].replace("_", ".")
        metadata["ai_model"] = ai_model
    
    return metadata


def scan_deepcastable_episodes(scan_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan directory for episodes that can be deepcast (have transcripts).
    Returns grouped data structure for complex table display.
    """
    episodes_dict = {}  # Key: (show, date, episode_dir)
    
    # Find all transcript files (diarized, aligned, base)
    transcript_patterns = [
        "transcript-diarized-*.json",
        "diarized-transcript-*.json",
        "transcript-aligned-*.json",
        "aligned-transcript-*.json",
        "transcript-*.json"
    ]
    
    for pattern in transcript_patterns:
        for transcript_file in scan_dir.rglob(pattern):
            try:
                # Skip if it's not a valid ASR transcript file
                filename = transcript_file.stem
                
                # Extract ASR model
                asr_model = None
                transcript_variant = "base"
                
                if filename.startswith("transcript-diarized-"):
                    asr_model = filename[len("transcript-diarized-"):]
                    transcript_variant = "diarized"
                elif filename.startswith("diarized-transcript-"):
                    asr_model = filename[len("diarized-transcript-"):]
                    transcript_variant = "diarized"
                elif filename.startswith("transcript-aligned-"):
                    asr_model = filename[len("transcript-aligned-"):]
                    transcript_variant = "aligned"
                elif filename.startswith("aligned-transcript-"):
                    asr_model = filename[len("aligned-transcript-"):]
                    transcript_variant = "aligned"
                elif filename.startswith("transcript-") and not filename.startswith("transcript-diarized-") and not filename.startswith("transcript-aligned-"):
                    asr_model = filename[len("transcript-"):]
                    transcript_variant = "base"
                else:
                    continue
                
                if not asr_model:
                    continue
                
                # Load transcript for metadata
                transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))
                
                # Get episode directory and metadata
                episode_dir = transcript_file.parent
                episode_meta_file = episode_dir / "episode-meta.json"
                episode_meta = {}
                if episode_meta_file.exists():
                    try:
                        episode_meta = json.loads(episode_meta_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                
                # Extract show and date
                show = episode_meta.get("show") or transcript_data.get("show") or "Unknown"
                date = episode_meta.get("episode_published", "")
                if date:
                    try:
                        from dateutil import parser as dtparse
                        parsed = dtparse.parse(date)
                        date = parsed.strftime("%Y-%m-%d")
                    except Exception:
                        date = date[:10] if len(date) >= 10 else "Unknown"
                else:
                    # Try to extract from directory name
                    date = episode_dir.name if re.match(r"^\d{4}-\d{2}-\d{2}$", episode_dir.name) else "Unknown"
                
                title = episode_meta.get("episode_title") or transcript_data.get("episode_title") or "Unknown"
                
                # Create episode key
                episode_key = (show, date, str(episode_dir))
                
                # Initialize episode entry if not exists
                if episode_key not in episodes_dict:
                    episodes_dict[episode_key] = {
                        "show": show,
                        "date": date,
                        "title": title,
                        "directory": episode_dir,
                        "episode_meta": episode_meta,
                        "asr_models": {},  # Key: asr_model, Value: {variant, file, deepcasts}
                    }
                
                # Add ASR model entry (prefer diarized > aligned > base)
                if asr_model not in episodes_dict[episode_key]["asr_models"]:
                    episodes_dict[episode_key]["asr_models"][asr_model] = {
                        "variant": transcript_variant,
                        "file": transcript_file,
                        "deepcasts": {},  # Key: ai_model, Value: {types: [list of types]}
                    }
                else:
                    # Update if this is a better variant
                    priority = {"diarized": 3, "aligned": 2, "base": 1}
                    current = episodes_dict[episode_key]["asr_models"][asr_model]["variant"]
                    if priority.get(transcript_variant, 0) > priority.get(current, 0):
                        episodes_dict[episode_key]["asr_models"][asr_model]["variant"] = transcript_variant
                        episodes_dict[episode_key]["asr_models"][asr_model]["file"] = transcript_file
                
            except Exception as e:
                continue
    
    # Now scan for existing deepcast files
    for deepcast_file in scan_dir.rglob("deepcast-*.json"):
        try:
            metadata = parse_deepcast_metadata(deepcast_file)
            episode_dir = deepcast_file.parent
            
            # Find matching episode
            for episode_key, episode_data in episodes_dict.items():
                if str(episode_data["directory"]) == str(episode_dir):
                    asr_model = metadata["asr_model"]
                    ai_model = metadata["ai_model"]
                    deepcast_type = metadata["deepcast_type"]
                    
                    # If ASR model doesn't exist, add it
                    if asr_model not in episode_data["asr_models"] and asr_model != "unknown":
                        episode_data["asr_models"][asr_model] = {
                            "variant": metadata.get("transcript_variant", "unknown"),
                            "file": None,
                            "deepcasts": {},
                        }
                    
                    # Add deepcast to the ASR model entry
                    if asr_model in episode_data["asr_models"] or asr_model == "unknown":
                        # For unknown ASR, try to match with any existing ASR model
                        if asr_model == "unknown" and episode_data["asr_models"]:
                            asr_model = list(episode_data["asr_models"].keys())[0]
                        
                        if asr_model in episode_data["asr_models"]:
                            if ai_model not in episode_data["asr_models"][asr_model]["deepcasts"]:
                                episode_data["asr_models"][asr_model]["deepcasts"][ai_model] = []
                            if deepcast_type not in episode_data["asr_models"][asr_model]["deepcasts"][ai_model]:
                                episode_data["asr_models"][asr_model]["deepcasts"][ai_model].append(deepcast_type)
                    break
        except Exception:
            continue
    
    # Convert to list and sort
    episodes_list = list(episodes_dict.values())
    episodes_list.sort(key=lambda e: (e["show"], e["date"]), reverse=False)
    episodes_list.sort(key=lambda e: e["date"], reverse=True)  # Most recent first
    
    return episodes_list


def read_stdin_or_file(inp: Optional[Path]) -> Dict[str, Any]:
    if inp:
        raw = inp.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        raise SystemExit("Provide transcript JSON via --in or stdin.")

    return json.loads(raw)


def hhmmss(sec: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    h, remainder = divmod(sec, 3600)
    m, s = divmod(remainder, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02}"


def segments_to_plain_text(
    segs: List[Dict[str, Any]], with_time: bool, with_speaker: bool
) -> str:
    """Convert segments to plain text with optional timecodes and speaker labels."""
    lines = []
    for s in segs:
        t = f"[{hhmmss(s['start'])}] " if with_time and "start" in s else ""
        spk = f"{s.get('speaker', '')}: " if with_speaker and s.get("speaker") else ""
        txt = s.get("text", "").strip()
        if txt:
            lines.append(f"{t}{spk}{txt}")
    return "\n".join(lines)


def split_into_chunks(text: str, approx_chars: int) -> List[str]:
    """Split text into chunks, trying to keep paragraphs together."""
    if len(text) <= approx_chars:
        return [text]

    paras = text.split("\n")
    chunks = []
    cur = []
    cur_len = 0

    for p in paras:
        L = len(p) + 1  # +1 for newline
        if cur_len + L > approx_chars and cur:
            chunks.append("\n".join(cur))
            cur = []
            cur_len = 0
        cur.append(p)
        cur_len += L

    if cur:
        chunks.append("\n".join(cur))

    return chunks


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


# llm client
def get_client() -> OpenAI:
    if OpenAI is None:
        raise SystemExit("Install OpenAI: pip install openai")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY environment variable")

    base_url = os.getenv("OPENAI_BASE_URL") or None
    return OpenAI(api_key=api_key, base_url=base_url)


def chat_once(
    client: OpenAI, model: str, system: str, user: str, temperature: float = 0.2
) -> str:
    """Make a single chat completion call."""
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


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

    # Get enhanced prompts based on podcast type
    template = get_template(podcast_type)

    # Use enhanced prompts with duration-aware scaling
    system_prompt = template.system_prompt

    # Add custom prompt additions from config (YAML takes precedence)
    if yaml_config and yaml_config.analysis and yaml_config.analysis.custom_prompts:
        system_prompt += f"\n\n{yaml_config.analysis.custom_prompts}"
    elif json_config and json_config.custom_prompt_additions:
        system_prompt += f"\n\n{json_config.custom_prompt_additions}"

    system = (
        system_prompt
        + "\n"
        + build_enhanced_variant(
            has_time, has_spk, podcast_type, episode_duration_minutes
        )
    )

    # Map phase with enhanced instructions
    chunks = split_into_chunks(text, max_chars_per_chunk)

    # If show_prompt_only, build and return prompts without calling API
    if show_prompt_only is not None:
        prompt_display = _build_prompt_display(
            system, template, chunks, want_json, show_prompt_only
        )
        return prompt_display, None

    # Normal flow: call the API
    client = get_client()
    map_notes = []

    for i, chunk in enumerate(chunks):
        prompt = f"{template.map_instructions}\n\nChunk {i+1}/{len(chunks)}:\n\n{chunk}"
        note = chat_once(
            client, model=model, system=system, user=prompt, temperature=temperature
        )
        map_notes.append(note)
        time.sleep(0.1)  # Rate limiting

    # Reduce phase with enhanced instructions
    reduce_prompt = (
        f"{template.reduce_instructions}\n\nChunk notes:\n\n"
        + "\n\n---\n\n".join(map_notes)
    )
    if want_json:
        reduce_prompt += f"\n\n{ENHANCED_JSON_SCHEMA}"

    final = chat_once(
        client, model=model, system=system, user=reduce_prompt, temperature=temperature
    )

    # Extract JSON if present
    if want_json and "---JSON---" in final:
        md, js = final.split("---JSON---", 1)
        js = js.strip()
        # Handle fenced code blocks
        if js.startswith("```json"):
            js = js[7:]
        if js.startswith("```"):
            js = js[3:]
        if js.endswith("```"):
            js = js[:-3]
        js = js.strip()

        try:
            parsed = json.loads(js)
            return build_episode_header(transcript) + md.strip(), parsed
        except json.JSONDecodeError:
            return build_episode_header(transcript) + md.strip(), None

    return build_episode_header(transcript) + final.strip(), None


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
    default=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    help="OpenAI model (gpt-4.1, gpt-4.1-mini) [default: gpt-4.1-mini]",
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
    "--type",
    "podcast_type_str",
    type=click.Choice([t.value for t in PodcastType]),
    help="Podcast type for specialized analysis (auto-detected if not specified)",
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
def main(
    inp: Optional[Path],
    output: Optional[Path],
    model: str,
    temperature: float,
    chunk_chars: int,
    extract_markdown: bool,
    podcast_type_str: Optional[str],
    meta: Optional[Path],
    show_prompt: Optional[str],
):
    """
    podx-deepcast: turn transcripts into a polished Markdown brief (and optional JSON) with summaries key points quotes timestamps and speaker labels when available
    """
    # Validate arguments
    if show_prompt is None and not output:
        raise SystemExit("--output must be provided (unless using --show-prompt)")

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
    if podcast_type_str:
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
        )
        print(prompt_display)
        return

    # Normal execution mode
    md, json_data = deepcast(
        transcript, model, temperature, chunk_chars, want_json, podcast_type
    )

    # Determine transcript variant (diarized > aligned > base)
    transcript_variant = "base"
    if transcript.get("segments") and len(transcript["segments"]) > 0:
        first_seg = transcript["segments"][0]
        if first_seg.get("speaker"):
            transcript_variant = "diarized"
        elif first_seg.get("words"):
            transcript_variant = "aligned"
    
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
        md_filename = generate_deepcast_filename(asr_model_str, model, deepcast_type_str, "md")
        markdown_file = json_output.parent / md_filename if json_output.parent.name else Path(md_filename)
        # Add metadata as HTML comment at the top
        metadata_comment = f"<!-- Metadata: ASR={asr_model_str}, AI={model}, Type={deepcast_type_str}, Transcript={transcript_variant} -->\n\n"
        markdown_with_metadata = metadata_comment + md
        markdown_file.write_text(markdown_with_metadata, encoding="utf-8")

    # Always print to stdout (for pipelines)
    print(json.dumps(unified, ensure_ascii=False))


if __name__ == "__main__":
    main()
