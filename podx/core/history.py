"""Episode processing history tracking."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from podx.logging import get_logger

logger = get_logger(__name__)


@dataclass
class HistoryEvent:
    """A single processing event."""

    step: str  # transcribe, diarize, cleanup, analyze
    timestamp: str  # ISO format
    model: Optional[str] = None
    template: Optional[str] = None  # For analyze
    details: Optional[dict[str, Any]] = None  # Extra info (language, etc.)


@dataclass
class EpisodeHistory:
    """Processing history for one episode."""

    episode_dir: str  # Absolute path to episode directory
    show: str
    episode_title: str
    events: list[HistoryEvent] = field(default_factory=list)

    @property
    def last_updated(self) -> str:
        """Get timestamp of most recent event."""
        if not self.events:
            return ""
        return max(e.timestamp for e in self.events)

    @property
    def steps_completed(self) -> list[str]:
        """Get list of completed steps in order."""
        step_order = ["transcribe", "diarize", "cleanup", "analyze"]
        completed = set(e.step for e in self.events)
        return [s for s in step_order if s in completed]


class HistoryManager:
    """Manages episode processing history."""

    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = history_file or self._default_history_file()
        self._history: dict[str, EpisodeHistory] = {}
        self._load()

    @staticmethod
    def _default_history_file() -> Path:
        return Path.home() / ".config" / "podx" / "history.json"

    def _load(self) -> None:
        """Load history from disk."""
        if not self.history_file.exists():
            return
        try:
            data = json.loads(self.history_file.read_text())
            for ep_dir, ep_data in data.items():
                events = [HistoryEvent(**e) for e in ep_data.get("events", [])]
                self._history[ep_dir] = EpisodeHistory(
                    episode_dir=ep_dir,
                    show=ep_data.get("show", "Unknown"),
                    episode_title=ep_data.get("episode_title", ""),
                    events=events,
                )
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")

    def _save(self) -> None:
        """Save history to disk."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for ep_dir, ep_history in self._history.items():
            data[ep_dir] = {
                "show": ep_history.show,
                "episode_title": ep_history.episode_title,
                "events": [asdict(e) for e in ep_history.events],
            }
        self.history_file.write_text(json.dumps(data, indent=2))

    def record_event(
        self,
        episode_dir: Path,
        step: str,
        model: Optional[str] = None,
        template: Optional[str] = None,
        show: Optional[str] = None,
        episode_title: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a processing event for an episode."""
        ep_key = str(episode_dir.resolve())

        # Get or create episode history
        if ep_key not in self._history:
            self._history[ep_key] = EpisodeHistory(
                episode_dir=ep_key,
                show=show or "Unknown",
                episode_title=episode_title or episode_dir.name,
                events=[],
            )

        # Update show/title if provided (may have loaded metadata after initial create)
        ep_history = self._history[ep_key]
        if show:
            ep_history.show = show
        if episode_title:
            ep_history.episode_title = episode_title

        # Add event
        event = HistoryEvent(
            step=step,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            template=template,
            details=details,
        )
        ep_history.events.append(event)

        self._save()

    def get_all(self, show_filter: Optional[str] = None) -> list[EpisodeHistory]:
        """Get all episode histories, optionally filtered by show."""
        histories = list(self._history.values())
        if show_filter:
            show_lower = show_filter.lower()
            histories = [h for h in histories if show_lower in h.show.lower()]
        # Sort by last updated, most recent first
        histories.sort(key=lambda h: h.last_updated, reverse=True)
        return histories

    def get_episode(self, episode_dir: Path) -> Optional[EpisodeHistory]:
        """Get history for a specific episode."""
        return self._history.get(str(episode_dir.resolve()))


# Global instance for convenience
_manager: Optional[HistoryManager] = None


def get_history_manager() -> HistoryManager:
    """Get the global history manager instance."""
    global _manager
    if _manager is None:
        _manager = HistoryManager()
    return _manager


def record_processing_event(
    episode_dir: Path,
    step: str,
    model: Optional[str] = None,
    template: Optional[str] = None,
    show: Optional[str] = None,
    episode_title: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Convenience function to record a processing event."""
    get_history_manager().record_event(
        episode_dir=episode_dir,
        step=step,
        model=model,
        template=template,
        show=show,
        episode_title=episode_title,
        details=details,
    )
