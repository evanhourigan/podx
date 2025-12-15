"""Artifact detection for pipeline steps."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from ..domain import PipelineStep


@dataclass
class EpisodeArtifacts:
    """Detected artifacts for an episode."""

    working_dir: Path
    episode_meta: Optional[Path] = None
    audio_meta: Optional[Path] = None
    transcripts: List[Path] = field(default_factory=list)
    aligned_transcripts: List[Path] = field(default_factory=list)
    diarized_transcripts: List[Path] = field(default_factory=list)
    preprocessed_transcripts: List[Path] = field(default_factory=list)
    deepcasts: List[Path] = field(default_factory=list)
    agreements: List[Path] = field(default_factory=list)
    consensus: List[Path] = field(default_factory=list)
    notion_output: Optional[Path] = None

    @property
    def has_transcripts(self) -> bool:
        """Check if any transcripts exist."""
        return bool(self.transcripts)

    @property
    def has_aligned(self) -> bool:
        """Check if aligned transcripts exist."""
        return bool(self.aligned_transcripts)

    @property
    def has_diarized(self) -> bool:
        """Check if diarized transcripts exist."""
        return bool(self.diarized_transcripts)

    @property
    def has_preprocessed(self) -> bool:
        """Check if preprocessed transcripts exist."""
        return bool(self.preprocessed_transcripts)

    @property
    def has_deepcast(self) -> bool:
        """Check if deepcast analyses exist."""
        return bool(self.deepcasts)

    @property
    def has_notion(self) -> bool:
        """Check if Notion output exists."""
        return self.notion_output is not None and self.notion_output.exists()


class ArtifactDetector:
    """Detect completed pipeline steps from artifacts."""

    # Artifact patterns for each pipeline step
    ARTIFACT_PATTERNS = {
        PipelineStep.FETCH: ["episode-meta.json"],
        PipelineStep.TRANSCODE: ["audio-meta.json"],
        PipelineStep.TRANSCRIBE: [
            "transcript-*.json",
            "transcript.json",  # Legacy
        ],
        PipelineStep.ALIGN: [
            "transcript-aligned-*.json",
            "aligned-transcript-*.json",
            "aligned-transcript.json",  # Legacy
        ],
        PipelineStep.DIARIZE: [
            "transcript-diarized-*.json",
            "diarized-transcript-*.json",
            "diarized-transcript.json",  # Legacy
        ],
        PipelineStep.PREPROCESS: [
            "transcript-preprocessed-*.json",
        ],
        PipelineStep.DEEPCAST: [
            "deepcast-*.json",
            "deepcast.json",  # Base file without suffix
        ],
        PipelineStep.NOTION: [
            "notion.out.json",
        ],
    }

    def __init__(self, working_dir: Path):
        """Initialize artifact detector.

        Args:
            working_dir: Directory to scan for artifacts
        """
        self.working_dir = Path(working_dir)

    def detect_all(self) -> EpisodeArtifacts:
        """Detect all artifacts in the working directory.

        Returns:
            EpisodeArtifacts with all detected files
        """
        artifacts = EpisodeArtifacts(working_dir=self.working_dir)

        # Detect episode metadata
        episode_meta = self.working_dir / "episode-meta.json"
        if episode_meta.exists():
            artifacts.episode_meta = episode_meta

        # Detect audio metadata
        audio_meta = self.working_dir / "audio-meta.json"
        if audio_meta.exists():
            artifacts.audio_meta = audio_meta

        # Detect transcripts (all patterns)
        artifacts.transcripts = self._find_files(
            [
                "transcript-*.json",
                "transcript.json",
            ]
        )

        # Detect aligned transcripts (all patterns)
        artifacts.aligned_transcripts = self._find_files(
            [
                "transcript-aligned-*.json",
                "aligned-transcript-*.json",
                "aligned-transcript.json",
            ]
        )

        # Detect diarized transcripts (all patterns)
        artifacts.diarized_transcripts = self._find_files(
            [
                "transcript-diarized-*.json",
                "diarized-transcript-*.json",
                "diarized-transcript.json",
            ]
        )

        # Detect preprocessed transcripts
        artifacts.preprocessed_transcripts = self._find_files(
            [
                "transcript-preprocessed-*.json",
            ]
        )

        # Detect deepcast analyses
        artifacts.deepcasts = self._find_files(
            [
                "deepcast-*.json",
                "deepcast.json",  # Base file without suffix
            ]
        )

        # Detect agreements
        artifacts.agreements = self._find_files(["agreement-*.json"])

        # Detect consensus
        artifacts.consensus = self._find_files(["consensus-*.json"])

        # Detect Notion output
        notion_out = self.working_dir / "notion.out.json"
        if notion_out.exists():
            artifacts.notion_output = notion_out

        return artifacts

    def detect_completed_steps(self) -> Set[PipelineStep]:
        """Detect which pipeline steps have been completed.

        Returns:
            Set of completed pipeline steps
        """
        completed = set()
        artifacts = self.detect_all()

        # Check each step
        if artifacts.episode_meta:
            completed.add(PipelineStep.FETCH)

        if artifacts.audio_meta:
            completed.add(PipelineStep.TRANSCODE)

        if artifacts.has_transcripts:
            completed.add(PipelineStep.TRANSCRIBE)

        if artifacts.has_aligned:
            completed.add(PipelineStep.ALIGN)

        if artifacts.has_diarized:
            completed.add(PipelineStep.DIARIZE)

        if artifacts.has_preprocessed:
            completed.add(PipelineStep.PREPROCESS)

        if artifacts.has_deepcast:
            completed.add(PipelineStep.DEEPCAST)

        if artifacts.has_notion:
            completed.add(PipelineStep.NOTION)

        return completed

    def get_artifact_for_step(self, step: PipelineStep) -> Optional[Path]:
        """Get the primary artifact for a pipeline step.

        Args:
            step: Pipeline step to get artifact for

        Returns:
            Path to primary artifact, or None if not found
        """
        artifacts = self.detect_all()

        if step == PipelineStep.FETCH:
            return artifacts.episode_meta
        elif step == PipelineStep.TRANSCODE:
            return artifacts.audio_meta
        elif step == PipelineStep.TRANSCRIBE:
            return artifacts.transcripts[0] if artifacts.transcripts else None
        elif step == PipelineStep.ALIGN:
            return artifacts.aligned_transcripts[0] if artifacts.aligned_transcripts else None
        elif step == PipelineStep.DIARIZE:
            return artifacts.diarized_transcripts[0] if artifacts.diarized_transcripts else None
        elif step == PipelineStep.PREPROCESS:
            return (
                artifacts.preprocessed_transcripts[0]
                if artifacts.preprocessed_transcripts
                else None
            )
        elif step == PipelineStep.DEEPCAST:
            return artifacts.deepcasts[0] if artifacts.deepcasts else None
        elif step == PipelineStep.NOTION:
            return artifacts.notion_output
        else:
            return None

    def _find_files(self, patterns: List[str]) -> List[Path]:
        """Find files matching any of the given patterns.

        Args:
            patterns: List of glob patterns to match

        Returns:
            List of matching file paths
        """
        files: List[Path] = []
        for pattern in patterns:
            files.extend(self.working_dir.glob(pattern))
        # Remove duplicates and sort
        return sorted(set(files))
