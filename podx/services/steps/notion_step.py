"""Notion step executor for uploading content to Notion."""

import time
from pathlib import Path
from typing import Any

from podx.cli.services.command_runner import run_command
from podx.services.command_builder import CommandBuilder

from .base import PipelineStep, StepContext, StepResult


class NotionStep(PipelineStep):
    """Execute Notion page creation/update with deepcast content.

    Uploads transcript analysis to Notion database, preferring exported markdown
    when available, falling back to model-specific deepcast files.
    """

    def __init__(
        self,
        notion_db: str,
        deepcast_model: str,
        model: str,
        podcast_prop: str,
        date_prop: str,
        episode_prop: str,
        model_prop: str,
        asr_prop: str,
        append_content: bool,
    ):
        """Initialize Notion step.

        Args:
            notion_db: Notion database ID or key from YAML config
            deepcast_model: AI model used for deepcast analysis
            model: ASR model name
            podcast_prop: Notion property name for podcast
            date_prop: Notion property name for date
            episode_prop: Notion property name for episode
            model_prop: Notion property name for model
            asr_prop: Notion property name for ASR provider
            append_content: Append to existing page instead of replacing
        """
        self.notion_db = notion_db
        self.deepcast_model = deepcast_model
        self.model = model
        self.podcast_prop = podcast_prop
        self.date_prop = date_prop
        self.episode_prop = episode_prop
        self.model_prop = model_prop
        self.asr_prop = asr_prop
        self.append_content = append_content

    @property
    def name(self) -> str:
        return "Upload to Notion"

    def execute(self, context: StepContext, progress: Any, verbose: bool = False) -> StepResult:
        """Execute Notion upload step."""
        progress.start_step("Uploading to Notion")
        step_start = time.time()

        wd = context.working_dir
        results = context.results

        # Prefer exported.md if available, else model-specific deepcast outputs
        model_suffix = self.deepcast_model.replace(".", "_").replace("-", "_")
        exported_md = (
            Path(results.get("exported_md", "")) if results.get("exported_md") else None
        )
        model_specific_md = wd / f"deepcast-{model_suffix}.md"
        model_specific_json = wd / f"deepcast-{model_suffix}.json"

        # Build command using CommandBuilder
        cmd = CommandBuilder("podx-notion")

        # If exported exists, use it directly
        if exported_md and exported_md.exists():
            md_path = str(exported_md)
            json_path = str(model_specific_json) if model_specific_json.exists() else None
            cmd.add_option("--markdown", md_path)
            cmd.add_option("--meta", str(wd / "episode-meta.json"))
            if json_path:
                cmd.add_option("--json", json_path)
        else:
            # Find any deepcast files if model-specific ones don't exist
            deepcast_files = list(wd.glob("deepcast-*.md"))
            fallback_md = deepcast_files[0] if deepcast_files else None

            # Prefer unified JSON mode if no separate markdown file exists
            if model_specific_json.exists() and not model_specific_md.exists():
                # Use unified JSON mode (deepcast JSON contains markdown)
                cmd.add_option("--input", str(model_specific_json))
            else:
                # Use separate markdown + JSON mode
                md_path = (
                    str(model_specific_md)
                    if model_specific_md.exists()
                    else str(fallback_md) if fallback_md else str(wd / "latest.txt")
                )
                json_path = (
                    str(model_specific_json) if model_specific_json.exists() else None
                )

                cmd.add_option("--markdown", md_path)
                cmd.add_option("--meta", str(wd / "episode-meta.json"))
                if json_path:
                    cmd.add_option("--json", json_path)

        # Add common options
        cmd.add_option("--db", self.notion_db)
        cmd.add_option("--podcast-prop", self.podcast_prop)
        cmd.add_option("--date-prop", self.date_prop)
        cmd.add_option("--episode-prop", self.episode_prop)
        cmd.add_option("--model-prop", self.model_prop)
        cmd.add_option("--asr-prop", self.asr_prop)
        cmd.add_option("--deepcast-model", self.deepcast_model)
        cmd.add_option("--asr-model", self.model)

        if self.append_content:
            cmd.add_flag("--append-content")

        run_command(
            cmd.build(),
            verbose=verbose,
            save_to=wd / "notion.out.json",
            label=None,
        )

        step_duration = time.time() - step_start
        progress.complete_step("Notion page created/updated", step_duration)

        context.results.update({"notion": str(wd / "notion.out.json")})

        return StepResult.ok(
            "Notion page created/updated",
            duration=step_duration,
            data={"notion": str(wd / "notion.out.json")}
        )
