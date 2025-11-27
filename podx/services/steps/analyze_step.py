"""Analyze step executor for AI-powered transcript analysis."""

import time
from typing import Any, Optional

from podx.cli.services.command_runner import run_command
from podx.logging import get_logger

from .base import PipelineStep, StepContext, StepResult

logger = get_logger(__name__)


class AnalyzeStep(PipelineStep):
    """Execute analyze step.

    Handles AI-powered transcript analysis with configurable analysis types
    and output formats (JSON, markdown, PDF).
    """

    def __init__(
        self,
        analyze_model: str,
        analyze_temp: float,
        yaml_analysis_type: Optional[str],
        extract_markdown: bool,
        analyze_pdf: bool,
    ):
        """Initialize analyze step.

        Args:
            analyze_model: AI model for analysis
            analyze_temp: Temperature for LLM calls
            yaml_analysis_type: Optional analysis type from YAML config
            extract_markdown: Extract markdown from analysis output
            analyze_pdf: Generate PDF from analysis output
        """
        self.analyze_model = analyze_model
        self.analyze_temp = analyze_temp
        self.yaml_analysis_type = yaml_analysis_type
        self.extract_markdown = extract_markdown
        self.analyze_pdf = analyze_pdf

    @property
    def name(self) -> str:
        return "AI Analysis"

    def should_skip(self, context: StepContext) -> tuple[bool, Optional[str]]:
        """Check if analysis can be skipped."""
        # Use model-specific filenames to allow multiple analyses
        model_suffix = self.analyze_model.replace(".", "_").replace("-", "_")
        json_out = context.working_dir / f"analysis-{model_suffix}.json"

        if json_out.exists():
            return True, f"Found existing analysis for {self.analyze_model}"
        return False, None

    def execute(
        self, context: StepContext, progress: Any, verbose: bool = False
    ) -> StepResult:
        """Execute analyze step."""
        from podx.utils import build_analyze_command

        wd = context.working_dir

        # Use model-specific filenames to allow multiple analyses
        model_suffix = self.analyze_model.replace(".", "_").replace("-", "_")
        json_out = wd / f"analysis-{model_suffix}.json"
        md_out = wd / f"analysis-{model_suffix}.md"

        if json_out.exists():
            logger.info("Found existing analysis, skipping AI analysis")
            progress.complete_step("Using existing AI analysis", 0)
            context.results.update({"analysis_json": str(json_out)})
            if self.extract_markdown and md_out.exists():
                context.results.update({"analysis_md": str(md_out)})
            return StepResult.skip(
                f"Using existing analysis for {self.analyze_model}"
            )

        # Perform analysis
        progress.start_step(f"Analyzing transcript with {self.analyze_model}")
        step_start = time.time()

        latest_path = wd / "latest.json"
        meta_file = wd / "episode-meta.json"

        cmd = build_analyze_command(
            input_path=latest_path,
            output_path=json_out,
            model=self.analyze_model,
            temperature=self.analyze_temp,
            meta_path=meta_file,
            analysis_type=self.yaml_analysis_type,
            extract_markdown=self.extract_markdown,
            generate_pdf=self.analyze_pdf,
        )

        run_command(cmd, verbose=verbose, save_to=None, label=None)

        step_duration = time.time() - step_start
        progress.complete_step("AI analysis completed", step_duration)

        # Update results
        context.results.update({"analysis_json": str(json_out)})
        if self.extract_markdown and md_out.exists():
            context.results.update({"analysis_md": str(md_out)})

        return StepResult.ok(
            "AI analysis completed",
            duration=step_duration,
            data={
                "analysis_json": str(json_out),
                "analysis_md": str(md_out) if md_out.exists() else None,
            },
        )
