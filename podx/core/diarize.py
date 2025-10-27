"""Core diarization engine - pure business logic.

No UI dependencies, no CLI concerns. Just speaker diarization using WhisperX.
Two-step process: alignment (word-level timing) + diarization (speaker identification).
"""
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..logging import get_logger

logger = get_logger(__name__)


class DiarizationError(Exception):
    """Raised when diarization fails."""

    pass


class DiarizationEngine:
    """Pure diarization logic with no UI dependencies.

    Uses WhisperX for two-step process:
    1. Alignment: Add word-level timing to transcript segments
    2. Diarization: Identify speakers and assign to words

    Can be used by CLI, TUI studio, web API, or any other interface.
    """

    def __init__(
        self,
        language: str = "en",
        device: str = "cpu",
        hf_token: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize diarization engine.

        Args:
            language: Language code for alignment model (e.g., 'en', 'es')
            device: Device to use ('cpu' or 'cuda')
            hf_token: Hugging Face token for diarization pipeline (optional)
            progress_callback: Optional callback for progress updates
        """
        self.language = language
        self.device = device
        self.hf_token = hf_token or os.getenv("HUGGINGFACE_TOKEN")
        self.progress_callback = progress_callback

    def _report_progress(self, message: str):
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(message)

    def diarize(
        self,
        audio_path: Path,
        transcript_segments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Diarize audio using WhisperX alignment and speaker identification.

        Args:
            audio_path: Path to audio file
            transcript_segments: List of transcript segments with text and timing

        Returns:
            Dictionary with diarized transcript including word-level speaker labels

        Raises:
            DiarizationError: If alignment or diarization fails
            FileNotFoundError: If audio file doesn't exist
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(
            "Starting diarization",
            audio=str(audio_path),
            language=self.language,
            segments_count=len(transcript_segments),
        )

        try:
            import whisperx
            from whisperx.diarize import DiarizationPipeline, assign_word_speakers
        except ImportError:
            raise DiarizationError(
                "whisperx not installed. Install with: pip install whisperx"
            )

        # Step 1: Alignment - add word-level timing
        self._report_progress("Loading alignment model")
        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=self.language, device=self.device
            )
        except Exception as e:
            raise DiarizationError(f"Failed to load alignment model: {e}") from e

        self._report_progress("Loading audio")
        try:
            audio_data = whisperx.load_audio(str(audio_path))
        except Exception as e:
            raise DiarizationError(f"Failed to load audio: {e}") from e

        self._report_progress("Aligning transcript")
        try:
            aligned_result = whisperx.align(
                transcript_segments,
                model_a,
                metadata,
                audio_data,
                device=self.device,
                return_char_alignments=False,
            )
        except Exception as e:
            raise DiarizationError(f"Alignment failed: {e}") from e

        logger.info("Alignment completed", segments_count=len(aligned_result.get("segments", [])))

        # Step 2: Diarization - assign speakers to words
        self._report_progress("Loading diarization model")
        try:
            dia = DiarizationPipeline(
                use_auth_token=self.hf_token, device=self.device
            )
        except Exception as e:
            raise DiarizationError(f"Failed to load diarization model: {e}") from e

        self._report_progress("Identifying speakers")
        try:
            diarized = dia(str(audio_path))
            final = assign_word_speakers(diarized, aligned_result)
        except Exception as e:
            raise DiarizationError(f"Diarization failed: {e}") from e

        # Count speakers
        speakers = set()
        for seg in final.get("segments", []):
            for word in seg.get("words", []):
                if "speaker" in word:
                    speakers.add(word["speaker"])

        logger.info(
            "Diarization completed",
            segments_count=len(final.get("segments", [])),
            speakers_count=len(speakers),
        )

        return final


# Convenience function for direct use
def diarize_transcript(
    audio_path: Path,
    transcript_segments: List[Dict[str, Any]],
    language: str = "en",
    device: str = "cpu",
    hf_token: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Diarize transcript with speaker identification.

    Args:
        audio_path: Path to audio file
        transcript_segments: List of transcript segments
        language: Language code for alignment
        device: Device to use ('cpu' or 'cuda')
        hf_token: Hugging Face token (optional)
        progress_callback: Optional progress callback

    Returns:
        Diarized transcript dictionary
    """
    engine = DiarizationEngine(
        language=language,
        device=device,
        hf_token=hf_token,
        progress_callback=progress_callback,
    )
    return engine.diarize(audio_path, transcript_segments)
