"""Cleanup step executor for removing intermediate files."""

import time
from typing import Any, Optional

from podx.logging import get_logger

from .base import PipelineStep, StepContext, StepResult

logger = get_logger(__name__)


class CleanupStep(PipelineStep):
    """Execute optional file cleanup after pipeline completion.

    Removes intermediate transcript files and optionally audio files,
    while preserving final artifacts like latest.json, exported files,
    and deepcast outputs.
    """

    def __init__(self, clean: bool, no_keep_audio: bool):
        """Initialize cleanup step.

        Args:
            clean: Enable cleanup of intermediate files
            no_keep_audio: Also remove audio files
        """
        self.clean = clean
        self.no_keep_audio = no_keep_audio

    @property
    def name(self) -> str:
        return "Cleanup Intermediate Files"

    def should_skip(self, context: StepContext) -> tuple[bool, Optional[str]]:
        """Check if cleanup should be skipped."""
        if not self.clean:
            return True, "Cleanup disabled"
        return False, None

    def execute(
        self, context: StepContext, progress: Any, verbose: bool = False
    ) -> StepResult:
        """Execute cleanup step."""
        if not self.clean:
            return StepResult.skip("Cleanup disabled")

        progress.start_step("Cleaning up intermediate files")
        step_start = time.time()

        wd = context.working_dir
        latest_name = context.latest_transcript_name

        # Keep final artifacts
        keep = {
            wd / "latest.json",
            wd / f"{latest_name}.txt",
            wd / f"{latest_name}.srt",
            wd / "notion.out.json",
            wd / "episode-meta.json",
            wd / "audio-meta.json",
        }
        # Keep all deepcast files (both new and legacy formats)
        keep.update(wd.glob("deepcast-*.json"))
        keep.update(wd.glob("deepcast-*.md"))

        cleaned_files = 0

        # Remove intermediate JSON files (both legacy and model-specific)
        cleanup_patterns = [
            "transcript.json",
            "transcript-*.json",
            # Legacy align/diarize formats (old)
            "aligned-transcript.json",
            "aligned-transcript-*.json",
            "diarized-transcript.json",
            "diarized-transcript-*.json",
            # New align/diarize formats
            "transcript-aligned.json",
            "transcript-aligned-*.json",
            "transcript-diarized.json",
            "transcript-diarized-*.json",
        ]
        for pattern in cleanup_patterns:
            for p in wd.glob(pattern):
                if p.exists() and p not in keep:
                    try:
                        p.unlink()
                        cleaned_files += 1
                        logger.debug("Cleaned intermediate file", file=str(p))
                    except Exception as e:
                        logger.warning(
                            "Failed to clean file", file=str(p), error=str(e)
                        )

        # Remove audio files if not keeping them
        if self.no_keep_audio:
            for p in [context.transcoded_audio_path, context.original_audio_path]:
                if p and p.exists():
                    try:
                        p.unlink()
                        cleaned_files += 1
                        logger.debug("Cleaned audio file", file=str(p))
                    except Exception as e:
                        logger.warning(
                            "Failed to clean audio file", file=str(p), error=str(e)
                        )

        step_duration = time.time() - step_start
        progress.complete_step(
            f"Cleanup completed ({cleaned_files} files removed)", step_duration
        )

        return StepResult.ok(
            f"Cleanup completed ({cleaned_files} files removed)",
            duration=step_duration,
            data={"files_removed": cleaned_files},
        )
