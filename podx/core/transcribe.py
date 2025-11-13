"""Core transcription engine - pure business logic.

No UI dependencies, no CLI concerns. Just audio transcription across multiple backends.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..device import (
    detect_device_for_ctranslate2,
    get_optimal_compute_type,
    log_device_usage,
)
from ..logging import get_logger

logger = get_logger(__name__)

# Model alias maps per provider
OPENAI_MODEL_ALIASES: Dict[str, str] = {
    "large-v3": "whisper-1",
    "large-v3-turbo": "whisper-1",
}

HF_MODEL_ALIASES: Dict[str, str] = {
    "distil-large-v3": "distil-whisper/distil-large-v3",
    "large-v3": "openai/whisper-large-v3",
}

LOCAL_MODEL_ALIASES: Dict[str, str] = {
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


class TranscriptionError(Exception):
    """Raised when transcription fails."""

    pass


def parse_model_and_provider(
    model_arg: str, provider_arg: Optional[str] = None
) -> Tuple[str, str]:
    """Parse model/provider from user input.

    Returns (provider, normalized_model_id).

    Rules:
    - Explicit provider via provider_arg takes precedence.
    - Prefix syntax "openai:large-v3-turbo" or "hf:distil-large-v3" selects provider.
    - Otherwise default to local provider.
    - Alias maps normalize to backend-specific ids.

    Args:
        model_arg: Model string (possibly with provider prefix)
        provider_arg: Explicit provider override

    Returns:
        Tuple of (provider, normalized_model_id)
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


