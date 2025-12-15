"""Helper for CLI commands to track operations in manifest.

This module provides simple functions that CLI commands can use to update
the manifest without needing to understand the full ManifestManager API.

All functions fail silently (log errors but don't crash) to ensure CLI
commands continue working even if manifest tracking fails.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from podx.logging import get_logger
from podx.manifest import ManifestManager

logger = get_logger(__name__)


def extract_episode_info(path: Path) -> Optional[tuple[str, str]]:
    """Extract show name and date from episode path.

    Expected structures:
    - show-name/YYYY-MM-DD/
    - show-name/episode-YYYY-MM-DD/
    - YYYY-MM-DD/
    - episode-YYYY-MM-DD/

    Returns:
        Tuple of (show, date) or None if cannot extract
    """
    try:
        path = path.resolve()

        # Try to find date pattern (YYYY-MM-DD)
        parts = path.parts
        date = None
        show = None

        # Check last two parts for show/date pattern
        for i in range(len(parts) - 1, max(0, len(parts) - 3), -1):
            part = parts[i]

            # Check if this looks like a date (YYYY-MM-DD or episode-YYYY-MM-DD)
            if "-" in part:
                potential_date = part.replace("episode-", "")
                if len(potential_date) == 10 and potential_date.count("-") == 2:
                    try:
                        # Validate it's actually date-like
                        year, month, day = potential_date.split("-")
                        if len(year) == 4 and len(month) == 2 and len(day) == 2:
                            date = potential_date
                            # Show name is the parent directory
                            if i > 0:
                                show = parts[i - 1]
                            break
                    except ValueError:
                        continue

        # Default show name to current directory if not found
        if date and not show:
            show = path.name if path.is_dir() else path.parent.name

        if show and date:
            return (show, date)

        return None

    except Exception as e:
        logger.debug("Could not extract episode info from path", path=str(path), error=str(e))
        return None


def start_stage(
    audio_path: Optional[Path] = None,
    episode_dir: Optional[Path] = None,
    show: Optional[str] = None,
    date: Optional[str] = None,
    stage: str = "unknown",
    model: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark a stage as started in the manifest.

    Args:
        audio_path: Path to audio file (will extract episode info from this)
        episode_dir: Path to episode directory
        show: Show name (if not provided, will try to extract)
        date: Episode date (if not provided, will try to extract)
        stage: Stage name (transcribe, diarize, deepcast, export, notion)
        model: Model being used for this stage
        metadata: Additional metadata to store
    """
    try:
        # Try to determine show and date
        if not (show and date):
            path = episode_dir or (audio_path.parent if audio_path else None)
            if path:
                info = extract_episode_info(path)
                if info:
                    show, date = info

        if not (show and date):
            logger.debug("Cannot track stage start: missing show/date info")
            return

        # Update manifest
        manager = ManifestManager()
        manager.start_stage(
            show=show,
            date=date,
            stage=stage,
            model=model,
            metadata=metadata or {},
        )
        logger.debug("Manifest updated: stage started", show=show, date=date, stage=stage)

    except Exception as e:
        logger.debug("Failed to update manifest (start)", error=str(e))


def complete_stage(
    audio_path: Optional[Path] = None,
    episode_dir: Optional[Path] = None,
    show: Optional[str] = None,
    date: Optional[str] = None,
    stage: str = "unknown",
    files: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark a stage as completed in the manifest.

    Args:
        audio_path: Path to audio file (will extract episode info from this)
        episode_dir: Path to episode directory
        show: Show name (if not provided, will try to extract)
        date: Episode date (if not provided, will try to extract)
        stage: Stage name (transcribe, diarize, deepcast, export, notion)
        files: List of output files created
        metadata: Additional metadata to store
    """
    try:
        # Try to determine show and date
        if not (show and date):
            path = episode_dir or (audio_path.parent if audio_path else None)
            if path:
                info = extract_episode_info(path)
                if info:
                    show, date = info

        if not (show and date):
            logger.debug("Cannot track stage completion: missing show/date info")
            return

        # Update manifest
        manager = ManifestManager()
        manager.complete_stage(
            show=show,
            date=date,
            stage=stage,
            files=[str(f) for f in (files or [])],
            metadata=metadata or {},
        )
        logger.debug("Manifest updated: stage completed", show=show, date=date, stage=stage)

    except Exception as e:
        logger.debug("Failed to update manifest (complete)", error=str(e))


def update_progress(
    audio_path: Optional[Path] = None,
    episode_dir: Optional[Path] = None,
    show: Optional[str] = None,
    date: Optional[str] = None,
    stage: str = "unknown",
    progress: float = 0.0,
    status: Optional[str] = None,
) -> None:
    """Update stage progress in the manifest.

    Args:
        audio_path: Path to audio file (will extract episode info from this)
        episode_dir: Path to episode directory
        show: Show name (if not provided, will try to extract)
        date: Episode date (if not provided, will try to extract)
        stage: Stage name (transcribe, diarize, deepcast, export, notion)
        progress: Progress as float 0.0 to 1.0
        status: Human-readable status message
    """
    try:
        # Try to determine show and date
        if not (show and date):
            path = episode_dir or (audio_path.parent if audio_path else None)
            if path:
                info = extract_episode_info(path)
                if info:
                    show, date = info

        if not (show and date):
            return

        # Update manifest
        manager = ManifestManager()
        manager.update_stage_progress(
            show=show,
            date=date,
            stage=stage,
            progress=progress,
            status=status,
        )

    except Exception as e:
        logger.debug("Failed to update manifest (progress)", error=str(e))


def fail_stage(
    audio_path: Optional[Path] = None,
    episode_dir: Optional[Path] = None,
    show: Optional[str] = None,
    date: Optional[str] = None,
    stage: str = "unknown",
    error: str = "Unknown error",
) -> None:
    """Mark a stage as failed in the manifest.

    Args:
        audio_path: Path to audio file (will extract episode info from this)
        episode_dir: Path to episode directory
        show: Show name (if not provided, will try to extract)
        date: Episode date (if not provided, will try to extract)
        stage: Stage name (transcribe, diarize, deepcast, export, notion)
        error: Error message
    """
    try:
        # Try to determine show and date
        if not (show and date):
            path = episode_dir or (audio_path.parent if audio_path else None)
            if path:
                info = extract_episode_info(path)
                if info:
                    show, date = info

        if not (show and date):
            return

        # Update manifest
        manager = ManifestManager()
        manager.fail_stage(
            show=show,
            date=date,
            stage=stage,
            error=error,
        )
        logger.debug("Manifest updated: stage failed", show=show, date=date, stage=stage)

    except Exception as e:
        logger.debug("Failed to update manifest (fail)", error=str(e))
