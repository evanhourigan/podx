"""Core backfill engine for batch re-analysis and Notion publishing.

Pure business logic — no UI, no CLI. Handles:
- Episode discovery and filtering
- Running analyses with multiple templates
- Parsing classification JSON from knowledge-oracle output
- Building Notion page content and properties
- Template version hashing for smart skip
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.analyze import AnalyzeEngine
from ..core.classify import classify_episode
from ..core.notion import md_to_blocks
from ..core.speakers import apply_speaker_map_to_transcript, has_generic_speakers, load_speaker_map
from ..logging import get_logger
from ..templates.manager import DeepcastTemplate, TemplateManager

logger = get_logger(__name__)

NOTION_DB_ID = "247340ada0a880e680ade71a2e97d02b"

DOMAIN_RELEVANCE_OPTIONS = [
    "Consulting",
    "Therapy Sites",
    "Engineering",
    "Personal Development",
    "Leadership",
    "Marketing",
    "AI/ML",
]

# Template classification format mappings
FORMAT_TO_TEMPLATE = {
    "interview": "interview-1on1",
    "interview-1on1": "interview-1on1",
    "panel": "panel-discussion",
    "panel-discussion": "panel-discussion",
    "solo": "solo-commentary",
    "solo-commentary": "solo-commentary",
    "general": "general",
    "debate": "debate-roundtable",
    "debate-roundtable": "debate-roundtable",
    "lecture": "lecture-presentation",
    "lecture-presentation": "lecture-presentation",
    "news": "news-analysis",
    "news-analysis": "news-analysis",
    "technical": "technical-deep-dive",
    "technical-deep-dive": "technical-deep-dive",
}

DEFAULT_MAP_INSTRUCTIONS = "Extract key points, notable quotes, and insights from this section."


@dataclass
class BackfillConfig:
    """Configuration for a backfill run."""

    model: str = "gpt-5.1"
    dry_run: bool = False
    force_reanalyze: bool = False
    notion_db_id: str = NOTION_DB_ID
    publish_to_notion: bool = True


@dataclass
class BackfillResult:
    """Result for a single episode backfill."""

    episode_dir: Path
    show: str = ""
    episode_title: str = ""
    success: bool = False
    error: Optional[str] = None
    notion_page_id: Optional[str] = None
    templates_run: List[str] = field(default_factory=list)
    classification: Optional[Dict[str, Any]] = None


def compute_template_hash(template: DeepcastTemplate) -> str:
    """Compute a hash of template prompt content for version tracking.

    Hash includes system_prompt + user_prompt + map_instructions so
    we can detect when a template has been updated and needs re-analysis.

    Args:
        template: The template to hash

    Returns:
        12-char hex hash string
    """
    content = template.system_prompt + template.user_prompt + (template.map_instructions or "")
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def analysis_needs_rerun(
    analysis_path: Path,
    template: DeepcastTemplate,
    force: bool = False,
) -> bool:
    """Check if an existing analysis needs to be re-run.

    Compares the template_hash stored in the analysis JSON with the
    current template's hash. Different hash = template was updated.

    Args:
        analysis_path: Path to existing analysis JSON
        template: Current template version
        force: Force re-run regardless of hash

    Returns:
        True if analysis should be re-run
    """
    if force:
        return True
    if not analysis_path.exists():
        return True

    try:
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        stored_hash = analysis.get("template_hash")
        if not stored_hash:
            return True  # No hash = old analysis, re-run
        current_hash = compute_template_hash(template)
        return stored_hash != current_hash
    except (json.JSONDecodeError, OSError):
        return True


def parse_classification_json(markdown: str) -> Optional[Dict[str, Any]]:
    """Extract classification JSON from knowledge-oracle analysis output.

    Looks for content between ---CLASSIFICATION--- delimiters.

    Args:
        markdown: Analysis markdown output

    Returns:
        Parsed classification dict, or None if not found/invalid
    """
    if "---CLASSIFICATION---" not in markdown:
        return None

    parts = markdown.split("---CLASSIFICATION---")
    if len(parts) < 3:
        return None

    json_str = parts[1].strip()
    # Handle fenced code blocks
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    json_str = json_str.strip()

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        logger.warning("Failed to parse classification JSON", raw=json_str[:200])
        return None


def build_notion_properties(
    classification: Optional[Dict[str, Any]],
    templates_run: List[str],
    model: str,
    asr_model: Optional[str] = None,
    has_transcript: bool = True,
    source_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Build Notion page properties for props_extra.

    Constructs raw Notion API property payloads for the new schema fields.
    Tags are REPLACED entirely (not merged) to clean up old cruft.

    Args:
        classification: Parsed classification JSON from knowledge-oracle
        templates_run: List of template names used
        model: LLM model used for analysis
        asr_model: ASR model used for transcription
        has_transcript: Whether full transcript is included
        source_url: Episode source URL

    Returns:
        Dict suitable for upsert_page's props_extra parameter
    """
    props_extra: Dict[str, Any] = {}

    if classification:
        # Domain Relevance -> multi_select (replace entirely)
        domains = classification.get("domain_relevance", [])
        if domains:
            valid_domains = [d for d in domains if d in DOMAIN_RELEVANCE_OPTIONS]
            if valid_domains:
                props_extra["Domain Relevance"] = {
                    "multi_select": [{"name": d} for d in valid_domains]
                }

        # Relevance Score -> select
        score = classification.get("relevance_score", "")
        if score in ("High", "Medium", "Low"):
            props_extra["Relevance Score"] = {"select": {"name": score}}

        # Tags -> multi_select (REPLACE entirely, don't merge with old tags)
        tags = classification.get("topic_tags", [])
        if tags:
            props_extra["Tags"] = {"multi_select": [{"name": t} for t in tags]}

        # Guest(s) -> rich_text
        guests = classification.get("guests", [])
        if guests:
            props_extra["Guest(s)"] = {
                "rich_text": [{"type": "text", "text": {"content": ", ".join(guests)}}]
            }

    # Template Used -> rich_text
    if templates_run:
        props_extra["Template Used"] = {
            "rich_text": [{"type": "text", "text": {"content": ", ".join(templates_run)}}]
        }

    # Has Transcript -> checkbox
    props_extra["Has Transcript"] = {"checkbox": has_transcript}

    # Source URL -> url
    if source_url:
        props_extra["Source URL"] = {"url": source_url}

    return props_extra


