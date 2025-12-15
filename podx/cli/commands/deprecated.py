"""Deprecated workflow commands for backwards compatibility."""

from typing import Any, Callable

import click

from podx.config import get_config


def register_deprecated_commands(main_group: click.Group, run_command: Callable[..., Any]) -> None:
    """Register deprecated workflow commands.

    Args:
        main_group: The main Click group to register commands to
        run_command: The run command function to invoke
    """

    @main_group.command("quick", hidden=True)
    @click.option("--show", help="Podcast show name (iTunes search)")
    @click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
    @click.option("--youtube-url", help="YouTube video URL (alternative to --show and --rss-url)")
    @click.option("--date", help="Episode date (YYYY-MM-DD)")
    @click.option("--title-contains", help="Substring to match in episode title")
    @click.option("--model", default=lambda: get_config().default_asr_model, help="ASR model")
    @click.option(
        "--asr-provider",
        type=click.Choice(["auto", "local", "openai", "hf"]),
        default="auto",
        help="ASR provider for transcribe",
    )
    @click.option(
        "--compute",
        default=lambda: get_config().default_compute,
        type=click.Choice(["auto", "int8", "int8_float16", "float16", "float32"]),
        help="Compute type",
    )
    @click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
    def quick(
        show: str,
        rss_url: str,
        youtube_url: str,
        date: str,
        title_contains: str,
        model: str,
        asr_provider: str,
        compute: str,
        verbose: bool,
    ) -> None:
        """Quick workflow: fetch + transcribe only (fastest option)."""
        click.secho("[deprecated] Use: podx run (with no extra flags)", fg="yellow")
        click.echo("🚀 Running quick transcription workflow...")

        # Use the existing run command but with minimal options (all flags defaulted to False)
        ctx = click.get_current_context()
        ctx.invoke(
            run_command,
            show=show,
            rss_url=rss_url,
            youtube_url=youtube_url,
            date=date,
            title_contains=title_contains,
            model=model,
            compute=compute,
            asr_provider=asr_provider,
            align=False,
            diarize=False,
            deepcast=False,
            extract_markdown=False,
            notion=False,
            verbose=verbose,
            clean=False,
            model_prop="Model",
        )

    @main_group.command("analyze", hidden=True)
    @click.option("--show", help="Podcast show name (iTunes search)")
    @click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
    @click.option("--youtube-url", help="YouTube video URL (alternative to --show and --rss-url)")
    @click.option("--date", help="Episode date (YYYY-MM-DD)")
    @click.option("--title-contains", help="Substring to match in episode title")
    @click.option("--model", default=lambda: get_config().default_asr_model, help="ASR model")
    @click.option(
        "--asr-provider",
        type=click.Choice(["auto", "local", "openai", "hf"]),
        default="auto",
        help="ASR provider for transcribe",
    )
    @click.option(
        "--compute",
        default=lambda: get_config().default_compute,
        type=click.Choice(["auto", "int8", "int8_float16", "float16", "float32"]),
        help="Compute type",
    )
    @click.option(
        "--deepcast-model",
        default=lambda: get_config().openai_model,
        help="AI analysis model",
    )
    @click.option(
        "--type",
        "podcast_type",
        type=click.Choice(
            [
                "interview",
                "tech",
                "business",
                "news",
                "educational",
                "narrative",
                "comedy",
                "general",
            ]
        ),
        help="Podcast type for specialized analysis",
    )
    @click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
    def analyze(
        show: str,
        rss_url: str,
        youtube_url: str,
        date: str,
        title_contains: str,
        model: str,
        asr_provider: str,
        compute: str,
        deepcast_model: str,
        podcast_type: str,
        verbose: bool,
    ) -> None:
        """Analysis workflow: transcribe + AI analysis (recommended)."""
        click.secho(
            "[deprecated] Use: podx run (deepcast + markdown enabled by default in v2.0)",
            fg="yellow",
        )
        click.echo("🤖 Running analysis workflow...")

        ctx = click.get_current_context()
        ctx.invoke(
            run_command,
            show=show,
            rss_url=rss_url,
            youtube_url=youtube_url,
            date=date,
            title_contains=title_contains,
            model=model,
            compute=compute,
            asr_provider=asr_provider,
            align=True,
            deepcast=True,
            extract_markdown=True,
            deepcast_model=deepcast_model,
            verbose=verbose,
            clean=False,
            model_prop="Model",
        )

    @main_group.command("publish", hidden=True)
    @click.option("--show", help="Podcast show name (iTunes search)")
    @click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
    @click.option("--youtube-url", help="YouTube video URL (alternative to --show and --rss-url)")
    @click.option("--date", help="Episode date (YYYY-MM-DD)")
    @click.option("--title-contains", help="Substring to match in episode title")
    @click.option(
        "--db",
        "notion_db",
        default=lambda: get_config().notion_db_id,
        help="Notion database ID",
    )
    @click.option(
        "--deepcast-model",
        default=lambda: get_config().openai_model,
        help="AI analysis model",
    )
    @click.option(
        "--type",
        "podcast_type",
        type=click.Choice(
            [
                "interview",
                "tech",
                "business",
                "news",
                "educational",
                "narrative",
                "comedy",
                "general",
            ]
        ),
        help="Podcast type for specialized analysis",
    )
    @click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
    def publish(
        show: str,
        rss_url: str,
        youtube_url: str,
        date: str,
        title_contains: str,
        notion_db: str,
        deepcast_model: str,
        podcast_type: str,
        verbose: bool,
    ) -> None:
        """Publishing workflow: full pipeline + Notion upload (complete)."""
        click.secho(
            "[deprecated] Use: podx run --notion (deepcast + markdown enabled by default in v2.0)",
            fg="yellow",
        )
        click.echo("📝 Running publishing workflow...")

        ctx = click.get_current_context()
        # Equivalent to selecting the publish workflow
        ctx.invoke(
            run_command,
            show=show,
            rss_url=rss_url,
            youtube_url=youtube_url,
            date=date,
            title_contains=title_contains,
            notion_db=notion_db,
            deepcast_model=deepcast_model,
            align=True,
            deepcast=True,
            extract_markdown=True,
            notion=True,
            verbose=verbose,
            clean=False,
            model_prop="Model",
        )
