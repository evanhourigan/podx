"""CLI wrapper for fetch command.

Thin Click wrapper that uses core.fetch.PodcastFetcher for actual logic.
Handles CLI arguments, input/output, and interactive mode.
"""
import json
import shutil
import sys
from pathlib import Path

import click

from podx.cli.cli_shared import print_json
from podx.core.fetch import FetchError, PodcastFetcher
from podx.errors import NetworkError, ValidationError
from podx.logging import get_logger
from podx.schemas import EpisodeMeta
from podx.validation import validate_output

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    import importlib.util

    TEXTUAL_AVAILABLE = importlib.util.find_spec("textual") is not None
except ImportError:
    TEXTUAL_AVAILABLE = False


def _truncate_text(text: str, max_length: int = 80) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


@click.command()
@click.option("--show", help="Podcast show name (iTunes search).")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show).")
@click.option("--date", help="Episode date (YYYY-MM-DD). Picks nearest.")
@click.option("--title-contains", help="Substring to match in episode title.")
@click.option(
    "--outdir",
    type=click.Path(path_type=Path),
    help="Override output directory (bypasses smart naming)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save EpisodeMeta JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive episode browser (ignores --date and --title-contains)",
)
@validate_output(EpisodeMeta)
def main(show, rss_url, date, title_contains, outdir, output, interactive):
    """Find feed, choose episode, download audio. Prints EpisodeMeta JSON to stdout."""
    logger.info(
        "Starting podcast fetch",
        show=show,
        rss_url=rss_url,
        date=date,
        title_contains=title_contains,
        interactive=interactive,
    )

    # Handle interactive mode
    if interactive:
        # Check if textual is available
        if not TEXTUAL_AVAILABLE:
            raise ValidationError(
                "Interactive mode requires textual. " "Run: pip install textual"
            )

        # Import the standalone fetch browser
        from podx.ui.episode_browser_tui import run_fetch_browser_standalone

        # Run the browser and get selected episode
        result = run_fetch_browser_standalone(
            show_name=show,
            rss_url=rss_url,
            output_dir=outdir or Path.cwd(),
        )

        if not result:
            logger.info("User cancelled episode selection")
            sys.exit(0)

        # Episode was fetched, extract metadata
        meta = result.get("meta")
        meta_file = result.get("meta_path")

        # In interactive mode, save metadata if not already saved
        if output and meta and meta_file:
            # Copy to requested output location
            shutil.copy(meta_file, output)
            logger.info("Episode metadata copied", destination=str(output))

        # Return the metadata
        return meta

    # Validate that either show or rss_url is provided (non-interactive mode)
    if not show and not rss_url:
        raise click.UsageError("Either --show or --rss-url must be provided.")
    if show and rss_url:
        raise click.UsageError("Provide either --show or --rss-url, not both.")

    # Use core podcast fetcher (pure business logic)
    try:
        fetcher = PodcastFetcher()
        result = fetcher.fetch_episode(
            show_name=show,
            rss_url=rss_url,
            date=date,
            title_contains=title_contains,
            output_dir=outdir,
        )
    except (ValidationError, NetworkError, FetchError) as e:
        raise SystemExit(str(e))

    # Extract metadata from result
    meta = result["meta"]

    # Handle output
    if output:
        # Save to specified output file
        output.write_text(json.dumps(meta, indent=2))
        logger.info("Episode metadata saved", file=str(output))

    # Always print to stdout in non-interactive mode
    print_json(meta)

    # Return for validation decorator
    return meta


if __name__ == "__main__":
    main()