class TranscriptionEngine:
    """Pure transcription logic with no UI dependencies.

    Supports multiple backends: local (faster-whisper), OpenAI API, Hugging Face.
    Can be used by CLI, web API, or any other interface.
    """

    def __init__(
        self,
        model: str = "small",
        provider: Optional[str] = None,
        compute_type: Optional[str] = None,
        device: Optional[str] = None,
        vad_filter: bool = True,
        condition_on_previous_text: bool = True,
        extra_decode_options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize transcription engine.

        Args:
            model: Model identifier (may include provider prefix like "openai:large-v3-turbo")
            provider: Explicit provider override (auto-detect if None)
            compute_type: Compute type for local models (auto-detect if None)
            device: Device to use (auto-detect if None: cuda/cpu)
            vad_filter: Enable voice activity detection filtering
            condition_on_previous_text: Enable conditioning on previous text
            extra_decode_options: Additional decoder options
            progress_callback: Optional callback for progress updates
        """
        self.provider, self.normalized_model = parse_model_and_provider(model, provider)

        # Auto-detect device if not specified (CTranslate2 only supports CUDA/CPU)
        self.device = device if device is not None else detect_device_for_ctranslate2()

        # Auto-select optimal compute type for device if not specified
        self.compute_type = (
            compute_type
            if compute_type is not None
            else get_optimal_compute_type(self.device)
        )

        self.vad_filter = vad_filter
        self.condition_on_previous_text = condition_on_previous_text
        self.extra_decode_options = extra_decode_options or {}
        self.progress_callback = progress_callback

    def _report_progress(self, message: str):
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(message)

    def transcribe(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe audio file using configured backend.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcript dictionary with segments, text, language, and metadata

        Raises:
            TranscriptionError: If transcription fails
            FileNotFoundError: If audio file doesn't exist
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(
            "Starting transcription",
            provider=self.provider,
            model=self.normalized_model,
            audio=str(audio_path),
        )

        # Dispatch to provider-specific method
        if self.provider == "local":
            return self._transcribe_local(audio_path)
        elif self.provider == "openai":
            return self._transcribe_openai(audio_path)
        elif self.provider == "hf":
            return self._transcribe_huggingface(audio_path)
        else:
            raise TranscriptionError(f"Unknown ASR provider: {self.provider}")

    def _transcribe_local(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe using local faster-whisper model."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise TranscriptionError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )

        self._report_progress(f"Loading model: {self.normalized_model}")

        # Log device usage for transparency
        log_device_usage(self.device, self.compute_type, "transcription")

        try:
            asr = WhisperModel(
                self.normalized_model,
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception as e:
            raise TranscriptionError(f"Failed to initialize Whisper model: {e}") from e

        self._report_progress("Transcribing audio")

        # Build transcription kwargs
        transcribe_kwargs: Dict[str, Any] = {
            "vad_filter": self.vad_filter,
            "vad_parameters": {"min_silence_duration_ms": 500},
            "condition_on_previous_text": self.condition_on_previous_text,
        }
        transcribe_kwargs.update(self.extra_decode_options)

        try:
            seg_iter, info = asr.transcribe(str(audio_path), **transcribe_kwargs)
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}") from e

        # Collect segments
        segments = []
        text_lines = []
        for s in seg_iter:
            segments.append({"start": s.start, "end": s.end, "text": s.text})
            text_lines.append(s.text)

        detected_language = getattr(info, "language", "en")

        logger.info(
            "Transcription completed",
            segments_count=len(segments),
            language=detected_language,
        )

        return {
            "audio_path": str(audio_path.resolve()),
            "language": detected_language,
            "asr_model": self.normalized_model,
            "asr_provider": "local",
            "decoder_options": {"vad_filter": self.vad_filter},
            "segments": segments,
            "text": "\n".join(text_lines).strip(),
        }

    def _transcribe_openai(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper API."""
        self._report_progress(f"Using OpenAI API: {self.normalized_model}")

        try:
            # Try new SDK first
            try:
                from openai import OpenAI

                client = OpenAI()
                use_new_sdk = True
            except Exception:
                import openai  # type: ignore

                use_new_sdk = False

            with open(str(audio_path), "rb") as f:
                if use_new_sdk:
                    resp = client.audio.transcriptions.create(
                        model=self.normalized_model,
                        file=f,
                        response_format="verbose_json",
                    )
                    text = getattr(resp, "text", None) or (
                        resp.get("text") if isinstance(resp, dict) else None
                    )
                    segs_raw = getattr(resp, "segments", None) or (
                        resp.get("segments") if isinstance(resp, dict) else None
                    )
                else:
                    resp = openai.Audio.transcriptions.create(
                        model=self.normalized_model,
                        file=f,
                        response_format="verbose_json",
                    )
                    text = resp.get("text")
                    segs_raw = resp.get("segments")

            # Parse segments
            segments: List[Dict[str, Any]] = []
            if segs_raw:
                for s in segs_raw:
                    start = s.get("start")
                    end = s.get("end")
                    txt = s.get("text", "")
                    # Handle timestamp format variations
                    if start is None or end is None:
                        ts = s.get("timestamp")
                        if isinstance(ts, (list, tuple)) and len(ts) == 2:
                            start, end = ts[0], ts[1]
                    if start is None:
                        start = 0.0
                    if end is None:
                        end = 0.0
                    segments.append(
                        {"start": float(start), "end": float(end), "text": txt}
                    )
            else:
                # Fallback: single segment
                txt = text or ""
                segments = [{"start": 0.0, "end": 0.0, "text": txt}]

            logger.info("OpenAI transcription completed", segments_count=len(segments))

            return {
                "audio_path": str(audio_path.resolve()),
                "language": "en",
                "asr_model": self.normalized_model,
                "asr_provider": "openai",
                "decoder_options": None,
                "segments": segments,
                "text": "\n".join([s["text"] for s in segments]).strip(),
            }

        except Exception as e:
            raise TranscriptionError(f"OpenAI transcription failed: {e}") from e

    def _transcribe_huggingface(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe using Hugging Face transformers pipeline."""
        self._report_progress(f"Using Hugging Face: {self.normalized_model}")

        try:
            from transformers import pipeline  # type: ignore
        except ImportError:
            raise TranscriptionError(
                "transformers not installed. "
                "Install with: pip install transformers torchaudio"
            )

        try:
            asr = pipeline(
                "automatic-speech-recognition",
                model=self.normalized_model,
                return_timestamps="chunk",
            )
            result = asr(str(audio_path), chunk_length_s=30, stride_length_s=5)

            # Parse chunks
            segments: List[Dict[str, Any]] = []
            chunks = result.get("chunks") if isinstance(result, dict) else None
            if chunks:
                for c in chunks:
                    ts = c.get("timestamp") or c.get("timestamps")
                    if isinstance(ts, (list, tuple)) and len(ts) == 2:
                        start, end = ts
                    else:
                        start, end = 0.0, 0.0
                    segments.append(
                        {
                            "start": float(start),
                            "end": float(end),
                            "text": c.get("text", ""),
                        }
                    )
            else:
                # Fallback: one segment
                text_val = result.get("text") if isinstance(result, dict) else ""
                segments = [{"start": 0.0, "end": 0.0, "text": text_val}]

            logger.info(
                "Hugging Face transcription completed", segments_count=len(segments)
            )

            return {
                "audio_path": str(audio_path.resolve()),
                "language": "en",
                "asr_model": self.normalized_model,
                "asr_provider": "hf",
                "decoder_options": None,
                "segments": segments,
                "text": "\n".join([s["text"] for s in segments]).strip(),
            }

        except Exception as e:
            raise TranscriptionError(f"Hugging Face transcription failed: {e}") from e


# Convenience functions for direct use
def transcribe_audio(
    audio_path: Path,
    model: str = "small",
    provider: Optional[str] = None,
    compute_type: Optional[str] = None,
    device: Optional[str] = None,
    vad_filter: bool = True,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Transcribe audio file with specified model.

    Args:
        audio_path: Path to audio file
        model: Model identifier
        provider: Provider override
        compute_type: Compute type for local models (auto-detect if None)
        device: Device to use (auto-detect if None)
        vad_filter: Enable VAD filtering
        progress_callback: Optional progress callback

    Returns:
        Transcript dictionary
    """
    engine = TranscriptionEngine(
        model=model,
        provider=provider,
        compute_type=compute_type,
        device=device,
        vad_filter=vad_filter,
        progress_callback=progress_callback,
    )
    return engine.transcribe(audio_path)