def build_notion_page_blocks(
    format_analysis_md: Optional[str],
    oracle_analysis_md: Optional[str],
    transcript: Optional[Dict[str, Any]],
    video_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build Notion page content blocks.

    Assembles:
    1. Format analysis (if available)
    2. Knowledge-oracle analysis (if available)
    3. Full transcript in collapsed toggle section

    Args:
        format_analysis_md: Markdown from format template analysis
        oracle_analysis_md: Markdown from knowledge-oracle analysis
        transcript: Transcript dict with segments
        video_url: Optional YouTube URL for timestamp links

    Returns:
        List of Notion block dicts
    """
    blocks: List[Dict[str, Any]] = []

    # Format analysis
    if format_analysis_md:
        blocks.extend(md_to_blocks(format_analysis_md))

    # Divider between analyses
    if format_analysis_md and oracle_analysis_md:
        blocks.append({"type": "divider", "divider": {}})

    # Knowledge-oracle analysis
    if oracle_analysis_md:
        # Strip classification block from display (it's metadata, not content)
        clean_md = oracle_analysis_md
        if "---CLASSIFICATION---" in clean_md:
            parts = clean_md.split("---CLASSIFICATION---")
            # Keep everything before the first delimiter + everything after the last
            clean_md = parts[0].rstrip()
            if len(parts) > 2:
                trailing = parts[-1].strip()
                if trailing:
                    clean_md += "\n\n" + trailing
        blocks.extend(md_to_blocks(clean_md))

    # Transcript in collapsed toggle blocks
    if transcript and transcript.get("segments"):
        blocks.append({"type": "divider", "divider": {}})
        transcript_blocks = _format_transcript_blocks(transcript, video_url)

        TOGGLE_CHILD_LIMIT = 100
        if len(transcript_blocks) <= TOGGLE_CHILD_LIMIT:
            blocks.append(
                {
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"type": "text", "text": {"content": "Full Transcript"}}],
                        "children": transcript_blocks,
                    },
                }
            )
        else:
            for i in range(0, len(transcript_blocks), TOGGLE_CHILD_LIMIT):
                chunk = transcript_blocks[i : i + TOGGLE_CHILD_LIMIT]
                part_num = (i // TOGGLE_CHILD_LIMIT) + 1
                blocks.append(
                    {
                        "type": "toggle",
                        "toggle": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {"content": f"Transcript (Part {part_num})"},
                                }
                            ],
                            "children": chunk,
                        },
                    }
                )

    return blocks


def _format_transcript_blocks(
    transcript: Dict[str, Any], video_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Convert transcript segments to Notion paragraph blocks."""
    blocks = []
    for seg in transcript.get("segments", []):
        start = seg.get("start", 0)
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        if not text:
            continue

        # Format timestamp
        minutes = int(start // 60)
        seconds = int(start % 60)
        ts = f"[{minutes}:{seconds:02d}]"

        if speaker:
            content = f"{ts} {speaker}: {text}"
        else:
            content = f"{ts} {text}"

        blocks.append(
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]},
            }
        )
    return blocks


