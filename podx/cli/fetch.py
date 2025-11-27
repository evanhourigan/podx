"""CLI wrapper for fetch command.

Thin Click wrapper that uses core.fetch.PodcastFetcher for actual logic.
Handles CLI arguments, input/output, and interactive mode.
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from podx.cli.cli_shared import print_json
from podx.core.fetch import FetchError, PodcastFetcher
from podx.domain.exit_codes import ExitCode
from podx.errors import NetworkError, ValidationError
from podx.logging import get_logger
from podx.schemas import EpisodeMeta
from podx.validation import validate_output

logger = get_logger(__name__)
console = Console()

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
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output structured JSON (suppresses Rich formatting)",
)
@validate_output(EpisodeMeta)
def main(show, rss_url, date, title_contains, outdir, output, interactive, json_output):
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
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": "Interactive mode requires textual",
                            "install": "pip install textual",
                        }
                    )
                )
            else:
                console.print(
                    "[red]Error:[/red] Interactive mode requires textual. "
                    "Run: [cyan]pip install textual[/cyan]"
                )
            sys.exit(ExitCode.USER_ERROR)

        # Interactive TUI browser removed in v4.0.0
        console.print(
            "[red]Error:[/red] Interactive fetch browser removed in v4.0.0. "
            "Use --show and --rss options instead."
        )
        sys.exit(ExitCode.USER_ERROR)

    # Validate that either show or rss_url is provided (non-interactive mode)
    if not show and not rss_url:
        if json_output:
            print(json.dumps({"error": "Either --show or --rss-url must be provided"}))
        else:
            console.print(
                "[red]Error:[/red] Either --show or --rss-url must be provided."
            )
        sys.exit(ExitCode.USER_ERROR)
    if show and rss_url:
        if json_output:
            print(json.dumps({"error": "Provide either --show or --rss-url, not both"}))
        else:
            console.print(
                "[red]Error:[/red] Provide either --show or --rss-url, not both."
            )
        sys.exit(ExitCode.USER_ERROR)

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
    except ValidationError as e:
        if json_output:
            print(json.dumps({"error": str(e), "type": "validation_error"}))
        else:
            console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(ExitCode.USER_ERROR)
    except NetworkError as e:
        if json_output:
            print(json.dumps({"error": str(e), "type": "network_error"}))
        else:
            console.print(f"[red]Network Error:[/red] {e}")
        sys.exit(ExitCode.SYSTEM_ERROR)
    except FetchError as e:
        if json_output:
            print(json.dumps({"error": str(e), "type": "fetch_error"}))
        else:
            console.print(f"[red]Fetch Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)

    # Extract metadata from result
    meta = result["meta"]
    audio_path = result.get("audio_path")
    meta_path = result.get("meta_path")

    # Handle output
    if output:
        # Save to specified output file
        output.write_text(json.dumps(meta, indent=2))
        logger.info("Episode metadata saved", file=str(output))

    # Output to stdout
    if json_output:
        # Structured JSON output
        output_data = {
            "success": True,
            "episode": meta,
            "files": {
                "audio": str(audio_path) if audio_path else None,
                "metadata": str(meta_path) if meta_path else None,
            },
        }
        print(json.dumps(output_data, indent=2))
    else:
        # Rich formatted output (existing behavior)
        print_json(meta)

    # Return for validation decorator
    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
