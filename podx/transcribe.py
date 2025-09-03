import os
from pathlib import Path

import click

from .cli_shared import print_json, read_stdin_json


@click.command()
@click.option(
    "--model",
    default=lambda: os.getenv("PODX_DEFAULT_MODEL", "small.en"),
    show_default=True,
)
@click.option(
    "--compute",
    default=lambda: os.getenv("PODX_DEFAULT_COMPUTE", "int8"),
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    show_default=True,
)
def main(model, compute):
    """
    Read AudioMeta JSON on stdin -> run faster-whisper -> print Transcript JSON to stdout.
    """
    meta = read_stdin_json()
    if not meta or "audio_path" not in meta:
        raise SystemExit("stdin must contain JSON with 'audio_path'")
    audio = Path(meta["audio_path"])

    from faster_whisper import WhisperModel

    # ensure 16k mono upstream; if not, faster-whisper will still handle it
    asr = WhisperModel(model, device="cpu", compute_type=compute)
    segments, info = asr.transcribe(
        str(audio), vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}
    )

    segs = []
    text_lines = []
    for s in segments:
        segs.append({"start": s.start, "end": s.end, "text": s.text})
        text_lines.append(s.text)

    out = {
        "audio_path": str(audio),
        "language": getattr(info, "language", "en"),
        "segments": segs,
        "text": "\n".join(text_lines).strip(),
    }
    print_json(out)


if __name__ == "__main__":
    main()
