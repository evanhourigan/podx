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
    Read coarse Transcript JSON on stdin -> WhisperX align -> print aligned JSON to stdout.
    """
    base = read_stdin_json()
    if not base or "segments" not in base:
        raise SystemExit("stdin must contain Transcript JSON with 'segments'")
    lang = base.get("language", "en")
    segs = base["segments"]

    import whisperx

    model_a, metadata = whisperx.load_align_model(language_code=lang, device="cpu")
    aligned = whisperx.align(segs, model_a, metadata, str(audio), device="cpu")
    aligned["audio_path"] = str(audio)

    print_json(aligned)


if __name__ == "__main__":
    main()
