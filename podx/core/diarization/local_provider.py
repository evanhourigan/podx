"""Local diarization provider using pyannote/WhisperX.

Wraps the existing DiarizationEngine to implement the DiarizationProvider interface.
"""

from pathlib import Path
from typing import Any, Dict, List

from ...logging import get_logger
from ..diarize import DiarizationEngine, DiarizationError
from .base import DiarizationProvider, DiarizationProviderError, DiarizationResult

logger = get_logger(__name__)


class LocalDiarizationProvider(DiarizationProvider):
    """Diarization provider using local pyannote/WhisperX models.

    Wraps the existing DiarizationEngine to provide the standard
    DiarizationProvider interface. This is the default provider
    when no cloud backend is specified.

    Features:
    - Word-level speaker alignment via WhisperX
    - Memory-aware chunking for long audio
    - Speaker re-identification across chunks
    - GPU acceleration on CUDA/MPS devices
    """

    @property
    def name(self) -> str:
        """Get provider name."""
        return "local"

    def diarize(
        self,
        audio_path: Path,
        transcript_segments: List[Dict[str, Any]],
    ) -> DiarizationResult:
        """Diarize audio using local pyannote/WhisperX models.

        Args:
            audio_path: Path to audio file
            transcript_segments: List of transcript segments with text and timing

        Returns:
            DiarizationResult with speaker-labeled segments

        Raises:
            DiarizationProviderError: If diarization fails
            FileNotFoundError: If audio file doesn't exist
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(
            "Starting local diarization",
            audio=str(audio_path),
            language=self.config.language,
            segments_count=len(transcript_segments),
        )

        try:
            # Create and run the existing diarization engine
            engine = DiarizationEngine(
                language=self.config.language,
                device=self.config.device,
                hf_token=self.config.hf_token,
                progress_callback=self.config.progress_callback,
                num_speakers=self.config.num_speakers,
                min_speakers=self.config.min_speakers,
                max_speakers=self.config.max_speakers,
            )

            result = engine.diarize(audio_path, transcript_segments)

            # Count speakers
            speakers = set()
            for seg in result.get("segments", []):
                for word in seg.get("words", []):
                    if "speaker" in word:
                        speakers.add(word["speaker"])

            # Check if chunking was used
            chunked = False
            chunk_info = None
            if hasattr(engine, "_chunking_info"):
                chunked = engine._chunking_info.get("needs_chunking", False)
            if hasattr(engine, "_chunk_info"):
                chunk_info = engine._chunk_info

            logger.info(
                "Local diarization completed",
                segments_count=len(result.get("segments", [])),
                speakers_count=len(speakers),
                chunked=chunked,
            )

            return DiarizationResult(
                audio_path=str(audio_path.resolve()),
                segments=result.get("segments", []),
                provider=self.name,
                speakers_count=len(speakers),
                language=self.config.language,
                chunked=chunked,
                chunk_info=chunk_info,
            )

        except DiarizationError as e:
            raise DiarizationProviderError(str(e)) from e
        except Exception as e:
            logger.error("Unexpected error during local diarization", error=str(e))
            raise DiarizationProviderError(f"Local diarization failed: {e}") from e
