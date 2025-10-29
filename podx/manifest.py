"""Episode manifest tracking system.

Tracks processed episodes, pipeline sessions, and progress in a central manifest.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class StageInfo(BaseModel):
    """Information about a pipeline stage."""

    completed: bool = False
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    model: Optional[str] = None
    files: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    progress: float = 0.0  # 0.0 to 1.0
    status: Optional[str] = None  # Human-readable status
    error: Optional[str] = None


class EpisodeManifest(BaseModel):
    """Manifest entry for a single episode."""

    show: str
    date: str
    title: Optional[str] = None
    path: str
    stages: Dict[str, StageInfo] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class PipelineSession(BaseModel):
    """A pipeline processing session."""

    id: str = Field(default_factory=lambda: f"session-{uuid4().hex[:8]}")
    episode_show: str
    episode_date: str
    pipeline: List[str]  # Ordered list of stages
    current_stage: Optional[str] = None
    current_stage_index: int = 0
    status: str = "pending"  # pending, running, completed, failed, paused
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None


class Manifest(BaseModel):
    """Root manifest tracking all episodes and sessions."""

    version: str = "2.0.0"
    episodes: List[EpisodeManifest] = Field(default_factory=list)
    sessions: List[PipelineSession] = Field(default_factory=list)


class ManifestManager:
    """Manages the episode manifest file."""

    def __init__(self, root_dir: Optional[Path] = None):
        """Initialize manifest manager.

        Args:
            root_dir: Root directory for manifest. Defaults to current directory.
        """
        self.root_dir = root_dir or Path.cwd()
        self.manifest_dir = self.root_dir / ".podx"
        self.manifest_file = self.manifest_dir / "manifest.json"

    def load(self) -> Manifest:
        """Load manifest from disk or create new one."""
        if self.manifest_file.exists():
            try:
                data = json.loads(self.manifest_file.read_text())
                return Manifest.model_validate(data)
            except Exception:
                # If manifest is corrupted, create new one
                return Manifest()
        return Manifest()

    def save(self, manifest: Manifest) -> None:
        """Save manifest to disk."""
        self.manifest_dir.mkdir(exist_ok=True)
        self.manifest_file.write_text(
            manifest.model_dump_json(indent=2, exclude_none=True)
        )

    # ============================================================================
    # Episode Management
    # ============================================================================

    def get_episode(
        self, manifest: Manifest, show: str, date: str
    ) -> Optional[EpisodeManifest]:
        """Get episode from manifest."""
        for episode in manifest.episodes:
            if episode.show == show and episode.date == date:
                return episode
        return None

    def add_or_update_episode(
        self,
        show: str,
        date: str,
        title: Optional[str] = None,
        path: Optional[str] = None,
    ) -> EpisodeManifest:
        """Add new episode or update existing one.

        Args:
            show: Show name
            date: Episode date (YYYY-MM-DD)
            title: Episode title
            path: Episode directory path

        Returns:
            The episode manifest entry
        """
        manifest = self.load()

        # Find existing episode
        episode = self.get_episode(manifest, show, date)

        if episode:
            # Update existing
            if title:
                episode.title = title
            if path:
                episode.path = path
            episode.updated_at = datetime.now().isoformat()
        else:
            # Create new
            episode = EpisodeManifest(
                show=show,
                date=date,
                title=title or "",
                path=path or f"{show}/{date}",
            )
            manifest.episodes.append(episode)

        self.save(manifest)
        return episode

    def start_stage(
        self,
        show: str,
        date: str,
        stage: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a stage as started.

        Args:
            show: Show name
            date: Episode date
            stage: Stage name
            model: Model being used
            metadata: Additional metadata
        """
        manifest = self.load()

        episode = self.get_episode(manifest, show, date)
        if not episode:
            episode = EpisodeManifest(show=show, date=date, path=f"{show}/{date}")
            manifest.episodes.append(episode)

        stage_info = StageInfo(
            completed=False,
            started_at=datetime.now().isoformat(),
            model=model,
            metadata=metadata or {},
            progress=0.0,
            status="Starting...",
        )
        episode.stages[stage] = stage_info
        episode.updated_at = datetime.now().isoformat()

        self.save(manifest)

    def update_stage_progress(
        self,
        show: str,
        date: str,
        stage: str,
        progress: float,
        status: Optional[str] = None,
    ) -> None:
        """Update progress for a running stage.

        Args:
            show: Show name
            date: Episode date
            stage: Stage name
            progress: Progress from 0.0 to 1.0
            status: Human-readable status message
        """
        manifest = self.load()

        episode = self.get_episode(manifest, show, date)
        if not episode or stage not in episode.stages:
            return

        episode.stages[stage].progress = progress
        if status:
            episode.stages[stage].status = status
        episode.updated_at = datetime.now().isoformat()

        self.save(manifest)

    def complete_stage(
        self,
        show: str,
        date: str,
        stage: str,
        files: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a stage as completed.

        Args:
            show: Show name
            date: Episode date
            stage: Stage name
            files: Output files created
            metadata: Additional metadata
        """
        manifest = self.load()

        episode = self.get_episode(manifest, show, date)
        if not episode:
            return

        if stage in episode.stages:
            stage_info = episode.stages[stage]
            stage_info.completed = True
            stage_info.completed_at = datetime.now().isoformat()
            stage_info.progress = 1.0
            stage_info.status = "Completed"
            if files:
                stage_info.files = files
            if metadata:
                stage_info.metadata.update(metadata)
        else:
            # Create completed stage
            episode.stages[stage] = StageInfo(
                completed=True,
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                files=files or [],
                metadata=metadata or {},
                progress=1.0,
                status="Completed",
            )

        episode.updated_at = datetime.now().isoformat()
        self.save(manifest)

    def fail_stage(
        self,
        show: str,
        date: str,
        stage: str,
        error: str,
    ) -> None:
        """Mark a stage as failed.

        Args:
            show: Show name
            date: Episode date
            stage: Stage name
            error: Error message
        """
        manifest = self.load()

        episode = self.get_episode(manifest, show, date)
        if not episode or stage not in episode.stages:
            return

        episode.stages[stage].error = error
        episode.stages[stage].status = f"Failed: {error}"
        episode.updated_at = datetime.now().isoformat()

        self.save(manifest)

    def get_all_episodes(self) -> List[EpisodeManifest]:
        """Get all episodes from manifest."""
        manifest = self.load()
        # Sort by date, newest first
        return sorted(
            manifest.episodes,
            key=lambda e: (e.show, e.date),
            reverse=True,
        )

    def get_episodes_by_stage(
        self, stage: str, completed: bool = True
    ) -> List[EpisodeManifest]:
        """Get episodes filtered by stage completion.

        Args:
            stage: Stage name to filter by
            completed: Whether to filter for completed or incomplete

        Returns:
            List of matching episodes
        """
        manifest = self.load()
        return [
            ep
            for ep in manifest.episodes
            if stage in ep.stages and ep.stages[stage].completed == completed
        ]

    # ============================================================================
    # Session Management
    # ============================================================================

    def create_session(
        self,
        show: str,
        date: str,
        pipeline: List[str],
    ) -> PipelineSession:
        """Create a new pipeline session.

        Args:
            show: Show name
            date: Episode date
            pipeline: Ordered list of stage names

        Returns:
            The created session
        """
        manifest = self.load()

        session = PipelineSession(
            episode_show=show,
            episode_date=date,
            pipeline=pipeline,
            current_stage=pipeline[0] if pipeline else None,
            current_stage_index=0,
            status="pending",
        )

        manifest.sessions.append(session)
        self.save(manifest)

        return session

    def get_session(self, session_id: str) -> Optional[PipelineSession]:
        """Get session by ID."""
        manifest = self.load()
        for session in manifest.sessions:
            if session.id == session_id:
                return session
        return None

    def update_session_stage(
        self,
        session_id: str,
        stage_index: int,
        status: str = "running",
    ) -> None:
        """Update current stage in session.

        Args:
            session_id: Session ID
            stage_index: Index of current stage
            status: Session status
        """
        manifest = self.load()

        for session in manifest.sessions:
            if session.id == session_id:
                session.current_stage_index = stage_index
                if stage_index < len(session.pipeline):
                    session.current_stage = session.pipeline[stage_index]
                session.status = status
                break

        self.save(manifest)

    def complete_session(self, session_id: str) -> None:
        """Mark session as completed."""
        manifest = self.load()

        for session in manifest.sessions:
            if session.id == session_id:
                session.status = "completed"
                session.completed_at = datetime.now().isoformat()
                break

        self.save(manifest)

    def fail_session(self, session_id: str, error: str) -> None:
        """Mark session as failed."""
        manifest = self.load()

        for session in manifest.sessions:
            if session.id == session_id:
                session.status = "failed"
                session.error = error
                session.completed_at = datetime.now().isoformat()
                break

        self.save(manifest)

    def get_incomplete_sessions(self) -> List[PipelineSession]:
        """Get all incomplete sessions."""
        manifest = self.load()
        return [
            s
            for s in manifest.sessions
            if s.status in ("pending", "running", "paused")
        ]

    def get_episode_sessions(self, show: str, date: str) -> List[PipelineSession]:
        """Get all sessions for an episode."""
        manifest = self.load()
        return [
            s
            for s in manifest.sessions
            if s.episode_show == show and s.episode_date == date
        ]

    # ============================================================================
    # Filesystem Sync
    # ============================================================================

    def scan_and_sync(self) -> Manifest:
        """Scan filesystem and sync with manifest.

        This scans the directory structure for episodes and updates the manifest
        with any episodes that aren't tracked yet.

        Returns:
            Updated manifest
        """
        manifest = self.load()

        # Scan for episode directories (show/YYYY-MM-DD/)
        for show_dir in self.root_dir.iterdir():
            if not show_dir.is_dir() or show_dir.name.startswith("."):
                continue

            for episode_dir in show_dir.iterdir():
                if not episode_dir.is_dir():
                    continue

                show = show_dir.name
                date = episode_dir.name

                # Get or create episode entry
                episode = self.get_episode(manifest, show, date)
                if not episode:
                    episode = EpisodeManifest(
                        show=show,
                        date=date,
                        path=str(episode_dir.relative_to(self.root_dir)),
                    )
                    manifest.episodes.append(episode)

                # Detect stages from files
                self._detect_stages(episode, episode_dir)

        self.save(manifest)
        return manifest

    def _detect_stages(self, episode: EpisodeManifest, episode_dir: Path) -> None:
        """Detect completed stages from filesystem.

        Args:
            episode: Episode manifest entry to update
            episode_dir: Episode directory path
        """
        # Fetch stage
        if (episode_dir / "episode-meta.json").exists():
            if "fetch" not in episode.stages or not episode.stages["fetch"].completed:
                episode.stages["fetch"] = StageInfo(
                    completed=True,
                    files=["episode-meta.json"],
                )

        # Transcribe stage
        transcripts = list(episode_dir.glob("transcript*.json"))
        if transcripts:
            if "transcribe" not in episode.stages or not episode.stages["transcribe"].completed:
                episode.stages["transcribe"] = StageInfo(
                    completed=True,
                    files=[t.name for t in transcripts],
                )

        # Diarize stage
        if (episode_dir / "diarized.json").exists():
            if "diarize" not in episode.stages or not episode.stages["diarize"].completed:
                episode.stages["diarize"] = StageInfo(
                    completed=True,
                    files=["diarized.json"],
                )

        # Deepcast stage
        deepcast_files = list(episode_dir.glob("deepcast*.json"))
        if deepcast_files:
            if "deepcast" not in episode.stages or not episode.stages["deepcast"].completed:
                episode.stages["deepcast"] = StageInfo(
                    completed=True,
                    files=[f.name for f in deepcast_files],
                )

        # Export stage
        exports = (
            list(episode_dir.glob("*.txt"))
            + list(episode_dir.glob("*.srt"))
            + list(episode_dir.glob("*.vtt"))
        )
        if exports:
            if "export" not in episode.stages or not episode.stages["export"].completed:
                episode.stages["export"] = StageInfo(
                    completed=True,
                    files=[f.name for f in exports],
                )

        # Notion stage
        if (episode_dir / "notion.out.json").exists():
            if "notion" not in episode.stages or not episode.stages["notion"].completed:
                episode.stages["notion"] = StageInfo(
                    completed=True,
                    files=["notion.out.json"],
                )
