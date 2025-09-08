import json
import subprocess
from pathlib import Path
from typing import Any, Dict

import click

from .cli_shared import print_json, read_stdin_json
from .schemas import AudioMeta


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
def main(fmt, bitrate, outdir, input, output):
    """
    Read EpisodeMeta JSON on stdin (with audio_path), transcode, print AudioMeta JSON on stdout.
    """
    # Read input
    if input:
        meta = json.loads(input.read_text())
    else:
        meta = read_stdin_json()

    if not meta or "audio_path" not in meta:
        raise SystemExit("input must contain EpisodeMeta JSON with 'audio_path' field")
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
            "audio_path": str(wav),
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
        out = {"audio_path": str(dst), "format": "mp3", **probed}
    else:
        dst = dst.with_suffix(".m4a")
        ffmpeg(["-y", "-i", str(src), "-c:a", "aac", "-b:a", bitrate, str(dst)])
        probed = ffprobe_audio_meta(dst)
        out = {"audio_path": str(dst), "format": "aac", **probed}

    # Save to file if requested
    if output:
        output.write_text(json.dumps(out, indent=2))

    # Always print to stdout
    print_json(out)


if __name__ == "__main__":
    main()
