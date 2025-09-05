import json
import os
import sys
from contextlib import redirect_stderr
from pathlib import Path

import click

from .cli_shared import print_json, read_stdin_json


@click.command()
@click.option(
    "--audio",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read Transcript JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save AlignedTranscript JSON to file (also prints to stdout)",
)
def main(audio, input, output):
    """
    Read coarse Transcript JSON on stdin -> WhisperX align -> print aligned JSON to stdout.
    """
    # Read input
    if input:
        base = json.loads(input.read_text())
    else:
        base = read_stdin_json()

    if not base or "segments" not in base:
        raise SystemExit("input must contain Transcript JSON with 'segments' field")
    lang = base.get("language", "en")
    segs = base["segments"]

    # Suppress WhisperX debug output that contaminates stdout
    import sys
    from contextlib import redirect_stderr, redirect_stdout

    import whisperx

    with redirect_stdout(open(os.devnull, "w")), redirect_stderr(open(os.devnull, "w")):
        model_a, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
        aligned = whisperx.align(segs, model_a, metadata, str(audio), device="cpu")

    aligned["audio_path"] = str(audio)

    # Save to file if requested
    if output:
        output.write_text(json.dumps(aligned, indent=2))

    # Always print to stdout
    print_json(aligned)


if __name__ == "__main__":
    main()
