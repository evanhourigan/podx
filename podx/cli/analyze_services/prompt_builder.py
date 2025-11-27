"""Prompt building utilities for analyze command."""

import textwrap
from typing import Any, Dict, List

from podx.prompt_templates import ENHANCED_JSON_SCHEMA


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
