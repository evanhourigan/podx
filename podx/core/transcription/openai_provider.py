"""OpenAI Whisper API ASR provider."""

from pathlib import Path
from typing import Any, Dict, List

from ...logging import get_logger
from .base import ASRProvider, TranscriptionError, TranscriptionResult

logger = get_logger(__name__)

# Model aliases for OpenAI provider
# OpenAI only has one Whisper API model called "whisper-1"
OPENAI_MODEL_ALIASES: Dict[str, str] = {
    "large-v3": "whisper-1",
    "large-v3-turbo": "whisper-1",
    "whisper-1": "whisper-1",
}


class OpenAIProvider(ASRProvider):
    """ASR provider using OpenAI Whisper API.

    This provider uses OpenAI's cloud-based Whisper API for transcription.
    Requires OPENAI_API_KEY environment variable to be set.
    """

    @property
    def name(self) -> str:
        """Get provider name."""
        return "openai"

    @property
    def supported_models(self) -> List[str]:
        """Get list of supported model identifiers."""
        return list(OPENAI_MODEL_ALIASES.keys())

    def normalize_model(self, model: str) -> str:
        """Normalize model identifier to OpenAI API format.

        OpenAI only has one Whisper model called 'whisper-1', so we
        map all model names to that.
        """
        return OPENAI_MODEL_ALIASES.get(model, "whisper-1")

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe audio using OpenAI Whisper API.

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptionResult with transcript data

        Raises:
            TranscriptionError: If transcription fails
            FileNotFoundError: If audio file doesn't exist
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        normalized_model = self.normalize_model(self.config.model)

        logger.info(
            "Starting OpenAI transcription",
            model=normalized_model,
            audio=str(audio_path),
        )

        self._report_progress(f"Using OpenAI API: {normalized_model}")

        try:
            from openai import OpenAI

            client = OpenAI()

            with open(str(audio_path), "rb") as f:
                resp = client.audio.transcriptions.create(
                    model=normalized_model,
                    file=f,
                    response_format="verbose_json",
                )
                text = getattr(resp, "text", None) or (
                    resp.get("text") if isinstance(resp, dict) else None
                )
                segs_raw = getattr(resp, "segments", None) or (
                    resp.get("segments") if isinstance(resp, dict) else None
                )

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
                    segments.append({"start": start, "end": end, "text": txt})

            logger.info(
                "OpenAI transcription completed",
                segments_count=len(segments),
            )

            return TranscriptionResult(
                audio_path=str(audio_path.resolve()),
                language=self.config.language,  # OpenAI doesn't return detected language
                asr_model=normalized_model,
                asr_provider=self.name,
                segments=segments,
                text=text or "",
                decoder_options={},
            )

        except ImportError as e:
            raise TranscriptionError(
                f"OpenAI SDK not installed. Install with: pip install openai: {e}"
            ) from e
        except Exception as e:
            raise TranscriptionError(f"OpenAI transcription failed: {e}") from e
