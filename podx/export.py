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


@click.command()
@click.option("--srt", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--vtt", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--txt", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--md", type=click.Path(dir_okay=False, path_type=Path))
def main(srt, vtt, txt, md):
    """
    Read (aligned or diarized) Transcript JSON on stdin and write files.
    """
    data = json.loads(sys.stdin.read())
    segs = data.get("segments") or []
    # TXT
    if txt:
        txt.write_text(
            "\n".join(s["text"].strip() for s in segs) + "\n", encoding="utf-8"
        )
    # SRT
    if srt:
        lines = []
        for i, s in enumerate(segs, 1):
            speaker = s.get("speaker")
            line = (
                s["text"].strip() if not speaker else f"[{speaker}] {s['text'].strip()}"
            )
            lines += [str(i), f"{ts(s['start'])} --> {ts(s['end'])}", line, ""]
        srt.write_text("\n".join(lines), encoding="utf-8")
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
        vtt.write_text("\n".join(lines), encoding="utf-8")
    # MD
    if md:
        md.write_text(
            "# Transcript\n\n" + "\n\n".join(s["text"].strip() for s in segs) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
