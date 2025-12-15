"""Local faster-whisper ASR provider."""

from pathlib import Path
from typing import Any, Dict, List

from ...device import detect_device_for_ctranslate2, get_optimal_compute_type, log_device_usage
from ...logging import get_logger
from .base import ASRProvider, ProviderConfig, TranscriptionError, TranscriptionResult

logger = get_logger(__name__)

# Model aliases for local provider
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


class LocalProvider(ASRProvider):
    """ASR provider using local faster-whisper models.

    This provider runs Whisper models locally using CTranslate2 for efficient inference.
    Supports CUDA/CPU with automatic device detection and optimization.
    """

    def __init__(self, config: ProviderConfig):
        """Initialize local provider.

        Args:
            config: Provider configuration
        """
        super().__init__(config)

        # Auto-detect device if not specified (CTranslate2 only supports CUDA/CPU)
        if self.config.device is None:
            self.config.device = detect_device_for_ctranslate2()

        # Auto-select optimal compute type for device if not specified
        if self.config.compute_type is None:
            self.config.compute_type = get_optimal_compute_type(self.config.device)

        # Normalize model identifier
        self.normalized_model = self.normalize_model(self.config.model)

    @property
    def name(self) -> str:
        """Get provider name."""
        return "local"

    @property
    def supported_models(self) -> List[str]:
        """Get list of supported model identifiers."""
        return list(LOCAL_MODEL_ALIASES.keys())

    def normalize_model(self, model: str) -> str:
        """Normalize model identifier to faster-whisper format."""
        return LOCAL_MODEL_ALIASES.get(model, model)

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe audio using local faster-whisper model.

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

        logger.info(
            "Starting local transcription",
            model=self.normalized_model,
            device=self.config.device,
            compute_type=self.config.compute_type,
            audio=str(audio_path),
        )

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise TranscriptionError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )

        self._report_progress(f"Loading model: {self.normalized_model}")

        # Log device usage for transparency
        log_device_usage(
            self.config.device or "cpu",
            self.config.compute_type or "int8",
            "transcription",
        )

        try:
            asr = WhisperModel(
                self.normalized_model,
                device=self.config.device,
                compute_type=self.config.compute_type,
            )
        except Exception as e:
            raise TranscriptionError(f"Failed to initialize Whisper model: {e}") from e

        self._report_progress("Transcribing audio")

        # Build transcription kwargs
        transcribe_kwargs: Dict[str, Any] = {
            "vad_filter": self.config.vad_filter,
            "vad_parameters": {"min_silence_duration_ms": 500},
            "condition_on_previous_text": self.config.condition_on_previous_text,
        }
        transcribe_kwargs.update(self.config.extra_options)

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

        detected_language = getattr(info, "language", self.config.language)

        logger.info(
            "Local transcription completed",
            segments_count=len(segments),
            language=detected_language,
        )

        return TranscriptionResult(
            audio_path=str(audio_path.resolve()),
            language=detected_language,
            asr_model=self.normalized_model,
            asr_provider=self.name,
            segments=segments,
            text="\n".join(text_lines).strip(),
            decoder_options={"vad_filter": self.config.vad_filter},
        )
