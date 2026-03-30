"""Obsidian vault output for podcast knowledge management.

Generates an interconnected Obsidian vault from podcast analyses:
- Episode notes with full analysis
- Atomic insight notes extracted from knowledge-oracle output
- Speaker notes that accumulate across episodes
- Topic and Domain MOC (Map of Content) notes

Pure business logic — no UI, no Notion dependencies, just file I/O.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logging import get_logger

logger = get_logger(__name__)

# Folders in the vault
FOLDERS = ["Episodes", "Insights", "Topics", "Speakers", "Domains", "Reflections"]

# Characters unsafe in filenames
UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


@dataclass
class ObsidianConfig:
    """Configuration for Obsidian vault output."""

    vault_path: Path = field(
        default_factory=lambda: Path.home() / "obsidian-vault" / "podcast-brain"
    )
    auto_commit: bool = True


@dataclass
class InsightRecord:
    """A single atomic insight extracted from analysis."""

    title: str
    body: str
    section_type: str  # framework, contrarian, strategy, quote, connection, takeaway
    speaker: Optional[str]
    topics: List[str]
    domains: List[str]
    actionable: bool
    source_episode: str  # Episode note name (without .md) for wikilinks
    date: str  # YYYY-MM-DD


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def publish_to_obsidian(
    vault_path: Path,
    episode_meta: Dict[str, Any],
    transcript: Optional[Dict[str, Any]],
    format_md: Optional[str],
    oracle_md: Optional[str],
    classification: Optional[Dict[str, Any]],
    model: str,
    asr_model: Optional[str] = None,
    auto_commit: bool = True,
) -> None:
    """Publish episode analysis to an Obsidian vault.

    Creates/updates episode note, insight notes, speaker notes,
    and topic/domain MOCs.

    Args:
        vault_path: Root path of the Obsidian vault
        episode_meta: Episode metadata dict
        transcript: Transcript dict (optional, for context)
        format_md: Format template analysis markdown
        oracle_md: Knowledge-oracle analysis markdown
        classification: Parsed classification dict from oracle output
        model: LLM model used for analysis
        asr_model: ASR model used for transcription
        auto_commit: Whether to git commit after writing
    """
    _ensure_vault(vault_path)

    # 1. Write episode note
    episode_path = write_episode_note(
        vault_path, episode_meta, format_md, oracle_md, classification, model, asr_model
    )
    episode_name = episode_path.stem  # Without .md, for wikilinks
    logger.info("Wrote episode note", path=str(episode_path))

    # 2. Extract and write insight notes
    insight_wikilinks: List[str] = []
    if oracle_md:
        insights = parse_insights(oracle_md, episode_meta, classification)
        if insights:
            written = write_insight_notes(vault_path, insights)
            insight_wikilinks = [p.stem for p in written]
            logger.info("Wrote insight notes", count=len(written))

    # 3. Update speaker notes
    guests = []
    if classification and classification.get("guests"):
        guests = classification["guests"]
    for guest in guests:
        update_speaker_note(vault_path, guest, episode_name, insight_wikilinks)

    # 4. Update topic MOCs
    tags = []
    if classification and classification.get("topic_tags"):
        tags = classification["topic_tags"]
    for tag in tags:
        topic_name = _tag_to_topic_name(tag)
        update_topic_moc(vault_path, topic_name, insight_wikilinks)

    # 5. Update domain MOCs
    domains = []
    if classification and classification.get("domain_relevance"):
        domains = classification["domain_relevance"]
    for domain in domains:
        update_domain_moc(vault_path, domain, insight_wikilinks)

    # 6. Git commit
    if auto_commit:
        show = episode_meta.get("show", "Unknown")
        title = episode_meta.get("episode_title", "Untitled")
        git_commit_vault(vault_path, f"Add: {show} - {title}")


# ---------------------------------------------------------------------------
# Episode note
# ---------------------------------------------------------------------------


def write_episode_note(
    vault_path: Path,
    episode_meta: Dict[str, Any],
    format_md: Optional[str],
    oracle_md: Optional[str],
    classification: Optional[Dict[str, Any]],
    model: str,
    asr_model: Optional[str] = None,
) -> Path:
    """Write an episode note to Episodes/ with frontmatter and analysis body."""
    date_str = _parse_date(episode_meta.get("episode_published", ""))
    show = episode_meta.get("show", "Unknown")
    title = episode_meta.get("episode_title", "Untitled")
    filename = _safe_filename(f"{date_str} - {show} - {title}")

    # Build frontmatter
    tags = classification.get("topic_tags", []) if classification else []
    domains = classification.get("domain_relevance", []) if classification else []
    relevance = classification.get("relevance_score", "") if classification else ""
    guests = classification.get("guests", []) if classification else []

    guest_links = ", ".join(f"[[{g}]]" for g in guests) if guests else ""
    source_url = episode_meta.get("feed", episode_meta.get("source_url", ""))

    fm = "---\n"
    fm += "type: episode\n"
    fm += f'podcast: "{_escape_yaml(show)}"\n'
    fm += f'episode_title: "{_escape_yaml(title)}"\n'
    if guest_links:
        fm += f'guest: "{guest_links}"\n'
    fm += f"date: {date_str}\n"
    if tags:
        fm += f"tags: [{', '.join(tags)}]\n"
    if domains:
        fm += f"domains: [{', '.join(domains)}]\n"
    if relevance:
        fm += f"relevance_score: {relevance}\n"
    if source_url:
        fm += f'source_url: "{source_url}"\n'
    fm += f"model: {model}\n"
    if asr_model:
        fm += f"asr_model: {asr_model}\n"
    fm += "---\n\n"

    # Build body
    body = f"# {title}\n\n"
    if format_md:
        body += format_md + "\n\n"
    if oracle_md:
        # Strip classification block from display
        clean_oracle = _strip_classification_block(oracle_md)
        if format_md:
            body += "---\n\n"
        body += clean_oracle + "\n"

    path = vault_path / "Episodes" / f"{filename}.md"
    path.write_text(fm + body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Insight extraction and writing
# ---------------------------------------------------------------------------


def parse_insights(
    oracle_md: str,
    episode_meta: Dict[str, Any],
    classification: Optional[Dict[str, Any]],
) -> List[InsightRecord]:
    """Parse knowledge-oracle markdown into atomic InsightRecords."""
    date_str = _parse_date(episode_meta.get("episode_published", ""))
    show = episode_meta.get("show", "Unknown")
    title = episode_meta.get("episode_title", "Untitled")
    episode_name = _safe_filename(f"{date_str} - {show} - {title}")

    tags = classification.get("topic_tags", []) if classification else []
    domains = classification.get("domain_relevance", []) if classification else []
    guests = classification.get("guests", []) if classification else []
    speaker = guests[0] if guests else None

    sections = _split_by_h2(oracle_md)
    insights: List[InsightRecord] = []

    for header, content in sections.items():
        header_lower = header.lower()

        if "transferable framework" in header_lower:
            items = _split_section_items(content)
            for item in items:
                item_title = _extract_framework_title(item)
                insights.append(
                    InsightRecord(
                        title=item_title,
                        body=item.strip(),
                        section_type="framework",
                        speaker=speaker,
                        topics=tags,
                        domains=domains,
                        actionable=False,
                        source_episode=episode_name,
                        date=date_str,
                    )
                )

        elif "contrarian insight" in header_lower:
            items = _split_section_items(content)
            for item in items:
                item_title = _extract_first_phrase(item, max_words=8)
                insights.append(
                    InsightRecord(
                        title=item_title,
                        body=item.strip(),
                        section_type="contrarian",
                        speaker=speaker,
                        topics=tags,
                        domains=domains,
                        actionable=False,
                        source_episode=episode_name,
                        date=date_str,
                    )
                )

        elif "actionable strateg" in header_lower:
            items = _split_section_items(content)
            for item in items:
                # Parse domain tags like [Consulting] [Engineering]
                item_domains = _extract_domain_tags(item) or domains
                item_title = _extract_first_phrase(item, max_words=8)
                insights.append(
                    InsightRecord(
                        title=item_title,
                        body=item.strip(),
                        section_type="strategy",
                        speaker=speaker,
                        topics=tags,
                        domains=item_domains,
                        actionable=True,
                        source_episode=episode_name,
                        date=date_str,
                    )
                )

        elif "quotable insight" in header_lower:
            items = _split_section_items(content)
            for item in items:
                item_title = _extract_quote_title(item)
                insights.append(
                    InsightRecord(
                        title=item_title,
                        body=item.strip(),
                        section_type="quote",
                        speaker=speaker,
                        topics=tags,
                        domains=domains,
                        actionable=False,
                        source_episode=episode_name,
                        date=date_str,
                    )
                )

        elif "knowledge connection" in header_lower:
            items = _split_section_items(content)
            for item in items:
                item_title = _extract_first_phrase(item, max_words=8)
                insights.append(
                    InsightRecord(
                        title=item_title,
                        body=item.strip(),
                        section_type="connection",
                        speaker=speaker,
                        topics=tags,
                        domains=domains,
                        actionable=False,
                        source_episode=episode_name,
                        date=date_str,
                    )
                )

        elif "domain-specific takeaway" in header_lower:
            # Has sub-sections like ### For Consulting Practice
            sub_sections = _split_by_h3(content)
            for sub_header, sub_content in sub_sections.items():
                sub_domains = _domains_from_header(sub_header) or domains
                items = _split_section_items(sub_content)
                for item in items:
                    item_title = _extract_first_phrase(item, max_words=8)
                    insights.append(
                        InsightRecord(
                            title=item_title,
                            body=item.strip(),
                            section_type="takeaway",
                            speaker=speaker,
                            topics=tags,
                            domains=sub_domains,
                            actionable=True,
                            source_episode=episode_name,
                            date=date_str,
                        )
                    )

    return insights


def write_insight_notes(vault_path: Path, insights: List[InsightRecord]) -> List[Path]:
    """Write each InsightRecord as a separate note in Insights/."""
    written: List[Path] = []
    used_filenames: set = set()

    for insight in insights:
        filename = _safe_filename(f"{insight.date} - {insight.title}")

        # Handle collisions
        if filename in used_filenames:
            counter = 2
            while f"{filename} ({counter})" in used_filenames:
                counter += 1
            filename = f"{filename} ({counter})"
        used_filenames.add(filename)

        # Build frontmatter
        fm = "---\n"
        fm += "type: insight\n"
        fm += f'source: "[[{insight.source_episode}]]"\n'
        if insight.speaker:
            fm += f'speaker: "[[{insight.speaker}]]"\n'
        if insight.topics:
            fm += f"topics: [{', '.join(insight.topics)}]\n"
        if insight.domains:
            fm += f"domains: [{', '.join(insight.domains)}]\n"
        fm += "confidence: high\n"
        fm += f"actionable: {'true' if insight.actionable else 'false'}\n"
        fm += "---\n\n"

        # Build body with wikilinks
        body = insight.body + "\n"

        # Add domain and topic wikilinks at the bottom
        links: List[str] = []
        for d in insight.domains:
            links.append(f"[[{d}]]")
        for t in insight.topics:
            topic_name = _tag_to_topic_name(t)
            links.append(f"[[{topic_name}]]")
        if links:
            body += "\n---\n\n"
            body += "Related: " + " | ".join(links) + "\n"

        path = vault_path / "Insights" / f"{filename}.md"
        path.write_text(fm + body, encoding="utf-8")
        written.append(path)

    return written


# ---------------------------------------------------------------------------
# Speaker notes
# ---------------------------------------------------------------------------


def update_speaker_note(
    vault_path: Path,
    speaker_name: str,
    episode_wikilink: str,
    insight_wikilinks: List[str],
) -> None:
    """Create or update a speaker note. Idempotent — won't add duplicate links."""
    filename = _safe_filename(speaker_name)
    path = vault_path / "Speakers" / f"{filename}.md"

    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = (
            f'---\ntype: speaker\nname: "{_escape_yaml(speaker_name)}"\n---\n\n'
            f"# {speaker_name}\n\n"
            f"## Episodes\n\n"
            f"## Notable Insights\n"
        )

    # Append episode link if not already present
    ep_link = f"[[{episode_wikilink}]]"
    if ep_link not in content:
        # Insert after ## Episodes header
        if "## Episodes" in content:
            content = content.replace("## Episodes\n", f"## Episodes\n- {ep_link}\n", 1)
        else:
            content += f"\n## Episodes\n- {ep_link}\n"

    # Append insight links if not already present
    for iw in insight_wikilinks:
        i_link = f"[[{iw}]]"
        if i_link not in content:
            if "## Notable Insights" in content:
                content = content.replace(
                    "## Notable Insights\n", f"## Notable Insights\n- {i_link}\n", 1
                )
            else:
                content += f"\n## Notable Insights\n- {i_link}\n"

    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Topic and Domain MOCs
