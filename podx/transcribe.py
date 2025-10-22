import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click

from .cli_shared import print_json, read_stdin_json
from .config import get_config
from .errors import AudioError, ValidationError
from .logging import get_logger
from .schemas import AudioMeta, Transcript
from .utils import sanitize_model_name
from .validation import validate_output

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    import importlib.util

    TEXTUAL_AVAILABLE = importlib.util.find_spec("textual") is not None
except ImportError:
    TEXTUAL_AVAILABLE = False

# Rich console for live timer in interactive mode
try:
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Shared UI components
try:
    from .ui import (
        LiveTimer,
        scan_transcribable_episodes,
        select_asr_model,
        select_episode_for_processing,
    )
except Exception:
    from .ui.asr_selector import select_asr_model
    from .ui.live_timer import LiveTimer
    from .ui.transcribe_browser import scan_transcribable_episodes

    def select_episode_for_processing(*args, **kwargs):
        raise ImportError("UI module not available")

# Model alias maps per provider. Keep minimal and conservative; expand over time.
OPENAI_MODEL_ALIASES: Dict[str, str] = {
    # Friendly -> API model id
    "large-v3": "whisper-large-v3",
    "large-v3-turbo": "whisper-large-v3-turbo",
}

HF_MODEL_ALIASES: Dict[str, str] = {
    # Friendly -> HF repo id
    "distil-large-v3": "distil-whisper/distil-large-v3",
    # Allow mapping to official whisper repos as well
    "large-v3": "openai/whisper-large-v3",
}

LOCAL_MODEL_ALIASES: Dict[str, str] = {
    # Accept common variations and normalize to faster-whisper names
    "small.en": "small.en",
    "medium.en": "medium.en",
    "large": "large",
    "large-v2": "large-v2",
    "large-v3": "large-v3",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
    "medium": "medium",
}


