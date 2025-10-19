import json
import subprocess
from pathlib import Path
from typing import Any, Dict

import click

from .cli_shared import print_json, read_stdin_json
from .logging import get_logger
from .schemas import AudioMeta

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    import rich  # noqa: F401

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Shared UI components
try:
    from .ui import TranscodeBrowser, scan_transcodable_episodes as scan_episodes
except Exception:
    TranscodeBrowser = None
    scan_episodes = None


def ffmpeg(args):
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error"] + args,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip())


def to_wav16(src: Path, dst: Path) -> Path:
    dst = dst.with_suffix(".wav")
    ffmpeg(["-y", "-i", str(src), "-ac", "1", "-ar", "16000", "-vn", str(dst)])
    return dst


def ffprobe_audio_meta(path: Path) -> Dict[str, Any]:
    """Probe audio stream for sample rate and channels using ffprobe (best effort)."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=sample_rate,channels",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return {}
        vals = [v for v in proc.stdout.strip().splitlines() if v]
        if len(vals) >= 2:
            return {"sample_rate": int(vals[0]), "channels": int(vals[1])}
    except Exception:
        pass
    return {}


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
        if not RICH_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires rich library. Install with: pip install rich"
            )

        # Scan for episodes
        logger.info(f"Scanning for episodes in: {scan_dir}")
        episodes = scan_episodes(Path(scan_dir))

        if not episodes:
            logger.error(f"No episodes found in {scan_dir}")
            raise SystemExit("No episodes with episode-meta.json found")

        logger.info(f"Found {len(episodes)} episodes")

        # Browse and select
        browser = TranscodeBrowser(episodes, episodes_per_page=10)
        selected = browser.browse()

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

    # Determine output directory
    if outdir:
        # Use specified outdir
        output_dir = outdir
    else:
        # Default: use same directory as source audio
        output_dir = src.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    dst = output_dir / src.stem

    if fmt == "wav16":
        wav = to_wav16(src, dst)
        out: AudioMeta = {
            "audio_path": str(wav.resolve()),  # Always use absolute path
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav16",
        }
    elif fmt == "mp3":
        dst = dst.with_suffix(".mp3")
        ffmpeg(
            ["-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", bitrate, str(dst)]
        )
        probed = ffprobe_audio_meta(dst)
        out = {
            "audio_path": str(dst.resolve()),
            "format": "mp3",
            **probed,
        }  # Absolute path
    else:
        dst = dst.with_suffix(".m4a")
        ffmpeg(["-y", "-i", str(src), "-c:a", "aac", "-b:a", bitrate, str(dst)])
        probed = ffprobe_audio_meta(dst)
        out = {
            "audio_path": str(dst.resolve()),
            "format": "aac",
            **probed,
        }  # Absolute path

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (already set to audio-meta.json)
        output.write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Audio metadata saved to: {output}")
    else:
        # Non-interactive mode: save to file if requested
        if output:
            output.write_text(json.dumps(out, indent=2))

        # Always print to stdout in non-interactive mode
        print_json(out)


if __name__ == "__main__":
    main()