# ---------------------------------------------------------------------------


def update_topic_moc(
    vault_path: Path,
    topic_name: str,
    insight_wikilinks: List[str],
) -> None:
    """Create or update a Topic MOC. Idempotent."""
    filename = _safe_filename(topic_name)
    path = vault_path / "Topics" / f"{filename}.md"

    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = f"---\ntype: topic\n---\n\n" f"# {topic_name}\n\n" f"## Key Insights\n"

    for iw in insight_wikilinks:
        link = f"[[{iw}]]"
        if link not in content:
            if "## Key Insights" in content:
                content = content.replace("## Key Insights\n", f"## Key Insights\n- {link}\n", 1)
            else:
                content += f"\n- {link}\n"

    path.write_text(content, encoding="utf-8")


def update_domain_moc(
    vault_path: Path,
    domain_name: str,
    insight_wikilinks: List[str],
) -> None:
    """Create or update a Domain MOC. Idempotent."""
    filename = _safe_filename(domain_name)
    path = vault_path / "Domains" / f"{filename}.md"

    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = f"---\ntype: domain\n---\n\n" f"# {domain_name}\n\n" f"## Key Insights\n"

    for iw in insight_wikilinks:
        link = f"[[{iw}]]"
        if link not in content:
            if "## Key Insights" in content:
                content = content.replace("## Key Insights\n", f"## Key Insights\n- {link}\n", 1)
            else:
                content += f"\n- {link}\n"

    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------