def parse_model_and_provider(
    model_arg: str,
    provider_arg: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Parse model/provider from user input.

    Returns (provider, normalized_model_id).

    Rules:
    - Explicit provider via provider_arg takes precedence.
    - Prefix syntax "openai:large-v3-turbo" or "hf:distil-large-v3" selects provider.
    - Otherwise default to local provider.
    - Alias maps normalize to backend-specific ids.
    """
    if not model_arg:
        return ("local", "small")

    # Detect prefix in model string
    detected_provider = None
    if ":" in model_arg:
        prefix, remainder = model_arg.split(":", 1)
        if prefix in {"local", "openai", "hf"}:
            detected_provider = prefix
            model_key = remainder
        else:
            model_key = model_arg
    else:
        model_key = model_arg

    provider = provider_arg or detected_provider or "local"

    if provider == "openai":
        normalized = OPENAI_MODEL_ALIASES.get(model_key, model_key)
        return ("openai", normalized)
    if provider == "hf":
        normalized = HF_MODEL_ALIASES.get(model_key, model_key)
        return ("hf", normalized)

    # local
    normalized = LOCAL_MODEL_ALIASES.get(model_key, model_key)
    return ("local", normalized)


def _truncate_text(text: str, max_length: int = 60) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


@click.command()
@click.option(
    "--model",
    default=lambda: get_config().default_asr_model,
    help=(
        "ASR model (e.g., tiny, base, small, medium, large, large-v2, large-v3, "
        "small.en, medium.en, or prefixed: openai:large-v3-turbo, hf:distil-large-v3)"
    ),
)
@click.option(
    "--asr-provider",
    type=click.Choice(["auto", "local", "openai", "hf"]),
    default="auto",
    help="ASR provider (auto-detect by model prefix/alias if 'auto')",
)
@click.option(
    "--expert",
    is_flag=True,
    help="Show and enable expert decoder flags (for advanced users)",
)
@click.option(
    "--vad-filter/--no-vad",
    default=None,
    help="Enable/disable VAD filtering (default: enabled)",
)
@click.option(
    "--condition-on-previous-text/--no-condition-on-previous-text",
    default=None,
    help="Condition decoding on previous text (default: enabled; local only)",
)
@click.option(
    "--decode-option",
    multiple=True,
    help="Advanced k=v options to pass to decoder (local provider only)",
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
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select episodes for transcription",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for episodes (default: current directory)",
)
@validate_output(Transcript)
def main(
    model,
    compute,
    input,
    output,
    interactive,
    scan_dir,
    asr_provider,
    expert,
    vad_filter,
    condition_on_previous_text,
    decode_option,
):
    """
    Read AudioMeta JSON on stdin -> run faster-whisper -> print Transcript JSON to stdout.

    With --interactive, browse episodes and select one to transcribe.
    """
    # Handle interactive mode
    if interactive:
        if not TEXTUAL_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires textual library. Install with: pip install textual"
            )

        # Browse and select episode using Textual TUI
        logger.info(f"Scanning for episodes in: {scan_dir}")
        selected = select_episode_for_processing(
            scan_dir=Path(scan_dir),
            title="Select Episode for Transcription",
            episode_scanner=scan_transcribable_episodes,
        )

        if not selected:
            logger.info("User cancelled episode selection")
            sys.exit(0)

        # Select ASR model
        console = Console() if RICH_AVAILABLE else None
        selected_model = select_asr_model(selected, console)

        if not selected_model:
            logger.info("User cancelled model selection")
            sys.exit(0)

        # Override model parameter with user selection
        model = selected_model

        # Use selected episode's audio path
        audio = selected["audio_path"]
        episode_dir = selected["directory"]

        # Force output to transcript-{safe_model}.json in episode directory
        safe_model = sanitize_model_name(model)
        output = episode_dir / f"transcript-{safe_model}.json"

        # Load audio metadata
        try:
            meta = AudioMeta.model_validate(selected["meta_data"])
        except Exception as e:
            raise ValidationError(f"Invalid AudioMeta input: {e}") from e

    else:
        # Non-interactive mode
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
            meta = AudioMeta.model_validate(raw_data)
            audio = Path(meta.audio_path)
            logger.debug("Input validation passed", audio_path=str(audio))
        except Exception as e:
            raise ValidationError(f"Invalid AudioMeta input: {e}") from e

    # Determine provider and normalized model id
    provider_choice = None if asr_provider == "auto" else asr_provider
    provider, normalized_model = parse_model_and_provider(model, provider_choice)

    logger.info("Selected ASR backend", provider=provider, model=normalized_model)

    # Dispatch to provider-specific transcription path
    segments = None
    detected_language = "en"
    full_text_lines: List[str] = []

    if provider == "local":
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise AudioError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )

        logger.info("Initializing local Whisper model", model=normalized_model, compute=compute)
        try:
            asr = WhisperModel(normalized_model, device="cpu", compute_type=compute)
        except Exception as e:
            raise AudioError(f"Failed to initialize Whisper model: {e}") from e

        logger.info("Starting transcription", audio_file=str(audio))

        # Start live timer in interactive mode
        timer = None
        if interactive and RICH_AVAILABLE:
            console = Console()
            timer = LiveTimer("Transcribing")
            timer.start()

        # Determine decode parameters (defaults to VAD=True, condition=True)
        # Can be overridden by explicit --vad-filter and --condition-on-previous-text flags
        use_vad = True if vad_filter is None else bool(vad_filter)
        use_condition = True if condition_on_previous_text is None else bool(condition_on_previous_text)

        # Parse additional decode options
        extra_kwargs: Dict[str, Any] = {}
        for opt in decode_option or ():
            if "=" in opt:
                k, v = opt.split("=", 1)
                extra_kwargs[k.strip()] = v.strip()

        try:
            transcribe_kwargs: Dict[str, Any] = {
                "vad_filter": use_vad,
                "vad_parameters": {"min_silence_duration_ms": 500},
            }
            if use_condition is not None:
                transcribe_kwargs["condition_on_previous_text"] = use_condition
            # Add expert options if provided
            if expert and extra_kwargs:
                transcribe_kwargs.update(extra_kwargs)

            seg_iter, info = asr.transcribe(str(audio), **transcribe_kwargs)
        except Exception as e:
            if timer:
                timer.stop()
            raise AudioError(f"Transcription failed: {e}") from e

        segs = []
        text_lines = []
        for s in seg_iter:
            segs.append({"start": s.start, "end": s.end, "text": s.text})
            text_lines.append(s.text)

        detected_language = getattr(info, "language", "en")
        total_segments = len(segs)

        # Stop timer and show completion message in interactive mode
        if timer:
            elapsed = timer.stop()
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            console.print(f"[green]✓ Transcribe completed in {minutes}:{seconds:02d}[/green]")

        logger.info(
            "Transcription completed",
            segments_count=total_segments,
            language=detected_language,
            total_duration=segs[-1]["end"] if segs else 0,
        )

        segments = segs
        full_text_lines = text_lines

    elif provider == "openai":
        # OpenAI Whisper via API
        logger.info("Using OpenAI transcription API", model=normalized_model)
        try:
            # Prefer new SDK if available
            try:
                from openai import OpenAI  # type: ignore
                client = OpenAI()
                use_new_sdk = True
            except Exception:
                import openai  # type: ignore
                use_new_sdk = False

            audio_path = str(audio)
            if use_new_sdk:
                with open(audio_path, "rb") as f:
                    # Attempt verbose JSON for segments
                    resp = client.audio.transcriptions.create(
                        model=normalized_model,
                        file=f,
                        response_format="verbose_json",
                    )
                # SDK returns pydantic-like objects; try to access fields
                text = getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else None)
                segs_raw = getattr(resp, "segments", None) or (resp.get("segments") if isinstance(resp, dict) else None)
            else:
                # Legacy SDK
                with open(audio_path, "rb") as f:
                    resp = openai.Audio.transcriptions.create(
                        model=normalized_model,
                        file=f,
                        response_format="verbose_json",
                    )
                text = resp.get("text")
                segs_raw = resp.get("segments")

            segs: List[Dict[str, Any]] = []
            if segs_raw:
                for s in segs_raw:
                    start = s.get("start")
                    end = s.get("end")
                    txt = s.get("text", "")
                    if start is None or end is None:
                        # Some APIs use "timestamp" as [start, end]
                        ts = s.get("timestamp")
                        if isinstance(ts, (list, tuple)) and len(ts) == 2:
                            start, end = ts[0], ts[1]
                    if start is None:
                        start = 0.0
                    if end is None:
                        end = 0.0
                    segs.append({"start": float(start), "end": float(end), "text": txt})
            else:
                # Fallback: single segment with full text
                txt = text or ""
                segs = [{"start": 0.0, "end": 0.0, "text": txt}]

            segments = segs
            full_text_lines = [s["text"] for s in segs]
            detected_language = "en"
        except Exception as e:
            raise AudioError(f"OpenAI transcription failed: {e}") from e

    elif provider == "hf":
        # Hugging Face transformers pipeline
        logger.info("Using Hugging Face ASR pipeline", model=normalized_model)
        try:
            from transformers import pipeline  # type: ignore
        except Exception as e:
            raise AudioError(
                "transformers not installed. Install with: pip install transformers torchaudio"
            ) from e

        try:
            asr = pipeline(
                "automatic-speech-recognition",
                model=normalized_model,
                return_timestamps="chunk",
            )
            result = asr(str(audio), chunk_length_s=30, stride_length_s=5)
            segs: List[Dict[str, Any]] = []
            chunks = result.get("chunks") if isinstance(result, dict) else None
            if chunks:
                for c in chunks:
                    ts = c.get("timestamp") or c.get("timestamps")
                    if isinstance(ts, (list, tuple)) and len(ts) == 2:
                        start, end = ts
                    else:
                        start, end = 0.0, 0.0
                    segs.append({"start": float(start), "end": float(end), "text": c.get("text", "")})
                segments = segs
                full_text_lines = [c.get("text", "") for c in chunks]
            else:
                # Fallback: one segment
                text_val = result.get("text") if isinstance(result, dict) else ""
                segments = [{"start": 0.0, "end": 0.0, "text": text_val}]
                full_text_lines = [text_val]
            detected_language = "en"
        except Exception as e:
            raise AudioError(f"Hugging Face transcription failed: {e}") from e
    else:
        raise AudioError(f"Unknown ASR provider: {provider}")

    out = {
        "audio_path": str(audio.resolve()),  # Always use absolute path
        "language": detected_language,
        "asr_model": model,
        "asr_provider": provider,
        "decoder_options": {"vad_filter": use_vad} if provider == "local" else None,
        "segments": segments,
        "text": "\n".join(full_text_lines).strip(),
    }

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (already set to transcript-{model}.json)
        output.write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Transcript saved to: {output}")
    else:
        # Non-interactive mode: use model-specific filename if model specified and no explicit output
        if model and not output:
            # Try to determine episode directory from audio path
            audio_dir = audio.parent
            safe_model = sanitize_model_name(model)
            output = audio_dir / f"transcript-{safe_model}.json"
            output.write_text(
                json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.debug("Transcript saved to file", file=str(output))
        elif output:
            # Explicit output file specified
            output.write_text(json.dumps(out, indent=2))
            logger.debug("Transcript saved to file", file=str(output))

        # Always print to stdout in non-interactive mode
        print_json(out)

    # Return for validation decorator
    return out


if __name__ == "__main__":
    main()
