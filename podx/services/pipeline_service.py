"""Pipeline service for high-level orchestration."""

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..domain import PipelineConfig, PipelineResult
from ..logging import get_logger
from ..state import ArtifactDetector, EpisodeArtifacts
from .step_executor import StepExecutor

logger = get_logger(__name__)


class PipelineService:
    """High-level pipeline orchestration service.

    This service coordinates the execution of individual pipeline steps,
    manages state and artifacts, and handles resumption logic.

    Examples:
        >>> config = PipelineConfig(show="My Podcast", align=True, deepcast=True)
        >>> service = PipelineService(config)
        >>> result = service.execute()
    """

    def __init__(
        self,
        config: PipelineConfig,
        executor: Optional[StepExecutor] = None,
    ):
        """Initialize pipeline service.

        Args:
            config: Pipeline configuration
            executor: Optional step executor (created if not provided)
        """
        self.config = config
        self.executor = executor or StepExecutor(verbose=config.verbose)
        self.start_time = 0.0

    def execute(
        self,
        skip_completed: bool = True,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> PipelineResult:
        """Execute the complete pipeline.

        Args:
            skip_completed: Skip steps that have already been completed
            progress_callback: Optional callback for progress updates (step_name, status)

        Returns:
            PipelineResult with execution details

        Raises:
            ValidationError: If configuration is invalid or execution fails
        """
        self.start_time = time.time()
        result = PipelineResult(workdir=Path("."))

        try:
            # 1. Fetch episode metadata
            meta = self._execute_fetch(result, progress_callback)

            # 2. Determine working directory
            workdir = self._determine_workdir(meta)
            result.workdir = workdir
            workdir.mkdir(parents=True, exist_ok=True)

            # Save metadata
            (workdir / "episode-meta.json").write_text(json.dumps(meta, indent=2))
            result.artifacts["meta"] = str(workdir / "episode-meta.json")

            # 3. Initialize state management
            # Note: RunState will be used in future for resumption logic
            detector = ArtifactDetector(workdir)
            artifacts = detector.detect_all()

            # 4. Execute pipeline steps
            self._execute_transcode(workdir, meta, artifacts, result, progress_callback)
            latest = self._execute_transcribe(
                workdir, artifacts, result, skip_completed, progress_callback
            )
            latest = self._execute_preprocess(
                workdir, latest, artifacts, result, skip_completed, progress_callback
            )
            latest = self._execute_align(
                workdir, latest, artifacts, result, skip_completed, progress_callback
            )
            latest = self._execute_diarize(
                workdir, latest, artifacts, result, skip_completed, progress_callback
            )

            # Always save latest.json
            (workdir / "latest.json").write_text(json.dumps(latest, indent=2))

            # 5. Export transcript formats
            self._execute_export(workdir, latest, result, progress_callback)

            # 6. Execute deepcast analysis
            if self.config.deepcast or self.config.dual:
                self._execute_deepcast(workdir, latest, result, progress_callback)

            # 7. Upload to Notion
            if self.config.notion and not self.config.dual:
                self._execute_notion(workdir, result, progress_callback)

            # 8. Cleanup
            if self.config.clean:
                self._execute_cleanup(workdir, result, progress_callback)

            # Update duration
            result.duration = time.time() - self.start_time

        except Exception as e:
            result.errors.append(str(e))
            logger.error("Pipeline execution failed", error=str(e))
            raise

        return result

    def _execute_fetch(
        self,
        result: PipelineResult,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute fetch step.

        Args:
            result: Pipeline result to update
            progress_callback: Optional progress callback

        Returns:
            Episode metadata dictionary
        """
        if progress_callback:
            progress_callback("fetch", "started")

        meta = self.executor.fetch(
            show=self.config.show,
            rss_url=self.config.rss_url,
            youtube_url=self.config.youtube_url,
            date=self.config.date,
            title_contains=self.config.title_contains,
        )

        result.steps_completed.append("fetch")
        if progress_callback:
            progress_callback("fetch", "completed")

        return meta

    def _determine_workdir(self, meta: Dict[str, Any]) -> Path:
        """Determine working directory from metadata.

        Args:
            meta: Episode metadata

        Returns:
            Working directory path
        """
        if self.config.workdir:
            return self.config.workdir

        # Generate smart workdir from show name and date
        from ..fetch import _generate_workdir

        show_name = meta.get("show", "Unknown Show")
        episode_date = meta.get("episode_published") or self.config.date or "unknown"
        return _generate_workdir(show_name, episode_date)

    def _execute_transcode(
        self,
        workdir: Path,
        meta: Dict[str, Any],
        artifacts: EpisodeArtifacts,
        result: PipelineResult,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute transcode step.

        Args:
            workdir: Working directory
            meta: Episode metadata
            artifacts: Detected artifacts
            result: Pipeline result to update
            progress_callback: Optional progress callback

        Returns:
            Audio metadata dictionary
        """
        audio_meta_file = workdir / "audio-meta.json"

        if audio_meta_file.exists():
            logger.info("Found existing audio metadata, skipping transcode")
            audio = json.loads(audio_meta_file.read_text())
            if progress_callback:
                progress_callback("transcode", "skipped")
            return audio

        if progress_callback:
            progress_callback("transcode", "started")

        # Convert fmt enum to string value if needed
        fmt_value = self.config.fmt.value if hasattr(self.config.fmt, "value") else self.config.fmt

        audio = self.executor.transcode(
            meta=meta,
            fmt=fmt_value,
            outdir=workdir,
            save_to=audio_meta_file,
        )

        result.steps_completed.append("transcode")
        result.artifacts["audio"] = str(audio_meta_file)
        if progress_callback:
            progress_callback("transcode", "completed")

        return audio

    def _execute_transcribe(
        self,
        workdir: Path,
        artifacts: EpisodeArtifacts,
        result: PipelineResult,
        skip_completed: bool,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute transcribe step.

        Args:
            workdir: Working directory
            artifacts: Detected artifacts
            result: Pipeline result to update
            skip_completed: Skip if already completed
            progress_callback: Optional progress callback

        Returns:
            Transcript dictionary
        """
        # Simplified version - full implementation would handle dual mode
        audio_meta_file = workdir / "audio-meta.json"
        audio = json.loads(audio_meta_file.read_text())

        # Check for existing transcript
        transcript_file = workdir / f"transcript-{self.config.model}.json"
        if skip_completed and transcript_file.exists():
            logger.info("Found existing transcript, skipping transcription")
            transcript = json.loads(transcript_file.read_text())
            if progress_callback:
                progress_callback("transcribe", "skipped")
            return transcript

        if progress_callback:
            progress_callback("transcribe", "started")

        # Convert preset enum to string value if needed
        preset_value = getattr(self.config.preset, "value", self.config.preset)

        transcript = self.executor.transcribe(
            audio=audio,
            model=self.config.model,
            compute=self.config.compute,
            asr_provider=self.config.asr_provider,
            preset=preset_value,
            save_to=transcript_file,
        )

        result.steps_completed.append("transcribe")
        result.artifacts["transcript"] = str(transcript_file)
        if progress_callback:
            progress_callback("transcribe", "completed")

        return transcript

    def _execute_preprocess(
        self,
        workdir: Path,
        latest: Dict[str, Any],
        artifacts: EpisodeArtifacts,
        result: PipelineResult,
        skip_completed: bool,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute preprocess step.

        Args:
            workdir: Working directory
            latest: Latest transcript
            artifacts: Detected artifacts
            result: Pipeline result to update
            skip_completed: Skip if already completed
            progress_callback: Optional progress callback

        Returns:
            Preprocessed transcript dictionary
        """
        if not self.config.preprocess and not self.config.dual:
            return latest

        # Check for existing preprocessed transcript
        model = latest.get("asr_model", self.config.model)
        preprocessed_file = workdir / f"transcript-preprocessed-{model}.json"

        if skip_completed and preprocessed_file.exists():
            logger.info("Found existing preprocessed transcript, skipping")
            preprocessed = json.loads(preprocessed_file.read_text())
            if progress_callback:
                progress_callback("preprocess", "skipped")
            return preprocessed

        if progress_callback:
            progress_callback("preprocess", "started")

        preprocessed = self.executor.preprocess(
            transcript=latest,
            restore=self.config.restore,
            save_to=preprocessed_file,
        )

        result.steps_completed.append("preprocess")
        result.artifacts["preprocessed"] = str(preprocessed_file)
        if progress_callback:
            progress_callback("preprocess", "completed")

        return preprocessed

    def _execute_align(
        self,
        workdir: Path,
        latest: Dict[str, Any],
        artifacts: EpisodeArtifacts,
        result: PipelineResult,
        skip_completed: bool,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute align step.

        Args:
            workdir: Working directory
            latest: Latest transcript
            artifacts: Detected artifacts
            result: Pipeline result to update
            skip_completed: Skip if already completed
            progress_callback: Optional progress callback

        Returns:
            Aligned transcript dictionary
        """
        if not self.config.align:
            return latest

        model = latest.get("asr_model", self.config.model)
        aligned_file = workdir / f"transcript-aligned-{model}.json"

        if skip_completed and aligned_file.exists():
            logger.info("Found existing aligned transcript, skipping")
            aligned = json.loads(aligned_file.read_text())
            if progress_callback:
                progress_callback("align", "skipped")
            return aligned

        if progress_callback:
            progress_callback("align", "started")

        aligned = self.executor.align(
            transcript=latest,
            save_to=aligned_file,
        )

        result.steps_completed.append("align")
        result.artifacts["aligned"] = str(aligned_file)
        if progress_callback:
            progress_callback("align", "completed")

        return aligned

    def _execute_diarize(
        self,
        workdir: Path,
        latest: Dict[str, Any],
        artifacts: EpisodeArtifacts,
        result: PipelineResult,
        skip_completed: bool,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute diarize step.

        Args:
            workdir: Working directory
            latest: Latest transcript
            artifacts: Detected artifacts
            result: Pipeline result to update
            skip_completed: Skip if already completed
            progress_callback: Optional progress callback

        Returns:
            Diarized transcript dictionary
        """
        if not self.config.diarize:
            return latest

        model = latest.get("asr_model", self.config.model)
        diarized_file = workdir / f"transcript-diarized-{model}.json"

        if skip_completed and diarized_file.exists():
            logger.info("Found existing diarized transcript, skipping")
            diarized = json.loads(diarized_file.read_text())
            if progress_callback:
                progress_callback("diarize", "skipped")
            return diarized

        if progress_callback:
            progress_callback("diarize", "started")

        diarized = self.executor.diarize(
            transcript=latest,
            save_to=diarized_file,
        )

        result.steps_completed.append("diarize")
        result.artifacts["diarized"] = str(diarized_file)
        if progress_callback:
            progress_callback("diarize", "completed")

        return diarized

    def _execute_export(
        self,
        workdir: Path,
        latest: Dict[str, Any],
        result: PipelineResult,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Execute export step.

        Args:
            workdir: Working directory
            latest: Latest transcript
            result: Pipeline result to update
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("export", "started")

        model = latest.get("asr_model", self.config.model)
        latest_name = f"transcript-{model}"

        export_result = self.executor.export(
            transcript=latest,
            formats="txt,srt",
            output_dir=workdir,
            input_path=workdir / f"{latest_name}.json",
            replace=True,
        )

        result.steps_completed.append("export")

        # Extract file paths from export result
        exported_files = export_result.get("files", {}) if isinstance(export_result, dict) else {}
        if "txt" in exported_files:
            result.artifacts["txt"] = exported_files["txt"]
        if "srt" in exported_files:
            result.artifacts["srt"] = exported_files["srt"]

        if progress_callback:
            progress_callback("export", "completed")

    def _execute_deepcast(
        self,
        workdir: Path,
        latest: Dict[str, Any],
        result: PipelineResult,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Execute deepcast step.

        Args:
            workdir: Working directory
            latest: Latest transcript
            result: Pipeline result to update
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("deepcast", "started")

        # Simplified version - full implementation would handle dual mode
        model_suffix = self.config.deepcast_model.replace(".", "_").replace("-", "_")
        json_out = workdir / f"deepcast-{model_suffix}.json"
        latest_path = workdir / "latest.json"
        meta_path = workdir / "episode-meta.json"

        # Convert analysis_type enum to string value if needed
        analysis_type_value = getattr(self.config.analysis_type, "value", self.config.analysis_type)

        self.executor.deepcast(
            input_path=latest_path,
            output_path=json_out,
            model=self.config.deepcast_model,
            temperature=self.config.deepcast_temp,
            meta_path=meta_path if meta_path.exists() else None,
            analysis_type=analysis_type_value,
            extract_markdown=self.config.extract_markdown,
            pdf=self.config.deepcast_pdf,
        )

        result.steps_completed.append("deepcast")
        result.artifacts["deepcast_json"] = str(json_out)

        # Check for markdown output
        md_out = workdir / f"deepcast-{model_suffix}.md"
        if md_out.exists():
            result.artifacts["deepcast_md"] = str(md_out)

        if progress_callback:
            progress_callback("deepcast", "completed")

    def _execute_notion(
        self,
        workdir: Path,
        result: PipelineResult,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Execute notion step.

        Args:
            workdir: Working directory
            result: Pipeline result to update
            progress_callback: Optional progress callback

        Raises:
            SystemExit: If notion_db is not configured
        """
        if not self.config.notion_db:
            raise SystemExit("Please pass --db or set NOTION_DB_ID environment variable")

        if progress_callback:
            progress_callback("notion", "started")

        # Find deepcast markdown file
        model_suffix = self.config.deepcast_model.replace(".", "_").replace("-", "_")
        deepcast_path = workdir / f"deepcast-{model_suffix}.md"

        if not deepcast_path.exists():
            logger.warning("No deepcast markdown found, skipping Notion upload")
            return

        self.executor.notion(
            deepcast_path=deepcast_path,
            database_id=self.config.notion_db,
            podcast_prop=self.config.podcast_prop,
            date_prop=self.config.date_prop,
            episode_prop=self.config.episode_prop,
            model_prop=self.config.model_prop,
            asr_prop=self.config.asr_prop,
            append_content=self.config.append_content,
        )

        result.steps_completed.append("notion")
        result.artifacts["notion"] = str(workdir / "notion.out.json")

        if progress_callback:
            progress_callback("notion", "completed")

    def _execute_cleanup(
        self,
        workdir: Path,
        result: PipelineResult,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Execute cleanup step.

        Args:
            workdir: Working directory
            result: Pipeline result to update
            progress_callback: Optional progress callback
        """
        if progress_callback:
            progress_callback("cleanup", "started")

        # Keep final artifacts
        keep = {
            workdir / "latest.json",
            workdir / "episode-meta.json",
            workdir / "audio-meta.json",
            workdir / "notion.out.json",
        }

        # Keep all deepcast files
        keep.update(workdir.glob("deepcast-*.json"))
        keep.update(workdir.glob("deepcast-*.md"))

        cleaned_files = 0

        # Remove intermediate JSON files
        cleanup_patterns = [
            "transcript.json",
            "transcript-*.json",
            "aligned-transcript*.json",
            "diarized-transcript*.json",
            "transcript-aligned-*.json",
            "transcript-diarized-*.json",
        ]

        for pattern in cleanup_patterns:
            for p in workdir.glob(pattern):
                if p.exists() and p not in keep:
                    try:
                        p.unlink()
                        cleaned_files += 1
                        logger.debug("Cleaned intermediate file", file=str(p))
                    except Exception as e:
                        logger.warning("Failed to clean file", file=str(p), error=str(e))

        result.steps_completed.append("cleanup")
        logger.info("Cleanup completed", files_removed=cleaned_files)

        if progress_callback:
            progress_callback("cleanup", "completed")
