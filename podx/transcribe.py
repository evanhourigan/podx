import json
import os
import sys
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
@click.option(
    "--input",
    type=click.Path(exists=True, path_type=Path),
    help="Read AudioMeta JSON from file instead of stdin",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Save Transcript JSON to file (also prints to stdout)",
)
def main(model, compute, input, output):
    """
    Read AudioMeta JSON on stdin -> run faster-whisper -> print Transcript JSON to stdout.
    """
    # Read input
    if input:
        meta = json.loads(input.read_text())
    else:
        meta = read_stdin_json()

    if not meta or "audio_path" not in meta:
        raise SystemExit("input must contain JSON with 'audio_path'")
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

    # Save to file if requested
    if output:
        output.write_text(json.dumps(out, indent=2))

    # Always print to stdout
    print_json(out)


if __name__ == "__main__":
    main()
