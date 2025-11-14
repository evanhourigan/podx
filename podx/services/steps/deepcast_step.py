"""Deepcast step executor for AI-powered transcript analysis."""

import time
from typing import Any, Optional

from podx.cli.services.command_runner import run_command
from podx.logging import get_logger

from .base import PipelineStep, StepContext, StepResult

logger = get_logger(__name__)


class DeepcastStep(PipelineStep):
    """Execute deepcast analysis step.

    Handles AI-powered transcript analysis with configurable analysis types
    and output formats (JSON, markdown, PDF).
    """

    def __init__(
        self,
        deepcast_model: str,
        deepcast_temp: float,
        yaml_analysis_type: Optional[str],
        extract_markdown: bool,
        deepcast_pdf: bool,
    ):
        """Initialize deepcast step.

        Args:
            deepcast_model: AI model for deepcast analysis
            deepcast_temp: Temperature for deepcast LLM calls
            yaml_analysis_type: Optional analysis type from YAML config
            extract_markdown: Extract markdown from deepcast output
            deepcast_pdf: Generate PDF from deepcast output
        """
        self.deepcast_model = deepcast_model
        self.deepcast_temp = deepcast_temp
        self.yaml_analysis_type = yaml_analysis_type
        self.extract_markdown = extract_markdown
        self.deepcast_pdf = deepcast_pdf

    @property
    def name(self) -> str:
        return "AI Analysis (Deepcast)"

    def should_skip(self, context: StepContext) -> tuple[bool, Optional[str]]:
        """Check if deepcast can be skipped."""
        # Use model-specific filenames to allow multiple analyses
        model_suffix = self.deepcast_model.replace(".", "_").replace("-", "_")
        json_out = context.working_dir / f"deepcast-{model_suffix}.json"

        if json_out.exists():
            return True, f"Found existing deepcast analysis for {self.deepcast_model}"
        return False, None

    def execute(self, context: StepContext, progress: Any, verbose: bool = False) -> StepResult:
        """Execute deepcast step."""
        from podx.utils import build_deepcast_command

        wd = context.working_dir

        # Use model-specific filenames to allow multiple analyses
        model_suffix = self.deepcast_model.replace(".", "_").replace("-", "_")
        json_out = wd / f"deepcast-{model_suffix}.json"
        md_out = wd / f"deepcast-{model_suffix}.md"

        if json_out.exists():
            logger.info("Found existing deepcast analysis, skipping AI analysis")
            progress.complete_step("Using existing AI analysis", 0)
            context.results.update({"deepcast_json": str(json_out)})
            if self.extract_markdown and md_out.exists():
                context.results.update({"deepcast_md": str(md_out)})
            return StepResult.skip(f"Using existing deepcast analysis for {self.deepcast_model}")

        # Perform deepcast analysis
        progress.start_step(f"Analyzing transcript with {self.deepcast_model}")
        step_start = time.time()

        latest_path = wd / "latest.json"
        meta_file = wd / "episode-meta.json"

        cmd = build_deepcast_command(
            input_path=latest_path,
            output_path=json_out,
            model=self.deepcast_model,
            temperature=self.deepcast_temp,
            meta_path=meta_file,
            analysis_type=self.yaml_analysis_type,
            extract_markdown=self.extract_markdown,
            generate_pdf=self.deepcast_pdf,
        )

        run_command(cmd, verbose=verbose, save_to=None, label=None)

        step_duration = time.time() - step_start
        progress.complete_step("AI analysis completed", step_duration)

        # Update results
        context.results.update({"deepcast_json": str(json_out)})
        if self.extract_markdown and md_out.exists():
            context.results.update({"deepcast_md": str(md_out)})

        return StepResult.ok(
            "AI analysis completed",
            duration=step_duration,
            data={"deepcast_json": str(json_out), "deepcast_md": str(md_out) if md_out.exists() else None}
        )
