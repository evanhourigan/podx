import subprocess
from pathlib import Path

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
    "--outdir", default="work", show_default=True, type=click.Path(path_type=Path)
)
def main(fmt, bitrate, outdir):
    """
    Read EpisodeMeta JSON on stdin (with audio_path), transcode, print AudioMeta JSON on stdout.
    """
    meta = read_stdin_json()
    if not meta or "audio_path" not in meta:
        raise SystemExit("stdin must contain JSON with 'audio_path'")
    src = Path(meta["audio_path"])
    outdir.mkdir(parents=True, exist_ok=True)
    dst = outdir / (src.stem + ".wav16" if fmt == "wav16" else src.stem + ".transcoded")

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
        out = {"audio_path": str(dst), "format": "mp3"}
    else:
        dst = dst.with_suffix(".m4a")
        ffmpeg(["-y", "-i", str(src), "-c:a", "aac", "-b:a", bitrate, str(dst)])
        out = {"audio_path": str(dst), "format": "aac"}

    print_json(out)


if __name__ == "__main__":
    main()
