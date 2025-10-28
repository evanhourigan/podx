#!/usr/bin/env python3
"""CLI wrapper for YouTube operations.

Thin wrapper that uses core.youtube.YouTubeEngine for actual logic.
Handles Rich progress display and CLI error formatting.
"""

import json
from pathlib import Path
from typing import Any, Dict

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from podx.core.youtube import (
    YouTubeEngine,
    YouTubeError,
    is_youtube_url,
)
from podx.errors import NetworkError, ValidationError
from podx.logging import get_logger

logger = get_logger()
console = Console()


def download_youtube_audio(
    url: str, output_dir: Path, filename: str | None = None
) -> Dict[str, Any]:
    """Download audio from YouTube video with Rich progress display.

    Args:
        url: YouTube video URL
        output_dir: Directory to save audio
        filename: Optional custom filename

    Returns:
        Dict containing episode metadata

    Raises:
        NetworkError: If download fails
    """
    try:
        # Set up Rich progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Downloading YouTube audio...", total=None)

            def progress_callback(message: str):
                progress.update(task, description=message)

            # Use core engine with progress callback
            engine = YouTubeEngine(progress_callback=progress_callback)
            result = engine.download_audio(url, output_dir, filename)

        return result

    except YouTubeError as e:
        raise NetworkError(str(e)) from e


def fetch_youtube_episode(url: str, workdir: Path) -> Dict[str, Any]:
    """Fetch a YouTube video as an episode with Rich progress display.

    Args:
        url: YouTube video URL
        workdir: Working directory for output

    Returns:
        Dict containing episode metadata

    Raises:
        ValidationError: If URL is invalid
        NetworkError: If fetch fails
    """
    if not is_youtube_url(url):
        raise ValidationError(f"Not a valid YouTube URL: {url}")

    logger.info("Processing YouTube URL", url=url)

    try:
        # Download audio with Rich progress
        episode_meta = download_youtube_audio(url, workdir)

        # Save episode metadata
        meta_file = workdir / "episode-meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(episode_meta, f, indent=2, ensure_ascii=False)

        logger.info("YouTube episode metadata saved", meta_file=str(meta_file))

        return episode_meta

    except YouTubeError as e:
        raise NetworkError(str(e)) from e


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python youtube.py <youtube_url>")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = Path("./youtube_test")

    try:
        result = fetch_youtube_episode(url, output_dir)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
