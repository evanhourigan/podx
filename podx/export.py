import json
import sys
from pathlib import Path

import click


def ts(sec: float) -> str:
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_if_changed(path: Path, content: str, replace: bool = False) -> None:
    """Write content to file only if it has changed (when replace=True)."""
    if replace and path.exists():
        existing_content = path.read_text(encoding="utf-8")
        if existing_content == content:
            return  # Content unchanged, skip write

    path.write_text(content, encoding="utf-8")


@click.command()
@click.option("--srt", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--vtt", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--txt", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--md", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--replace", is_flag=True, help="Only overwrite files if content has changed"
)
@click.option(
    "--input",
    type=click.Path(exists=True, path_type=Path),
    help="Read Transcript JSON from file instead of stdin",
)
def main(srt, vtt, txt, md, replace, input):
    """
    Read (aligned or diarized) Transcript JSON on stdin and write files.
    """
    # Read input
    if input:
        data = json.loads(input.read_text())
    else:
        data = json.loads(sys.stdin.read())

    # Validate input format
    if not data or "segments" not in data:
        raise SystemExit("input must contain Transcript JSON with 'segments' field")

    segs = data.get("segments") or []
    # TXT
    if txt:
        content = "\n".join(s["text"].strip() for s in segs) + "\n"
        write_if_changed(txt, content, replace)
    # SRT
    if srt:
        lines = []
        for i, s in enumerate(segs, 1):
            speaker = s.get("speaker")
            line = (
                s["text"].strip() if not speaker else f"[{speaker}] {s['text'].strip()}"
            )
            lines += [str(i), f"{ts(s['start'])} --> {ts(s['end'])}", line, ""]
        content = "\n".join(lines)
        write_if_changed(srt, content, replace)
    # VTT
    if vtt:
        lines = ["WEBVTT", ""]
        for s in segs:
            speaker = s.get("speaker")
            line = (
                s["text"].strip() if not speaker else f"[{speaker}] {s['text'].strip()}"
            )
            lines += [
                f"{ts(s['start']).replace(',', '.')} --> {ts(s['end']).replace(',', '.')}",
                line,
                "",
            ]
        content = "\n".join(lines)
        write_if_changed(vtt, content, replace)
    # MD
    if md:
        content = (
            "# Transcript\n\n" + "\n\n".join(s["text"].strip() for s in segs) + "\n"
        )
        write_if_changed(md, content, replace)


if __name__ == "__main__":
    main()