def git_commit_vault(vault_path: Path, message: str) -> bool:
    """Git add and commit all changes in the vault. Returns True on success."""
    if not (vault_path / ".git").is_dir():
        # Initialize repo if it doesn't exist
        try:
            subprocess.run(
                ["git", "-C", str(vault_path), "init"],
                capture_output=True,
                check=True,
            )
            _ensure_gitignore(vault_path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Failed to initialize git repo in vault")
            return False

    _ensure_gitignore(vault_path)

    try:
        subprocess.run(
            ["git", "-C", str(vault_path), "add", "."],
            capture_output=True,
            check=True,
        )
        result = subprocess.run(
            ["git", "-C", str(vault_path), "commit", "-m", message],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("Git commit successful", message=message)
            return True
        # returncode 1 means "nothing to commit" — not an error
        return False
    except FileNotFoundError:
        logger.warning("git not found on PATH")
        return False
    except subprocess.CalledProcessError as e:
        logger.warning("Git commit failed", error=str(e))
        return False


def _ensure_gitignore(vault_path: Path) -> None:
    """Ensure .obsidian/workspace.json is gitignored."""
    gitignore = vault_path / ".gitignore"
    ignore_entry = ".obsidian/workspace.json"

    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if ignore_entry in content:
            return
        content = content.rstrip() + f"\n{ignore_entry}\n"
    else:
        content = f"{ignore_entry}\n"

    gitignore.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_vault(vault_path: Path) -> None:
    """Create vault folder structure if it doesn't exist."""
    for folder in FOLDERS:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    clean = UNSAFE_FILENAME_CHARS.sub("", name)
    # Collapse multiple spaces
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncate to reasonable length
    if len(clean) > 150:
        clean = clean[:147] + "..."
    return clean


def _escape_yaml(s: str) -> str:
    """Escape a string for YAML values."""
    return s.replace('"', '\\"')


def _parse_date(date_str: str) -> str:
    """Parse a date string to YYYY-MM-DD format."""
    if not date_str:
        return "unknown-date"
    try:
        from dateutil import parser as dtparse

        parsed = dtparse.parse(date_str)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        # Try to extract YYYY-MM-DD from the string
        match = re.search(r"\d{4}-\d{2}-\d{2}", date_str)
        if match:
            return match.group(0)
        return date_str[:10] if len(date_str) >= 10 else "unknown-date"


def _strip_classification_block(md: str) -> str:
    """Remove ---CLASSIFICATION--- block from markdown."""
    if "---CLASSIFICATION---" not in md:
        return md
    parts = md.split("---CLASSIFICATION---")
    result = parts[0].rstrip()
    if len(parts) > 2:
        trailing = parts[-1].strip()
        if trailing:
            result += "\n\n" + trailing
    return result


def _split_by_h2(md: str) -> Dict[str, str]:
    """Split markdown into sections by ## headers."""
    sections: Dict[str, str] = {}
    parts = re.split(r"\n(?=## )", md)
    for part in parts:
        lines = part.strip().split("\n", 1)
        if lines and lines[0].startswith("## "):
            header = lines[0].lstrip("# ").strip()
            content = lines[1].strip() if len(lines) > 1 else ""
            sections[header] = content
    return sections


def _split_by_h3(md: str) -> Dict[str, str]:
    """Split markdown into sub-sections by ### headers."""
    sections: Dict[str, str] = {}
    parts = re.split(r"\n(?=### )", md)
    for part in parts:
        lines = part.strip().split("\n", 1)
        if lines and lines[0].startswith("### "):
            header = lines[0].lstrip("# ").strip()
            content = lines[1].strip() if len(lines) > 1 else ""
            sections[header] = content
    return sections


def _split_section_items(content: str) -> List[str]:
    """Split a section into individual items.

    Handles both bullet-point lists and bold-header-separated items.
    Groups multi-line items together.
    """
    # Try splitting on bold headers first (** patterns at start of line)
    bold_items = re.split(r"\n(?=\*\*)", content)
    if len(bold_items) > 1:
        return [item.strip() for item in bold_items if item.strip()]

    # Try splitting on numbered items
    numbered = re.split(r"\n(?=\d+\.\s)", content)
    if len(numbered) > 1:
        return [item.strip() for item in numbered if item.strip()]

    # Fall back to top-level bullets (not indented sub-bullets)
    bullet_items = re.split(r"\n(?=- (?!\s))", content)
    if len(bullet_items) > 1:
        return [item.strip() for item in bullet_items if item.strip()]

    # Single item — return the whole content
    if content.strip():
        return [content.strip()]
    return []


def _extract_framework_title(item: str) -> str:
    """Extract a title from a framework item (looks for **Name**: pattern)."""
    match = re.search(r"\*\*(?:Name:?\s*)?(.+?)\*\*", item)
    if match:
        title = match.group(1).strip().rstrip(":")
        if len(title) > 60:
            title = title[:57] + "..."
        return title
    return _extract_first_phrase(item, max_words=8)


def _extract_first_phrase(item: str, max_words: int = 8) -> str:
    """Extract the first meaningful phrase from an item for use as a title."""
    # Strip markdown formatting
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", item)
    clean = re.sub(r"\[.*?\]", "", clean)  # Remove domain tags
    clean = clean.lstrip("- 0123456789.>")
    clean = clean.strip()

    # Take first sentence or phrase
    for sep in [". ", ": ", " — ", " - "]:
        if sep in clean:
            clean = clean.split(sep)[0]
            break

    words = clean.split()[:max_words]
    title = " ".join(words)

    if len(title) > 60:
        title = title[:57] + "..."

    return title if title else "Untitled Insight"


def _extract_quote_title(item: str) -> str:
    """Extract a short title from a quote item."""
    # Look for quoted text
    match = re.search(r'"(.+?)"', item)
    if not match:
        match = re.search(r">(.+?)$", item, re.MULTILINE)
    if match:
        words = match.group(1).split()[:6]
        return " ".join(words) + "..."
    return _extract_first_phrase(item, max_words=6)


def _extract_domain_tags(item: str) -> List[str]:
    """Extract [Domain] tags from an item like [Consulting] [Engineering]."""
    matches = re.findall(
        r"\[(Consulting|Therapy Sites|Engineering|Personal Development|Leadership|Marketing|AI/ML)\]",
        item,
    )
    return matches if matches else []


def _domains_from_header(header: str) -> List[str]:
    """Extract domain from a ### For X Practice header."""
    header_lower = header.lower()
    if "consulting" in header_lower:
        return ["Consulting"]
    if "therapy" in header_lower:
        return ["Therapy Sites"]
    if "personal" in header_lower:
        return ["Personal Development"]
    if "engineering" in header_lower:
        return ["Engineering"]
    if "leadership" in header_lower:
        return ["Leadership"]
    return []


def _tag_to_topic_name(tag: str) -> str:
    """Convert a lowercase tag to a Title Case topic name for MOC files."""
    return tag.replace("-", " ").title()
