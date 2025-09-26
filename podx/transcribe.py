import json
import os
import sys
from pathlib import Path

import click

from .cli_shared import print_json, read_stdin_json
from .config import get_config
from .errors import AudioError, ValidationError
from .logging import get_logger
from .schemas import AudioMeta, Transcript
from .validation import validate_output

logger = get_logger(__name__)


@click.command()
@click.option(
    "--model",
    default=lambda: get_config().default_asr_model,
    help="ASR model (tiny, base, small, medium, large, large-v2, large-v3)",
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read AudioMeta JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save Transcript JSON to file (also prints to stdout)",
)
@validate_output(Transcript)
def main(model, compute, input, output):
    """
    Read AudioMeta JSON on stdin -> run faster-whisper -> print Transcript JSON to stdout.
    """
    logger.info("Starting transcription", model=model, compute=compute)

    # Read input
    if input:
        raw_data = json.loads(input.read_text())
        logger.debug("Reading input from file", file=str(input))
    else:
        raw_data = read_stdin_json()
        logger.debug("Reading input from stdin")

    if not raw_data or "audio_path" not in raw_data:
        raise ValidationError(
            "input must contain AudioMeta JSON with 'audio_path' field"
        )

    # Validate input data
    try:
        meta = AudioMeta.parse_obj(raw_data)
        audio = Path(meta.audio_path)
        logger.debug("Input validation passed", audio_path=str(audio))
    except Exception as e:
        raise ValidationError(f"Invalid AudioMeta input: {e}") from e

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise AudioError(
            "faster-whisper not installed. Install with: pip install faster-whisper"
        )

    logger.info("Initializing Whisper model", model=model, compute=compute)
    try:
        asr = WhisperModel(model, device="cpu", compute_type=compute)
    except Exception as e:
        raise AudioError(f"Failed to initialize Whisper model: {e}") from e

    logger.info("Starting transcription", audio_file=str(audio))
    try:
        segments, info = asr.transcribe(
            str(audio), vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}
        )
    except Exception as e:
        raise AudioError(f"Transcription failed: {e}") from e

    segs = []
    text_lines = []
    for s in segments:
        segs.append({"start": s.start, "end": s.end, "text": s.text})
        text_lines.append(s.text)

    detected_language = getattr(info, "language", "en")
    total_segments = len(segs)

    logger.info(
        "Transcription completed",
        segments_count=total_segments,
        language=detected_language,
        total_duration=segs[-1]["end"] if segs else 0,
    )

    out = {
        "audio_path": str(audio),
        "language": detected_language,
        "asr_model": model,
        "segments": segs,
        "text": "\n".join(text_lines).strip(),
    }

    # Save to file if requested
    if output:
        output.write_text(json.dumps(out, indent=2))
        logger.debug("Transcript saved to file", file=str(output))

    # Always print to stdout
    print_json(out)

    # Return for validation decorator
    return out


if __name__ == "__main__":
    main()
