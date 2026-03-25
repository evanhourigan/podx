"""Disk cleanup for episode directories.

Tiered deletion strategy:
- Tier 1 (always safe): audio.wav, analysis files, export files
- Tier 2 (with confirmation): original audio (mp3, m4a)
- Tier 3 (never delete): episode-meta.json, transcript.json, speaker-map.json

Philosophy: Local storage is a workspace, not an archive. Notion is
the system of record. Once published, intermediate files can be cleaned.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from ..logging import get_logger

logger = get_logger(__name__)

# Tier 1: Always safe to delete after verified Notion publish
TIER1_PATTERNS = [
    "audio.wav",
    "audio_diarize.wav",
    "audio-meta.json",
    "analysis*.json",
    "analysis*.md",
    "deepcast-*.json",
    "deepcast-*.md",
    "episode-classification.json",
    "transcript.md",
    "transcript.txt",
    "*.srt",
    "*.vtt",
]

# Tier 2: Delete with confirmation (original audio)
TIER2_PATTERNS = [
    "*.mp3",
    "*.m4a",
    "*.mp4",
    "*.ogg",
    "*.flac",
]

# Tier 3: Never delete
TIER3_KEEP = [
    "episode-meta.json",
    "transcript.json",
    "speaker-map.json",
]


@dataclass
class CleanupPlan:
    """Plan for what would be cleaned in an episode directory."""

    episode_dir: Path
    tier1_files: List[Path] = field(default_factory=list)
    tier2_files: List[Path] = field(default_factory=list)
    tier3_files: List[Path] = field(default_factory=list)
    total_bytes_tier1: int = 0
    total_bytes_tier2: int = 0
    notion_verified: bool = False


def plan_cleanup(episode_dir: Path) -> CleanupPlan:
    """Scan episode directory and build a cleanup plan.

    Categorizes all files into tiers based on deletion safety.

    Args:
        episode_dir: Path to episode directory

    Returns:
        CleanupPlan with categorized files and byte counts
    """
    plan = CleanupPlan(episode_dir=episode_dir)
    keep_names = set(TIER3_KEEP)

    for f in episode_dir.iterdir():
        if not f.is_file():
            continue

        # Tier 3: never delete
        if f.name in keep_names:
            plan.tier3_files.append(f)
            continue

        # Tier 1: safe to delete
        if _matches_patterns(f.name, TIER1_PATTERNS):
            plan.tier1_files.append(f)
            plan.total_bytes_tier1 += f.stat().st_size
            continue

        # Tier 2: original audio
        if _matches_patterns(f.name, TIER2_PATTERNS):
            plan.tier2_files.append(f)
            plan.total_bytes_tier2 += f.stat().st_size
            continue

        # Unmatched files go to tier 3 (keep)
        plan.tier3_files.append(f)

    return plan


def verify_notion_publish(
    episode_dir: Path,
    db_id: str,
) -> bool:
    """Verify episode has been published to Notion.

    Queries the Notion database to check for an existing entry
    matching this episode.

    Args:
        episode_dir: Episode directory (must contain episode-meta.json)
        db_id: Notion database ID

    Returns:
        True if episode is published in Notion
    """
    import json as json_module

    meta_path = episode_dir / "episode-meta.json"
    if not meta_path.exists():
        return False

    try:
        from notion_client import Client
    except ImportError:
        logger.warning("notion-client not installed, cannot verify publish")
        return False

    token = os.getenv("NOTION_TOKEN")
    if not token:
        logger.warning("NOTION_TOKEN not set, cannot verify publish")
        return False

    meta = json_module.loads(meta_path.read_text(encoding="utf-8"))
    episode_title = meta.get("episode_title", "")
    if not episode_title:
        return False

    client = Client(auth=token)
    try:
        # Query by title
        db_schema = client.databases.retrieve(db_id)
        title_prop = None
        for pname, pinfo in db_schema.get("properties", {}).items():
            if pinfo.get("type") == "title":
                title_prop = pname
                break

        if not title_prop:
            return False

        resp = client.databases.query(
            database_id=db_id,
            filter={"property": title_prop, "title": {"equals": episode_title}},
        )
        return bool(resp.get("results"))
    except Exception as e:
        logger.warning("Notion verification failed", error=str(e))
        return False


def execute_cleanup(
    plan: CleanupPlan,
    include_tier2: bool = False,
    require_notion_verification: bool = True,
) -> Tuple[int, int]:
    """Execute the cleanup plan.

    Args:
        plan: The cleanup plan to execute
        include_tier2: Whether to delete tier 2 files (original audio)
        require_notion_verification: Require Notion publish verification

    Returns:
        Tuple of (files_deleted, bytes_freed)

    Raises:
        RuntimeError: If Notion verification required but failed
    """
    if require_notion_verification and not plan.notion_verified:
        raise RuntimeError(
            "Notion publish not verified. Use --force to skip verification, "
            "or run 'podx backfill' to publish first."
        )

    files_deleted = 0
    bytes_freed = 0

    # Delete tier 1 files
    for f in plan.tier1_files:
        try:
            size = f.stat().st_size
            f.unlink()
            files_deleted += 1
            bytes_freed += size
        except OSError as e:
            logger.warning("Failed to delete file", path=str(f), error=str(e))

    # Optionally delete tier 2 files
    if include_tier2:
        for f in plan.tier2_files:
            try:
                size = f.stat().st_size
                f.unlink()
                files_deleted += 1
                bytes_freed += size
            except OSError as e:
                logger.warning("Failed to delete file", path=str(f), error=str(e))

    return files_deleted, bytes_freed


def format_bytes(n: int) -> str:
    """Format byte count as human-readable string."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    else:
        return f"{n / (1024 * 1024 * 1024):.1f} GB"


def _matches_patterns(filename: str, patterns: List[str]) -> bool:
    """Check if a filename matches any of the glob-style patterns."""
    from fnmatch import fnmatch

    return any(fnmatch(filename, pat) for pat in patterns)
