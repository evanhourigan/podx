"""Quote mining utilities — verbatim validation, ID generation, and markdown rendering."""

import hashlib
import re
from typing import Any, Dict, List


def validate_quotes_verbatim(quotes: List[Dict[str, Any]], transcript_text: str) -> List[Dict]:
    """Verify each quote is an exact substring of the transcript.

    Two checks:
    1. Strict: raw quote is exact substring of raw transcript
    2. Light normalization: whitespace collapse + smart quotes only

    If neither matches: verbatim=false. Verbatim quotes are sorted first
    (preserving rank order), non-verbatim last.
    """
    norm_transcript = _light_normalize(transcript_text)

    for q in quotes:
        raw_quote = q.get("quote", "")
        if not raw_quote.strip():
            q["verbatim"] = False
            continue
        # Check 1: strict exact substring
        if raw_quote in transcript_text:
            q["verbatim"] = True
            continue
        # Check 2: light normalization only (whitespace + smart quotes)
        norm_quote = _light_normalize(raw_quote)
        q["verbatim"] = norm_quote in norm_transcript

    # Sort: verbatim first (preserving rank order), non-verbatim last
    verbatim = [q for q in quotes if q.get("verbatim")]
    suspect = [q for q in quotes if not q.get("verbatim")]
    return verbatim + suspect


def _light_normalize(text: str) -> str:
    """Whitespace collapse + smart quote normalization only.

    NO case folding. NO heavy punctuation stripping.
    """
    # Smart quotes -> straight quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Em/en dashes -> hyphen
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_quote_id(quote: Dict[str, Any]) -> str:
    """Generate a stable hash ID from speaker + start + quote text."""
    key = f"{quote.get('speaker', '')}|{quote.get('start', '')}|{quote.get('quote', '')}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def render_quotes_markdown(json_data: Dict[str, Any], episode_meta: Dict[str, Any]) -> str:
    """Render quote-miner JSON results as markdown.

    Produces a complete markdown document with episode metadata header
    and ranked quotes with speaker, timestamp, category, and context.
    """
    lines: List[str] = []

    # Episode header
    title = episode_meta.get("episode_title", "Unknown Episode")
    show = episode_meta.get("show", "Unknown Show")
    published = episode_meta.get("episode_published", "")
    summary = json_data.get("episode_summary", "")

    lines.append(f"# Quote Mining: {title}")
    lines.append("")

    meta_parts = []
    if show != "Unknown Show":
        meta_parts.append(f"**Show:** {show}")
    if published:
        meta_parts.append(f"**Date:** {published}")
    total_candidates = json_data.get("total_candidates_found")
    if total_candidates:
        meta_parts.append(f"**Candidates found:** {total_candidates}")
    if meta_parts:
        lines.append(" | ".join(meta_parts))
        lines.append("")

    if summary:
        lines.append(f"*{summary}*")
        lines.append("")

    # Quotes section
    quotes = json_data.get("quotes", [])
    if not quotes:
        lines.append("*No quotes extracted.*")
        return "\n".join(lines)

    verbatim_quotes = [q for q in quotes if q.get("verbatim")]
    suspect_quotes = [q for q in quotes if not q.get("verbatim")]

    lines.append(
        f"## Top Quotes ({len(verbatim_quotes)} verbatim, {len(suspect_quotes)} unverified)"
    )
    lines.append("")

    for q in quotes:
        rank = q.get("rank", "")
        quote_title = q.get("title", "")
        category = q.get("category", "")
        speaker = q.get("speaker", "Unknown")
        start = q.get("start", "")
        end = q.get("end", "")
        context = q.get("context", "")
        quote_text = q.get("quote", "")
        why = q.get("why_it_works", "")
        use_case = q.get("use_case", "")
        tags = q.get("tags", [])
        verbatim = q.get("verbatim", False)

        # Header with rank, title, and category
        category_str = f" ({category})" if category else ""
        verbatim_marker = "" if verbatim else " [unverified]"
        lines.append(f"### {rank}. {quote_title}{category_str}{verbatim_marker}")
        lines.append("")

        # Quote block with attribution
        timestamp_str = ""
        if start and end:
            timestamp_str = f" [{start}\u2013{end}]"
        elif start:
            timestamp_str = f" [{start}]"
        lines.append(f'> "{quote_text}" \u2014 {speaker}{timestamp_str}')
        lines.append("")

        # Context
        if context:
            lines.append(f"**Context:** {context}")
            lines.append("")

        # Why it works
        if why:
            lines.append(f"**Why it works:** {why}")
            lines.append("")

        # Use case
        if use_case:
            lines.append(f"**Use case:** {use_case}")
            lines.append("")

        # Tags
        if tags:
            lines.append(f"**Tags:** {', '.join(tags)}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Summary stats
    speakers = json_data.get("speakers", [])
    if speakers:
        lines.append(f"**Speakers:** {', '.join(speakers)}")
        lines.append("")

    return "\n".join(lines)