def detect_format_template(transcript: Dict[str, Any], episode_meta: Dict[str, Any]) -> str:
    """Auto-detect the best format template for an episode.

    Uses heuristic classification from podx.core.classify.

    Args:
        transcript: Transcript dict with segments
        episode_meta: Episode metadata dict

    Returns:
        Template name string
    """
    try:
        result = classify_episode(transcript, episode_meta)
        detected_format = result.get("format", "general")
        template_name = FORMAT_TO_TEMPLATE.get(detected_format, "general")
        logger.info("Detected format", format=detected_format, template=template_name)
        return template_name
    except Exception:
        return "general"


def run_analysis(
    transcript: Dict[str, Any],
    episode_meta: Dict[str, Any],
    episode_dir: Path,
    template_name: str,
    model: str,
    force: bool = False,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Path]:
    """Run a single template analysis on an episode.

    Checks for existing analysis with matching template hash before re-running.

    Args:
        transcript: Transcript dict
        episode_meta: Episode metadata
        episode_dir: Episode directory path
        template_name: Template to use
        model: LLM model string (provider:model_name)
        force: Force re-run regardless of hash

    Returns:
        Tuple of (markdown, json_data, analysis_path)
    """
    manager = TemplateManager()
    tmpl = manager.load(template_name)

    # Build output path
    from podx.cli.analyze import analysis_output_path

    analysis_path = analysis_output_path(episode_dir, template_name, model)

    # Check if re-run is needed
    if not analysis_needs_rerun(analysis_path, tmpl, force):
        logger.info("Skipping analysis (template hash matches)", template=template_name)
        existing = json.loads(analysis_path.read_text(encoding="utf-8"))
        return existing.get("markdown", ""), existing.get("results"), analysis_path

    # Build transcript text
    segments = transcript.get("segments", [])
    transcript_text = "\n".join(
        (
            f"[{s.get('speaker', 'SPEAKER')}] {s.get('text', '')}"
            if s.get("speaker")
            else s.get("text", "")
        )
        for s in segments
    )

    # Build context
    speaker_set = set(s.get("speaker") for s in segments if s.get("speaker"))
    speaker_count = len(speaker_set) if speaker_set else 1
    speakers_str = ", ".join(sorted(speaker_set)) if speaker_set else "Unknown"

    date_str = episode_meta.get("episode_published", "")
    if date_str:
        try:
            from dateutil import parser as dtparse

            parsed = dtparse.parse(date_str)
            date_str = parsed.strftime("%Y-%m-%d")
        except Exception:
            date_str = date_str[:10] if len(date_str) >= 10 else date_str

    duration_minutes = int(segments[-1].get("end", 0) // 60) if segments else 0

    context = {
        "transcript": transcript_text,
        "speaker_count": speaker_count,
        "speakers": speakers_str,
        "duration": duration_minutes,
        "title": episode_meta.get("episode_title", episode_dir.name),
        "show": episode_meta.get("show", "Unknown"),
        "date": date_str or "Unknown",
        "description": episode_meta.get("episode_description", ""),
    }

    # Render template
    system_prompt, user_prompt = tmpl.render(context)

    # Parse model string
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

    md, json_data = engine.analyze(
        transcript=transcript,
        system_prompt=system_prompt,
        map_instructions=(tmpl.map_instructions or DEFAULT_MAP_INSTRUCTIONS),
        reduce_instructions=user_prompt,
        want_json=not tmpl.wants_json_only,
        json_schema=tmpl.json_schema,
    )

    # Save analysis with template hash
    template_hash = compute_template_hash(tmpl)
    result = {
        "episode": {
            "title": episode_meta.get("episode_title", episode_dir.name),
            "show": episode_meta.get("show", "Unknown"),
            "published": episode_meta.get("episode_published", ""),
            "duration_minutes": duration_minutes,
        },
        "template": template_name,
        "template_hash": template_hash,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "results": json_data or {},
        "markdown": md,
    }
    analysis_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return md, json_data, analysis_path


def find_transcript(episode_dir: Path) -> Optional[Path]:
    """Find best transcript file in episode directory.

    Priority: transcript.json > diarized > aligned > base
    """
    standard = episode_dir / "transcript.json"
    if standard.exists():
        return standard

    # Legacy patterns
    for pattern in [
        "transcript-diarized-*.json",
        "transcript-aligned-*.json",
        "transcript-*.json",
    ]:
        matches = sorted(episode_dir.glob(pattern))
        if matches:
            return matches[-1]
    return None


def backfill_episode(
    episode_dir: Path,
    config: BackfillConfig,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> BackfillResult:
    """Run the full backfill pipeline for a single episode.

    Steps:
    1. Load episode metadata and transcript
    2. Apply speaker map if generic speakers remain
    3. Auto-detect format template
    4. Run format template analysis (smart skip via hash)
    5. Run knowledge-oracle analysis (smart skip via hash)
    6. Parse classification JSON from oracle output
    7. Build Notion properties and blocks
    8. Upsert to Notion

    Args:
        episode_dir: Path to episode directory
        config: Backfill configuration
        progress_callback: Optional callback for status updates

    Returns:
        BackfillResult with success/failure details
    """
    result = BackfillResult(episode_dir=episode_dir)

    def _progress(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        logger.info(msg, episode_dir=str(episode_dir))

    # 1. Load metadata
    meta_path = episode_dir / "episode-meta.json"
    if not meta_path.exists():
        result.error = "No episode-meta.json found"
        return result

    episode_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    result.show = episode_meta.get("show", "Unknown")
    result.episode_title = episode_meta.get("episode_title", episode_dir.name)

    # Load transcript
    transcript_path = find_transcript(episode_dir)
    if not transcript_path:
        result.error = "No transcript found"
        return result

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    if not transcript.get("segments"):
        result.error = "Transcript has no segments"
        return result

    _progress(f"Processing: {result.show} - {result.episode_title}")

    # 2. Apply speaker map if needed
    if has_generic_speakers(episode_dir):
        speaker_map = load_speaker_map(episode_dir)
        if speaker_map:
            apply_speaker_map_to_transcript(episode_dir, speaker_map)
            # Reload transcript with applied names
            transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
            _progress(f"Applied speaker map ({len(speaker_map)} speakers)")

    # 3. Auto-detect format template
    format_template = detect_format_template(transcript, episode_meta)
    _progress(f"Detected format: {format_template}")

    if config.dry_run:
        result.success = True
        result.templates_run = [format_template, "knowledge-oracle"]
        return result

    # 4. Run format template analysis
    _progress(f"Running {format_template} analysis...")
    try:
        format_md, _, _ = run_analysis(
            transcript,
            episode_meta,
            episode_dir,
            format_template,
            config.model,
            config.force_reanalyze,
        )
        result.templates_run.append(format_template)
    except Exception as e:
        _progress(f"Format analysis failed: {e}")
        format_md = None

    # 5. Run knowledge-oracle analysis
    _progress("Running knowledge-oracle analysis...")
    oracle_md = None
    try:
        oracle_md, _, _ = run_analysis(
            transcript,
            episode_meta,
            episode_dir,
            "knowledge-oracle",
            config.model,
            config.force_reanalyze,
        )
        result.templates_run.append("knowledge-oracle")
    except Exception as e:
        _progress(f"Knowledge-oracle analysis failed: {e}")

    # 6. Parse classification
    if oracle_md:
        result.classification = parse_classification_json(oracle_md)
        if result.classification:
            _progress(f"Classification: {result.classification.get('relevance_score', '?')}")

    # 7-8. Publish to Notion
    if config.publish_to_notion and (format_md or oracle_md):
        try:
            page_id = _publish_to_notion(
                episode_dir,
                episode_meta,
                transcript,
                format_md,
                oracle_md,
                result,
                config,
            )
            result.notion_page_id = page_id
            _progress(f"Published to Notion: {page_id}")
        except Exception as e:
            _progress(f"Notion publish failed: {e}")
            result.error = f"Notion publish failed: {e}"
            return result

    result.success = True
    return result


def _publish_to_notion(
    episode_dir: Path,
    episode_meta: Dict[str, Any],
    transcript: Dict[str, Any],
    format_md: Optional[str],
    oracle_md: Optional[str],
    result: BackfillResult,
    config: BackfillConfig,
) -> str:
    """Publish episode to Notion. Returns page ID."""
    import os

    try:
        from notion_client import Client
    except ImportError:
        raise RuntimeError("notion-client not installed. Run: pip install notion-client")

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN environment variable not set")

    client = Client(auth=token)

    # Build properties
    video_url = episode_meta.get("video_url")
    source_url = episode_meta.get("feed") or episode_meta.get("source_url")
    asr_model = None
    if transcript:
        asr_model = transcript.get("asr_model")

    props_extra = build_notion_properties(
        classification=result.classification,
        templates_run=result.templates_run,
        model=config.model,
        asr_model=asr_model,
        has_transcript=bool(transcript and transcript.get("segments")),
        source_url=source_url,
    )

    # Add ASR Model if available
    if asr_model:
        props_extra["ASR Model"] = {"rich_text": [{"type": "text", "text": {"content": asr_model}}]}

    # Build page blocks — separate analysis from transcript toggles
    # Toggle blocks with nested children can blow past Notion's per-request
    # block limit, so we append them individually after page creation.
    all_blocks = build_notion_page_blocks(format_md, oracle_md, transcript, video_url)

    analysis_blocks = []
    toggle_blocks = []
    for b in all_blocks:
        if b.get("type") == "toggle":
            toggle_blocks.append(b)
        else:
            analysis_blocks.append(b)

    # Parse date
    date_iso = None
    date_str = episode_meta.get("episode_published", "")
    if date_str:
        try:
            from dateutil import parser as dtparse

            parsed = dtparse.parse(date_str)
            date_iso = parsed.strftime("%Y-%m-%d")
        except Exception:
            if len(date_str) >= 10:
                date_iso = date_str[:10]

    # Upsert with analysis blocks only (no toggles)
    from podx.cli.notion_services.page_operations import upsert_page

    page_id = upsert_page(
        client=client,
        db_id=config.notion_db_id,
        podcast_name=episode_meta.get("show", "Unknown"),
        episode_title=episode_meta.get("episode_title", episode_dir.name),
        date_iso=date_iso,
        podcast_prop="Podcast",
        episode_prop="Episode",
        date_prop="Date",
        model_prop="Model",
        asr_prop="ASR Model",
        deepcast_model=config.model,
        asr_model=asr_model,
        props_extra=props_extra,
        blocks=analysis_blocks,
        replace_content=True,
    )

    # Append transcript toggle blocks one at a time (each has nested children)
    for toggle in toggle_blocks:
        try:
            client.blocks.children.append(block_id=page_id, children=[toggle])
        except Exception as e:
            logger.warning("Failed to append toggle block", error=str(e))

    return page_id
