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
    required=False,
    help="Audio file path (optional if specified in aligned transcript JSON)",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read AlignedTranscript JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
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
        raise SystemExit(
            "input must contain AlignedTranscript JSON with 'segments' field"
        )

    # Preserve metadata from input aligned transcript
    asr_model = aligned.get("asr_model")
    language = aligned.get("language", "en")

    # Get audio path from --audio flag or from JSON
    if not audio:
        if "audio_path" not in aligned:
            raise SystemExit(
                "--audio flag required when aligned transcript JSON has no 'audio_path' field"
            )
        audio = Path(aligned["audio_path"])
        if not audio.exists():
            raise SystemExit(f"Audio file not found: {audio}")

    # Ensure we use absolute path
    audio = audio.resolve()

    # Suppress WhisperX debug output that contaminates stdout
    import sys
    from contextlib import redirect_stderr, redirect_stdout

    from whisperx import diarize

    with redirect_stdout(open(os.devnull, "w")), redirect_stderr(open(os.devnull, "w")):
        dia = diarize.DiarizationPipeline(
            use_auth_token=os.getenv("HUGGINGFACE_TOKEN"), device="cpu"
        )
        diarized = dia(str(audio))
        final = diarize.assign_word_speakers(diarized, aligned)

    # Preserve metadata from input transcript (always use absolute path)
    final["audio_path"] = str(audio)  # Already resolved to absolute path above
    final["language"] = language
    if asr_model:
        final["asr_model"] = asr_model

    # Handle output with model-specific filename if available
    if asr_model and not output:
        # Use model-specific filename in same directory as audio
        audio_dir = Path(audio).parent
        output = audio_dir / f"diarized-transcript-{asr_model}.json"
        output.write_text(
            json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    elif output:
        # Explicit output file specified
        output.write_text(json.dumps(final, indent=2))

    # Always print to stdout
    print_json(final)


if __name__ == "__main__":
    main()
