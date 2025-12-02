"""Episode discovery and filtering for batch processing."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from podx.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EpisodeFilter:
    """Filters for episode discovery."""

    show: Optional[str] = None
    since: Optional[str] = None  # ISO date string
    date_range: Optional[Tuple[str, str]] = None  # (start, end) ISO dates
    min_duration: Optional[int] = None  # seconds
    max_duration: Optional[int] = None  # seconds
    pattern: Optional[str] = None  # glob pattern
    status: Optional[str] = None  # "new", "partial", "complete"


class EpisodeDiscovery:
    """Discover and filter episodes for batch processing."""

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize episode discovery.

        Args:
            base_dir: Base directory to search (defaults to cwd)
        """
        self.base_dir = base_dir or Path.cwd()

    def discover_episodes(
        self,
        auto_detect: bool = False,
        filters: Optional[EpisodeFilter] = None,
    ) -> List[Dict[str, Any]]:
        """Discover episodes matching criteria.

        Args:
            auto_detect: Auto-detect episodes from directory structure
            filters: Optional filters to apply

        Returns:
            List of episode metadata dictionaries
        """
        episodes = []

        if auto_detect:
            episodes = self._auto_detect_episodes()
        elif filters and filters.pattern:
            episodes = self._discover_by_pattern(filters.pattern)
        else:
            # Default: look for episode-meta.json files
            episodes = self._discover_by_pattern("*/episode-meta.json")

        # Apply filters
        if filters:
            episodes = self._apply_filters(episodes, filters)

        logger.info(f"Discovered {len(episodes)} episodes")
        return episodes

    def _auto_detect_episodes(self) -> List[Dict[str, Any]]:
        """Auto-detect episodes from directory structure.

        Looks for:
        - episode-meta.json files
        - Directories with audio files
        - Transcript JSON files
        """
        episodes = []

        # Find all episode-meta.json files
        for meta_file in self.base_dir.rglob("episode-meta.json"):
            try:
                episode = self._load_episode_metadata(meta_file)
                if episode:
                    episodes.append(episode)
            except Exception as e:
                logger.warning(f"Failed to load metadata from {meta_file}: {e}")

        # Find directories with audio files but no metadata
        audio_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
        for audio_file in self.base_dir.rglob("*"):
            if audio_file.suffix.lower() in audio_extensions:
                # Check if we already have metadata for this episode
                meta_file = audio_file.parent / "episode-meta.json"
                if not meta_file.exists():
                    # Create minimal episode metadata
                    episode = {
                        "audio_path": str(audio_file),
                        "title": audio_file.stem,
                        "directory": str(audio_file.parent),
                        "discovered": True,
                    }
                    episodes.append(episode)

        return episodes

    def _discover_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Discover episodes matching glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*/episode-meta.json", "*.mp3")

        Returns:
            List of episode metadata
        """
        episodes = []

        for path in self.base_dir.glob(pattern):
            if path.suffix == ".json" and path.name == "episode-meta.json":
                # Load episode metadata
                episode = self._load_episode_metadata(path)
                if episode:
                    episodes.append(episode)
            elif path.suffix.lower() in {".mp3", ".wav", ".m4a", ".flac", ".ogg"}:
                # Create minimal episode from audio file
                episode = {
                    "audio_path": str(path),
                    "title": path.stem,
                    "directory": str(path.parent),
                    "discovered": True,
                }
                episodes.append(episode)

        return episodes

    def _load_episode_metadata(self, meta_file: Path) -> Optional[Dict[str, Any]]:
        """Load episode metadata from JSON file.

        Args:
            meta_file: Path to episode-meta.json

        Returns:
            Episode metadata dict or None if invalid
        """
        try:
            with open(meta_file) as f:
                metadata = json.load(f)

            # Add directory and ensure audio_path is set
            metadata["directory"] = str(meta_file.parent)

            if "audio_path" not in metadata:
                # Try to find audio file in directory
                audio_file = self._find_audio_file(meta_file.parent)
                if audio_file:
                    metadata["audio_path"] = str(audio_file)
                else:
                    logger.warning(
                        f"No audio file found for episode: {metadata.get('title', meta_file)}"
                    )
                    return None

            return metadata

        except Exception as e:
            logger.error(f"Failed to load metadata from {meta_file}: {e}")
            return None

    def _find_audio_file(self, directory: Path) -> Optional[Path]:
        """Find audio file in directory.

        Args:
            directory: Directory to search

        Returns:
            Path to audio file or None
        """
        audio_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}

        for ext in audio_extensions:
            audio_files = list(directory.glob(f"*{ext}"))
            if audio_files:
                return audio_files[0]

        return None

    def _apply_filters(
        self,
        episodes: List[Dict[str, Any]],
        filters: EpisodeFilter,
    ) -> List[Dict[str, Any]]:
        """Apply filters to episode list.

        Args:
            episodes: List of episodes
            filters: Filters to apply

        Returns:
            Filtered episode list
        """
        filtered = episodes

        # Filter by show
        if filters.show:
            filtered = [
                ep
                for ep in filtered
                if filters.show.lower() in ep.get("show", "").lower()
            ]

        # Filter by date (since)
        if filters.since:
            since_date = datetime.fromisoformat(filters.since)
            filtered = [
                ep
                for ep in filtered
                if ep.get("date") and datetime.fromisoformat(ep["date"]) >= since_date
            ]

        # Filter by date range
        if filters.date_range:
            start_date = datetime.fromisoformat(filters.date_range[0])
            end_date = datetime.fromisoformat(filters.date_range[1])
            filtered = [
                ep
                for ep in filtered
                if ep.get("date")
                and start_date <= datetime.fromisoformat(ep["date"]) <= end_date
            ]

        # Filter by duration
        if filters.min_duration is not None:
            filtered = [
                ep for ep in filtered if ep.get("duration", 0) >= filters.min_duration
            ]

        if filters.max_duration is not None:
            filtered = [
                ep
                for ep in filtered
                if ep.get("duration", float("inf")) <= filters.max_duration
            ]

        # Filter by status
        if filters.status:
            filtered = [
                ep for ep in filtered if self._get_episode_status(ep) == filters.status
            ]

        return filtered

    def _get_episode_status(self, episode: Dict[str, Any]) -> str:
        """Get processing status of episode.

        Args:
            episode: Episode metadata

        Returns:
            Status: "new", "partial", or "complete"
        """
        directory = Path(episode.get("directory", "."))

        # Check for transcript files
        has_transcript = (directory / "transcript.json").exists()
        has_diarized = (directory / "diarized-transcript.json").exists()
        has_preprocessed = (directory / "preprocessed-transcript.json").exists()
        has_deepcast = (directory / "deepcast-notes.md").exists()

        if has_deepcast:
            return "complete"
        elif has_transcript or has_diarized or has_preprocessed:
            return "partial"
        else:
            return "new"

    def filter_by_audio_path(
        self, episodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter episodes to only those with valid audio paths.

        Args:
            episodes: List of episodes

        Returns:
            Episodes with valid audio paths
        """
        filtered = []

        for ep in episodes:
            audio_path = ep.get("audio_path")
            if audio_path and Path(audio_path).exists():
                filtered.append(ep)
            else:
                logger.warning(
                    f"Skipping episode (missing audio): {ep.get('title', 'unknown')}"
                )

        return filtered
