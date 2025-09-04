import json
import os
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
    type=click.Path(exists=True, path_type=Path),
    help="Read AlignedTranscript JSON from file instead of stdin",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Save DiarizedTranscript JSON to file (also prints to stdout)",
)
def main(audio, input, output):
    """
    Read aligned JSON on stdin -> WhisperX diarization -> print diarized JSON to stdout.
    """
    # Read input
    if input:
        aligned = json.loads(input.read_text())
    else:
        aligned = read_stdin_json()

    if not aligned or "segments" not in aligned:
        raise SystemExit("input must contain aligned JSON with 'segments'")

    import whisperx

    dia = whisperx.DiarizationPipeline(
        use_auth_token=os.getenv("HUGGINGFACE_TOKEN"), device="cpu"
    )
    diarized = dia(str(audio))
    final = whisperx.assign_word_speakers(diarized, aligned)
    final["audio_path"] = str(audio)

    # Save to file if requested
    if output:
        output.write_text(json.dumps(final, indent=2))

    # Always print to stdout
    print_json(final)


if __name__ == "__main__":
    main()
