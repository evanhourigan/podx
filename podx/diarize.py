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
def main(audio):
    """
    Read aligned JSON on stdin -> WhisperX diarization -> print diarized JSON to stdout.
    """
    aligned = read_stdin_json()
    if not aligned or "segments" not in aligned:
        raise SystemExit("stdin must contain aligned JSON with 'segments'")

    import whisperx

    dia = whisperx.DiarizationPipeline(
        use_auth_token=os.getenv("HUGGINGFACE_TOKEN"), device="cpu"
    )
    diarized = dia(str(audio))
    final = whisperx.assign_word_speakers(diarized, aligned)
    final["audio_path"] = str(audio)

    print_json(final)


if __name__ == "__main__":
    main()
