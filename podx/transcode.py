"""CLI wrapper for transcode command.

Thin Click wrapper that uses core.transcode.TranscodeEngine for actual logic.
Handles CLI arguments, input/output, and interactive mode.
"""
import json
from pathlib import Path

import click

from .cli_shared import print_json, read_stdin_json
from .core.transcode import TranscodeEngine, TranscodeError
from .logging import get_logger

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    import importlib.util

    TEXTUAL_AVAILABLE = importlib.util.find_spec("textual") is not None
except ImportError:
    TEXTUAL_AVAILABLE = False

# Shared UI components
try:
    from .ui import scan_transcodable_episodes, select_episode_for_processing
except Exception:
    from .ui.transcode_browser import scan_transcodable_episodes

    def select_episode_for_processing(*args, **kwargs):
        raise ImportError("UI module not available")


@click.command()
@click.option(
    "--to",
    "fmt",
    default="wav16",
    type=click.Choice(["wav16", "mp3", "aac"]),
    show_default=True,
)
@click.option("--bitrate", default="128k", show_default=True)
@click.option(
    "--outdir",
    type=click.Path(path_type=Path),
    help="Output directory (defaults to same directory as source audio)",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read EpisodeMeta JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save AudioMeta JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select episodes for transcoding",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for episodes (default: current directory)",
)
def main(fmt, bitrate, outdir, input, output, interactive, scan_dir):
    """
    Read EpisodeMeta JSON on stdin (with audio_path), transcode, print AudioMeta JSON on stdout.

    With --interactive, browse episodes and select one to transcode.
    """
    # Handle interactive mode
    if interactive:
        if not TEXTUAL_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires textual library. Install with: pip install textual"
            )

        # Browse and select episode using Textual TUI
        logger.info(f"Scanning for episodes in: {scan_dir}")
        selected = select_episode_for_processing(
            scan_dir=Path(scan_dir),
            title="Select Episode for Transcoding",
            episode_scanner=scan_transcodable_episodes,
        )

        if not selected:
            logger.info("User cancelled")
            return

        # Use selected episode's metadata
        meta = selected["meta_data"]
        src = selected["audio_path"]
        episode_dir = selected["directory"]

        # Force outdir to episode directory in interactive mode
        outdir = episode_dir

        # Force output to audio-meta.json in interactive mode
        output = episode_dir / "audio-meta.json"

    else:
        # Non-interactive mode: read from input
        if input:
            meta = json.loads(input.read_text())
        else:
            meta = read_stdin_json()

        if not meta or "audio_path" not in meta:
            raise SystemExit(
                "input must contain EpisodeMeta JSON with 'audio_path' field"
            )
        src = Path(meta["audio_path"])

        # If audio_path doesn't exist, try to find it in outdir
        if not src.exists() and outdir:
            # Try to find audio file with same basename in outdir
            audio_extensions = [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"]
            for ext in audio_extensions:
                candidate = outdir / (src.stem + ext)
                if candidate.exists():
                    logger.debug(
                        "Audio path in metadata doesn't exist; found alternative",
                        metadata_path=str(src),
                        actual_path=str(candidate),
                    )
                    src = candidate
                    break

        # Final check: if source still doesn't exist, raise clear error
        if not src.exists():
            raise SystemExit(
                f"Audio file not found: {src}\n"
                f"Metadata may contain outdated path. "
                f"Expected file in: {outdir if outdir else src.parent}"
            )

    # Determine output directory
    if outdir:
        output_dir = outdir
    else:
        output_dir = src.parent

    # Use core transcode engine (pure business logic)
    try:
        engine = TranscodeEngine(format=fmt, bitrate=bitrate)
        result = engine.transcode(src, output_dir)
    except (TranscodeError, FileNotFoundError) as e:
        raise SystemExit(str(e))

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (already set to audio-meta.json)
        output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Audio metadata saved to: {output}")
    else:
        # Non-interactive mode: save to file if requested
        if output:
            output.write_text(json.dumps(result, indent=2))

        # Always print to stdout in non-interactive mode
        print_json(result)


if __name__ == "__main__":
    main()
