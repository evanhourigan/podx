"""Pipeline execution state management."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

from ..domain import PipelineConfig, PipelineStep
from .artifact_detector import ArtifactDetector, EpisodeArtifacts


class RunState:
    """Manages pipeline execution state and resumption."""

    STATE_FILENAME = "run-state.json"

    def __init__(
        self,
        working_dir: Path,
        config: Optional[PipelineConfig] = None,
    ):
        """Initialize run state.

        Args:
            working_dir: Working directory for the pipeline
            config: Pipeline configuration (optional)
        """
        self.working_dir = Path(working_dir)
        self.config = config or PipelineConfig()
        self.completed_steps: Set[PipelineStep] = set()
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self._detector = ArtifactDetector(working_dir)

    @classmethod
    def load(cls, working_dir: Path) -> Optional["RunState"]:
        """Load saved state from run-state.json.

        Args:
            working_dir: Working directory to load state from

        Returns:
            RunState instance if state file exists, None otherwise
        """
        working_dir = Path(working_dir)
        state_file = working_dir / cls.STATE_FILENAME

        if not state_file.exists():
            return None

        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))

            # Create instance
            state = cls(working_dir)

            # Load completed steps
            if "completed_steps" in data:
                state.completed_steps = {
                    PipelineStep(step) for step in data["completed_steps"]
                }

            # Load metadata
            if "metadata" in data:
                state.metadata = data["metadata"]

            # Load timestamps
            if "created_at" in data:
                state.created_at = datetime.fromisoformat(data["created_at"])
            if "updated_at" in data:
                state.updated_at = datetime.fromisoformat(data["updated_at"])

            # Load config (if present)
            if "config" in data:
                state.metadata["saved_config"] = data["config"]

            return state

        except Exception:
            # If loading fails, return None
            return None

    def save(self) -> None:
        """Persist state to disk."""
        self.updated_at = datetime.now()

        state_file = self.working_dir / self.STATE_FILENAME

        data = {
            "completed_steps": [step.value for step in self.completed_steps],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

        state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def mark_completed(self, step: PipelineStep) -> None:
        """Mark a pipeline step as completed.

        Args:
            step: Pipeline step to mark as completed
        """
        self.completed_steps.add(step)
        self.save()

    def is_completed(self, step: PipelineStep) -> bool:
        """Check if a pipeline step has been completed.

        Args:
            step: Pipeline step to check

        Returns:
            True if step is completed, False otherwise
        """
        return step in self.completed_steps

    def get_artifact_path(self, step: PipelineStep) -> Optional[Path]:
        """Get path to the primary artifact for a step.

        Args:
            step: Pipeline step to get artifact for

        Returns:
            Path to primary artifact, or None if not found
        """
        return self._detector.get_artifact_for_step(step)

    def detect_completed_steps(self) -> Set[PipelineStep]:
        """Scan working directory for artifacts and detect completed steps.

        Returns:
            Set of completed pipeline steps based on artifacts
        """
        detected = self._detector.detect_completed_steps()
        # Update our completed_steps with detected artifacts
        self.completed_steps.update(detected)
        return detected

    def get_artifacts(self) -> EpisodeArtifacts:
        """Get all detected artifacts.

        Returns:
            EpisodeArtifacts with all detected files
        """
        return self._detector.detect_all()

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of state
        """
        return {
            "working_dir": str(self.working_dir),
            "completed_steps": [step.value for step in self.completed_steps],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
