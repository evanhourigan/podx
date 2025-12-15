"""Enhancement step executor for transcript preprocessing and diarization."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from podx.cli.services.command_runner import run_command
from podx.logging import get_logger
from podx.services.command_builder import CommandBuilder

from .base import PipelineStep, StepContext, StepResult

logger = get_logger(__name__)


class EnhancementStep(PipelineStep):
    """Execute transcript enhancement pipeline (preprocess, diarize).

    Processes transcripts through optional enhancement steps, updating the
    latest transcript and its name as each step completes.
    """

    def __init__(
        self,
        preprocess: bool,
        restore: bool,
        diarize: bool,
        model: str,
    ):
        """Initialize enhancement step.

        Args:
            preprocess: Enable transcript preprocessing
            restore: Enable semantic restore in preprocessing
            diarize: Enable speaker diarization
            model: ASR model name (for file naming)
        """
        self.preprocess = preprocess
        self.restore = restore
        self.diarize = diarize
        self.model = model

    @property
    def name(self) -> str:
        parts = []
        if self.preprocess:
            parts.append("Preprocess")
        if self.diarize:
            parts.append("Diarize")
        return " & ".join(parts) if parts else "Enhancement"

    def should_skip(self, context: StepContext) -> Tuple[bool, Optional[str]]:
        """Check if enhancement can be skipped."""
        if not self.preprocess and not self.diarize:
            return True, "No enhancement steps enabled"
        return False, None

    def execute(self, context: StepContext, progress: Any, verbose: bool = False) -> StepResult:
        """Execute enhancement step."""
        if not self.preprocess and not self.diarize:
            return StepResult.skip("No enhancement steps enabled")

        total_start = time.time()
        latest = context.latest_transcript
        latest_name = context.latest_transcript_name
        wd = context.working_dir

        # PREPROCESS (optional)
        if self.preprocess:
            latest, latest_name = self._execute_preprocess(
                latest or {}, latest_name or "", wd, progress, verbose
            )

        # DIARIZE (optional)
        if self.diarize:
            latest, latest_name = self._execute_diarize(
                latest or {}, latest_name or "", wd, progress, verbose
            )

        # Update context
        context.latest_transcript = latest
        context.latest_transcript_name = latest_name

        total_duration = time.time() - total_start
        return StepResult.ok(
            f"Enhancement complete: {latest_name}",
            duration=total_duration,
            data={"transcript": latest, "transcript_name": latest_name},
        )

    def _execute_preprocess(
        self,
        latest: Dict[str, Any],
        latest_name: str,
        wd: Path,
        progress: Any,
        verbose: bool,
    ) -> Tuple[Dict[str, Any], str]:
        """Execute preprocessing step."""
        from podx.utils import build_preprocess_command, sanitize_model_name

        progress.start_step("Preprocessing transcript (merge/normalize)")
        step_start = time.time()

        # Preprocess the latest transcript
        used_model = (
            (latest or {}).get("asr_model", self.model) if isinstance(latest, dict) else self.model
        )
        pre_file = wd / f"transcript-preprocessed-{sanitize_model_name(used_model)}.json"
        latest = run_command(
            build_preprocess_command(pre_file, self.restore),
            stdin_payload=latest,
            verbose=verbose,
            save_to=pre_file,
            label=None,
        )
        latest_name = f"transcript-preprocessed-{used_model}"

        step_duration = time.time() - step_start
        progress.complete_step("Preprocessing completed", step_duration)

        return latest, latest_name

    def _execute_diarize(
        self,
        latest: Dict[str, Any],
        latest_name: str,
        wd: Path,
        progress: Any,
        verbose: bool,
    ) -> Tuple[Dict[str, Any], str]:
        """Execute diarization step."""
        from podx.utils import sanitize_model_name

        # Get model from latest transcript
        used_model = latest.get("asr_model", self.model)
        diarized_file = wd / f"transcript-diarized-{sanitize_model_name(used_model)}.json"

        # Check if already exists (also check legacy filenames)
        legacy_diarized_new = wd / f"diarized-transcript-{used_model}.json"
        legacy_diarized = wd / "diarized-transcript.json"

        if diarized_file.exists():
            logger.info(f"Found existing diarized transcript ({used_model}), skipping diarization")
            diar = json.loads(diarized_file.read_text())
            progress.complete_step(f"Using existing diarized transcript ({used_model})", 0)
            return diar, f"transcript-diarized-{used_model}"

        elif legacy_diarized_new.exists():
            logger.info(f"Found existing legacy diarized transcript ({used_model}), using it")
            diar = json.loads(legacy_diarized_new.read_text())
            progress.complete_step("Using existing diarized transcript", 0)
            return diar, f"transcript-diarized-{used_model}"

        elif legacy_diarized.exists():
            logger.info("Found existing legacy diarized transcript, using it")
            diar = json.loads(legacy_diarized.read_text())
            progress.complete_step("Using existing diarized transcript", 0)
            return diar, "transcript-diarized"

        else:
            # No existing diarization - perform it
            progress.start_step("Identifying speakers")
            step_start = time.time()

            if verbose:
                import click

                click.secho(
                    f"Debug: Passing {latest_name} JSON to diarize with {len(latest.get('segments', []))} segments",
                    fg="yellow",
                )

            diarize_cmd = CommandBuilder("podx-diarize")
            diar = run_command(
                diarize_cmd.build(),
                stdin_payload=latest,
                verbose=verbose,
                save_to=diarized_file,
                label=None,
            )

            step_duration = time.time() - step_start
            progress.complete_step("Speaker diarization completed", step_duration)
            return diar, f"transcript-diarized-{used_model}"
