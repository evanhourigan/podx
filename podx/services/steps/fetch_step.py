"""Fetch step executor for episode metadata retrieval."""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from podx.cli.services.command_runner import run_command
from podx.constants import TITLE_MAX_LENGTH
from podx.errors import ValidationError
from podx.logging import get_logger
from podx.services.command_builder import CommandBuilder

from .base import PipelineStep, StepContext, StepResult

logger = get_logger(__name__)


class FetchStep(PipelineStep):
    """Execute fetch step to get episode metadata and determine working directory.

    Handles three fetch modes:
    1. Interactive mode: Use pre-loaded metadata and workdir (skip fetch)
    2. YouTube mode: Fetch from YouTube URL
    3. RSS/Podcast mode: Fetch from iTunes search or RSS feed

    After fetching, applies podcast-specific configuration from YAML/JSON config.
    """

    def __init__(
        self,
        interactive_mode_meta: Optional[Dict[str, Any]] = None,
        interactive_mode_wd: Optional[Path] = None,
    ):
        """Initialize fetch step.

        Args:
            interactive_mode_meta: Pre-loaded metadata from interactive selection (or None)
            interactive_mode_wd: Pre-determined workdir from interactive selection (or None)
        """
        self.interactive_mode_meta = interactive_mode_meta
        self.interactive_mode_wd = interactive_mode_wd

    @property
    def name(self) -> str:
        return "Fetch Episode Metadata"

    def execute(
        self, context: StepContext, progress: Any, verbose: bool = False
    ) -> StepResult:
        """Execute fetch step."""
        step_start = time.time()

        try:
            # 1. Interactive mode: metadata and workdir already determined
            if (
                self.interactive_mode_meta is not None
                and self.interactive_mode_wd is not None
            ):
                # Check if audio file exists; if not, need to fetch
                audio_path = self.interactive_mode_meta.get("audio_path")
                if audio_path and Path(audio_path).exists():
                    context.metadata = self.interactive_mode_meta
                    context.working_dir = self.interactive_mode_wd
                    return StepResult.skip(
                        "Using pre-selected episode from interactive mode"
                    )

                # Audio missing - populate config from metadata and fall through to fetch
                if self.interactive_mode_meta.get("show"):
                    context.config["show"] = self.interactive_mode_meta["show"]
                if self.interactive_mode_meta.get("episode_published"):
                    context.config["date"] = self.interactive_mode_meta[
                        "episode_published"
                    ]
                if self.interactive_mode_meta.get("episode_title"):
                    context.config["title_contains"] = self.interactive_mode_meta[
                        "episode_title"
                    ]
                if self.interactive_mode_meta.get("feed"):
                    context.config["rss_url"] = self.interactive_mode_meta["feed"]

                # Use the selected episode's workdir instead of generating a new one
                context.config["workdir"] = self.interactive_mode_wd

            # 2. YouTube URL mode
            if context.config.get("youtube_url"):
                meta = self._fetch_youtube(context, progress, verbose)

            # 3. RSS/Podcast mode
            else:
                meta = self._fetch_podcast(context, progress, verbose)

            # 4. Apply podcast-specific configuration from YAML/JSON
            self._apply_podcast_config(context, meta)

            # 5. Determine working directory
            if context.config.get("workdir"):
                wd = context.config["workdir"]
            else:
                from podx.utils import generate_workdir

                show = meta.get("show", "Unknown Show")
                episode_date = (
                    meta.get("episode_published")
                    or context.config.get("date")
                    or "unknown"
                )
                wd = generate_workdir(show, episode_date)

            # Update context
            context.metadata = meta
            context.working_dir = wd

            duration = time.time() - step_start
            episode_title = meta.get("episode_title", "Unknown")[:TITLE_MAX_LENGTH]
            return StepResult.ok(
                f"Episode fetched: {episode_title}",
                duration=duration,
                data={"metadata": meta, "working_dir": str(wd)},
            )

        except ValidationError as e:
            duration = time.time() - step_start
            return StepResult.fail("Fetch failed", str(e), duration=duration)
        except Exception as e:
            duration = time.time() - step_start
            return StepResult.fail("Fetch failed", str(e), duration=duration)

    def _fetch_youtube(
        self, context: StepContext, progress: Any, verbose: bool
    ) -> Dict[str, Any]:
        """Fetch YouTube video metadata."""
        from podx.cli.youtube import get_youtube_metadata, is_youtube_url

        youtube_url = context.config["youtube_url"]
        if not is_youtube_url(youtube_url):
            raise ValidationError(f"Invalid YouTube URL: {youtube_url}")

        progress.start_step("Fetching YouTube video metadata")

        # Get metadata first to determine workdir
        youtube_metadata = get_youtube_metadata(youtube_url)

        # Create metadata dict
        meta = {
            "show": youtube_metadata["channel"],
            "episode_title": youtube_metadata["title"],
            "episode_published": youtube_metadata.get("upload_date", ""),
        }

        progress.complete_step(
            f"YouTube metadata fetched: {meta.get('episode_title', 'Unknown')[:TITLE_MAX_LENGTH]}"
        )

        return meta

    def _fetch_podcast(
        self, context: StepContext, progress: Any, verbose: bool
    ) -> Dict[str, Any]:
        """Fetch podcast episode metadata from RSS/iTunes."""
        fetch_cmd = CommandBuilder("podx-fetch")
        if context.config.get("show"):
            fetch_cmd.add_option("--show", context.config["show"])
        elif context.config.get("rss_url"):
            fetch_cmd.add_option("--rss-url", context.config["rss_url"])
        else:
            raise ValidationError(
                "Either --show, --rss-url, or --youtube-url must be provided."
            )

        if context.config.get("date"):
            fetch_cmd.add_option("--date", context.config["date"])
        if context.config.get("title_contains"):
            fetch_cmd.add_option("--title-contains", context.config["title_contains"])
        if context.config.get("workdir"):
            fetch_cmd.add_option("--outdir", str(context.config["workdir"]))

        # Run fetch first to get metadata
        progress.start_step("Fetching episode metadata")
        meta = run_command(
            fetch_cmd.build(),
            verbose=verbose,
            save_to=None,  # Don't save yet, we'll save after determining workdir
            label=None,  # Progress handles the display
        )
        progress.complete_step(
            f"Episode fetched: {meta.get('episode_title', 'Unknown')}"
        )

        return meta

    def _apply_podcast_config(self, context: StepContext, meta: Dict[str, Any]) -> None:
        """Apply podcast-specific configuration from YAML/JSON."""
        from podx.utils import apply_podcast_config

        show_name = meta.get("show") or meta.get("show_name", "")

        # Current flags to potentially override
        current_flags = {
            "align": context.config["align"],
            "diarize": context.config["diarize"],
            "deepcast": context.config["deepcast"],
            "extract_markdown": context.config["extract_markdown"],
            "notion": context.config["notion"],
        }

        config_result = apply_podcast_config(
            show_name=show_name,
            current_flags=current_flags,
            deepcast_model=context.config["deepcast_model"],
            deepcast_temp=context.config["deepcast_temp"],
            notion=context.config["notion"],
            logger=logger,
        )

        # Update config with podcast-specific overrides
        context.config["align"] = config_result.flags["align"]
        context.config["diarize"] = config_result.flags["diarize"]
        context.config["deepcast"] = config_result.flags["deepcast"]
        context.config["extract_markdown"] = config_result.flags["extract_markdown"]
        context.config["notion"] = config_result.flags["notion"]
        context.config["deepcast_model"] = config_result.deepcast_model
        context.config["deepcast_temp"] = config_result.deepcast_temp
        context.config["yaml_analysis_type"] = config_result.yaml_analysis_type
