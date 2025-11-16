"""Batch processing status tracking and display."""

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.table import Table

from podx.logging import get_logger

logger = get_logger(__name__)
console = Console()


class ProcessingState(str, Enum):
    """Processing state for pipeline steps."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EpisodeStatus:
    """Processing status for a single episode."""

    title: str
    show: Optional[str] = None
    directory: Optional[str] = None

    # Processing states
    fetch: ProcessingState = ProcessingState.NOT_STARTED
    transcode: ProcessingState = ProcessingState.NOT_STARTED
    transcribe: ProcessingState = ProcessingState.NOT_STARTED
    diarize: ProcessingState = ProcessingState.NOT_STARTED
    preprocess: ProcessingState = ProcessingState.NOT_STARTED
    deepcast: ProcessingState = ProcessingState.NOT_STARTED
    export: ProcessingState = ProcessingState.NOT_STARTED

    # Metadata
    last_updated: Optional[str] = None
    error_message: Optional[str] = None


class BatchStatus:
    """Track and display batch processing status."""

    def __init__(self, status_file: Optional[Path] = None):
        """Initialize batch status tracker.

        Args:
            status_file: Path to status file (defaults to ~/.podx/batch-status.json)
        """
        if status_file is None:
            status_file = Path.home() / ".podx" / "batch-status.json"

        self.status_file = status_file
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.episodes: Dict[str, EpisodeStatus] = {}

        # Load existing status
        self._load()

    def update_episode(
        self,
        episode_key: str,
        step: str,
        state: ProcessingState,
        error_message: Optional[str] = None,
    ) -> None:
        """Update episode processing status.

        Args:
            episode_key: Unique episode identifier (e.g., title or path)
            step: Processing step (fetch, transcribe, etc.)
            state: New processing state
            error_message: Optional error message if failed
        """
        if episode_key not in self.episodes:
            self.episodes[episode_key] = EpisodeStatus(title=episode_key)

        episode = self.episodes[episode_key]

        # Update step state
        if hasattr(episode, step):
            setattr(episode, step, state)

        # Update error message
        if error_message:
            episode.error_message = error_message

        # Update timestamp
        from datetime import datetime

        episode.last_updated = datetime.now().isoformat()

        # Save to disk
        self._save()

    def add_episode(self, episode: Dict[str, Any]) -> str:
        """Add episode to tracking.

        Args:
            episode: Episode metadata

        Returns:
            Episode key
        """
        # Use directory as key if available, otherwise title
        episode_key = episode.get("directory") or episode.get("title", "unknown")

        if episode_key not in self.episodes:
            self.episodes[episode_key] = EpisodeStatus(
                title=episode.get("title", episode_key),
                show=episode.get("show"),
                directory=episode.get("directory"),
            )
            self._save()

        return episode_key

    def get_status(self, episode_key: str) -> Optional[EpisodeStatus]:
        """Get status for episode.

        Args:
            episode_key: Episode identifier

        Returns:
            EpisodeStatus or None
        """
        return self.episodes.get(episode_key)

    def display_status_table(self) -> None:
        """Display status table with Rich."""
        if not self.episodes:
            console.print("[yellow]No episodes tracked[/yellow]")
            return

        # Create table
        table = Table(title="Batch Processing Status", show_header=True)
        table.add_column("Episode", style="cyan", no_wrap=True)
        table.add_column("Show", style="magenta")
        table.add_column("Fetch", justify="center")
        table.add_column("Transcode", justify="center")
        table.add_column("Transcribe", justify="center")
        table.add_column("Diarize", justify="center")
        table.add_column("Preprocess", justify="center")
        table.add_column("Deepcast", justify="center")
        table.add_column("Export", justify="center")

        # Add rows
        for episode in self.episodes.values():
            table.add_row(
                episode.title,
                episode.show or "-",
                self._state_icon(episode.fetch),
                self._state_icon(episode.transcode),
                self._state_icon(episode.transcribe),
                self._state_icon(episode.diarize),
                self._state_icon(episode.preprocess),
                self._state_icon(episode.deepcast),
                self._state_icon(episode.export),
            )

        console.print(table)

    def export_json(self, output_path: Path) -> None:
        """Export status to JSON file.

        Args:
            output_path: Output file path
        """
        data = {
            key: asdict(status) for key, status in self.episodes.items()
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        console.print(f"[green]Status exported to {output_path}[/green]")

    def export_csv(self, output_path: Path) -> None:
        """Export status to CSV file.

        Args:
            output_path: Output file path
        """
        import csv

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "Episode",
                "Show",
                "Fetch",
                "Transcode",
                "Transcribe",
                "Diarize",
                "Preprocess",
                "Deepcast",
                "Export",
            ])

            # Rows
            for episode in self.episodes.values():
                writer.writerow([
                    episode.title,
                    episode.show or "",
                    episode.fetch.value,
                    episode.transcode.value,
                    episode.transcribe.value,
                    episode.diarize.value,
                    episode.preprocess.value,
                    episode.deepcast.value,
                    episode.export.value,
                ])

        console.print(f"[green]Status exported to {output_path}[/green]")

    def clear_completed(self) -> int:
        """Clear completed episodes from tracking.

        Returns:
            Number of episodes cleared
        """
        completed = []

        for key, episode in self.episodes.items():
            if episode.export == ProcessingState.COMPLETED:
                completed.append(key)

        for key in completed:
            del self.episodes[key]

        if completed:
            self._save()
            console.print(f"[green]Cleared {len(completed)} completed episodes[/green]")

        return len(completed)

    def _state_icon(self, state: ProcessingState) -> str:
        """Get icon for processing state.

        Args:
            state: Processing state

        Returns:
            Icon string
        """
        icons = {
            ProcessingState.NOT_STARTED: "○",
            ProcessingState.IN_PROGRESS: "⏳",
            ProcessingState.COMPLETED: "✓",
            ProcessingState.FAILED: "✗",
        }
        return icons.get(state, "?")

    def _load(self) -> None:
        """Load status from disk."""
        if not self.status_file.exists():
            return

        try:
            with open(self.status_file) as f:
                data = json.load(f)

            for key, episode_data in data.items():
                # Convert state strings to enums
                for field in ["fetch", "transcode", "transcribe", "diarize", "preprocess", "deepcast", "export"]:
                    if field in episode_data:
                        episode_data[field] = ProcessingState(episode_data[field])

                self.episodes[key] = EpisodeStatus(**episode_data)

        except Exception as e:
            logger.warning(f"Failed to load batch status: {e}")

    def _save(self) -> None:
        """Save status to disk."""
        try:
            data = {
                key: asdict(status) for key, status in self.episodes.items()
            }

            with open(self.status_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save batch status: {e}")
