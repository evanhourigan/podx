"""Transcribe step executor for ASR transcription."""

import json
import time
from typing import Any, Optional

from podx.cli.services.command_runner import run_command
from podx.services.command_builder import CommandBuilder
from podx.logging import get_logger

from .base import PipelineStep, StepContext, StepResult

logger = get_logger(__name__)


class TranscribeStep(PipelineStep):
    """Execute transcription step.

    Handles transcript discovery and resume support, reusing existing
    transcripts for the same model when available.
    """

    def __init__(self, model: str, compute: str, asr_provider: str):
        """Initialize transcribe step.

        Args:
            model: ASR model name (e.g., "large-v3")
            compute: Compute type (int8, float16, float32)
            asr_provider: ASR provider (auto, local, openai, hf)
        """
        self.model = model
        self.compute = compute
        self.asr_provider = asr_provider

    @property
    def name(self) -> str:
        return "Transcribe Audio"

    def should_skip(self, context: StepContext) -> tuple[bool, Optional[str]]:
        """Check if transcription can be skipped by finding existing transcript."""
        from podx.utils import discover_transcripts, sanitize_model_name

        wd = context.working_dir
        existing_transcripts = discover_transcripts(wd)

        # Check for model-specific transcript
        transcript_file = wd / f"transcript-{sanitize_model_name(self.model)}.json"
        if transcript_file.exists():
            return True, f"Found existing transcript for model {self.model}"

        # Check legacy transcript.json
        legacy_transcript = wd / "transcript.json"
        if legacy_transcript.exists():
            try:
                legacy_data = json.loads(legacy_transcript.read_text())
                legacy_model = legacy_data.get("asr_model", "unknown")
                existing_transcripts[legacy_model] = legacy_transcript
            except Exception:
                existing_transcripts["unknown"] = legacy_transcript

        if existing_transcripts:
            # Found transcripts with other models
            order = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
            available = list(existing_transcripts.keys())
            best = None
            for m in reversed(order):
                if m in available:
                    best = m
                    break
            best_model = best or available[0]
            return True, f"Found existing transcript with model {best_model}"

        return False, None

    def execute(self, context: StepContext, progress: Any, verbose: bool = False) -> StepResult:
        """Execute transcription step."""
        from podx.utils import discover_transcripts, sanitize_model_name

        wd = context.working_dir
        existing_transcripts = discover_transcripts(wd)

        # Check for existing transcript
        transcript_file = wd / f"transcript-{sanitize_model_name(self.model)}.json"

        # Check legacy transcript.json
        legacy_transcript = wd / "transcript.json"
        if legacy_transcript.exists():
            try:
                legacy_data = json.loads(legacy_transcript.read_text())
                legacy_model = legacy_data.get("asr_model", "unknown")
                existing_transcripts[legacy_model] = legacy_transcript
            except Exception:
                existing_transcripts["unknown"] = legacy_transcript

        if transcript_file.exists():
            # Use existing transcript for this specific model
            logger.info(
                f"Found existing transcript for model {self.model}, skipping transcription"
            )
            base = json.loads(transcript_file.read_text())
            progress.complete_step(
                f"Using existing transcript ({self.model}) - {len(base.get('segments', []))} segments",
                0,
            )
            context.latest_transcript = base
            context.latest_transcript_name = f"transcript-{base.get('asr_model', self.model)}"
            return StepResult.skip(f"Using existing transcript ({self.model})")

        elif existing_transcripts:
            # Found transcripts with other models - pick the most sophisticated
            order = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
            available = list(existing_transcripts.keys())
            best = None
            for m in reversed(order):
                if m in available:
                    best = m
                    break
            best_model = best or available[0]

            logger.info(f"Found existing transcript with model {best_model}, using it")
            base = json.loads(existing_transcripts[best_model].read_text())
            progress.complete_step(
                f"Using existing transcript ({best_model}) - {len(base.get('segments', []))} segments",
                0,
            )
            context.latest_transcript = base
            context.latest_transcript_name = f"transcript-{base.get('asr_model', best_model)}"
            return StepResult.skip(f"Using existing transcript ({best_model})")

        else:
            # No existing transcript - perform transcription
            step_start = time.time()
            progress.start_step(f"Transcribing with {self.model} model")

            transcribe_cmd = (
                CommandBuilder("podx-transcribe")
                .add_option("--model", self.model)
                .add_option("--compute", self.compute)
            )
            if self.asr_provider and self.asr_provider != "auto":
                # Convert asr_provider enum to string value if needed
                asr_provider_value = (
                    self.asr_provider.value if hasattr(self.asr_provider, "value") else self.asr_provider
                )
                transcribe_cmd.add_option("--asr-provider", asr_provider_value)

            base = run_command(
                transcribe_cmd.build(),
                stdin_payload=context.audio_metadata,
                verbose=verbose,
                save_to=transcript_file,
                label=None,
            )

            step_duration = time.time() - step_start
            num_segments = len(base.get('segments', []))
            progress.complete_step(
                f"Transcription complete - {num_segments} segments",
                step_duration,
            )

            # Update context
            context.latest_transcript = base
            context.latest_transcript_name = f"transcript-{base.get('asr_model', self.model)}"

            return StepResult.ok(
                f"Transcription complete - {num_segments} segments",
                duration=step_duration,
                data={"transcript": base, "transcript_name": context.latest_transcript_name}
            )
