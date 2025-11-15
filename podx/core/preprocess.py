"""Core transcript preprocessing engine - pure business logic.

No UI dependencies, no CLI concerns. Just transcript text processing.
"""

import re
from typing import Any, Dict, List, Optional

from ..llm import LLMMessage, LLMProvider, get_provider
from ..logging import get_logger
from ..progress import ProgressReporter, SilentProgressReporter

logger = get_logger(__name__)


class PreprocessError(Exception):
    """Raised when preprocessing fails."""

    pass


class TranscriptPreprocessor:
    """Pure transcript preprocessing logic with no UI dependencies.

    Can be used by CLI, web API, or any other interface.
    """

    def __init__(
        self,
        merge: bool = False,
        normalize: bool = False,
        restore: bool = False,
        max_gap: float = 1.0,
        max_len: int = 800,
        restore_model: str = "gpt-4o-mini",
        restore_batch_size: int = 20,
        llm_provider: Optional[LLMProvider] = None,
        provider_name: str = "openai",
        progress: Optional[ProgressReporter] = None,
    ):
        """Initialize transcript preprocessor.

        Args:
            merge: Merge adjacent short segments
            normalize: Normalize whitespace and punctuation
            restore: Use LLM to restore punctuation/grammar
            max_gap: Maximum gap (seconds) between segments to merge
            max_len: Maximum merged text length (characters)
            restore_model: Model for semantic restore
            restore_batch_size: Segments per LLM request
            llm_provider: Optional pre-configured LLM provider instance
            provider_name: Provider to use if llm_provider not provided (default: openai)
            progress: Optional progress reporter for status updates
        """
        self.merge = merge
        self.normalize = normalize
        self.restore = restore
        self.max_gap = max_gap
        self.max_len = max_len
        self.restore_model = restore_model
        self.restore_batch_size = restore_batch_size
        self.progress = progress or SilentProgressReporter()

        # Use provided provider or create one
        if llm_provider:
            self.llm_provider = llm_provider
        elif restore:
            # Only create provider if restore is enabled
            try:
                self.llm_provider = get_provider(provider_name)
            except Exception as e:
                raise PreprocessError(f"Failed to initialize LLM provider: {e}") from e
        else:
            self.llm_provider = None

    def merge_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge adjacent segments based on timing gaps and length.

        Args:
            segments: List of segment dictionaries with text, start, end

        Returns:
            List of merged segments
        """
        if not segments:
            return []

        merged: List[Dict[str, Any]] = []
        current = {
            "text": segments[0]["text"],
            "start": segments[0]["start"],
            "end": segments[0]["end"],
        }

        for seg in segments[1:]:
            gap = float(seg["start"]) - float(current["end"])
            if (
                gap < self.max_gap
                and len(current["text"]) + len(seg["text"]) < self.max_len
            ):
                current["text"] += " " + seg["text"]
                current["end"] = seg["end"]
            else:
                merged.append(current)
                current = {
                    "text": seg["text"],
                    "start": seg["start"],
                    "end": seg["end"],
                }

        merged.append(current)
        return merged

    def normalize_text(self, text: str) -> str:
        """Normalize whitespace and punctuation in text.

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        # Collapse multiple whitespace
        text = re.sub(r"\s+", " ", text)
        # Ensure space after sentence-ending punctuation
        text = re.sub(r"([.?!])([A-Za-z])", r"\1 \2", text)
        return text.strip()

    def normalize_segments(
        self, segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply text normalization to all segments.

        Args:
            segments: List of segment dictionaries

        Returns:
            List of segments with normalized text
        """
        for s in segments:
            s["text"] = self.normalize_text(s.get("text", ""))
        return segments

    def semantic_restore(self, texts: List[str]) -> List[str]:
        """Use LLM to restore punctuation and grammar.

        Args:
            texts: List of text segments to restore

        Returns:
            List of restored text segments

        Raises:
            PreprocessError: If LLM API fails
        """
        if not self.llm_provider:
            raise PreprocessError(
                "LLM provider not configured. Enable restore in constructor."
            )

        prompt = (
            "You are cleaning up noisy ASR transcript text.\n"
            "- Fix grammar and punctuation.\n"
            "- Preserve every idea and clause, even incomplete ones.\n"
            "- Do NOT remove filler words that imply transitions.\n"
            "Return only the cleaned text."
        )

        out: List[str] = []
        total_batches = (len(texts) + self.restore_batch_size - 1) // self.restore_batch_size

        for i in range(0, len(texts), self.restore_batch_size):
            batch_num = i // self.restore_batch_size + 1
            chunk = texts[i : i + self.restore_batch_size]

            # Report progress
            self.progress.update_step(
                f"Restoring batch {batch_num}/{total_batches}",
                step=batch_num,
                progress=batch_num / total_batches,
            )

            # Batch processing: join texts with delimiter
            delimiter = "\n---SEGMENT---\n"
            batch_text = delimiter.join(chunk)
            batch_prompt = (
                f"Clean up these {len(chunk)} transcript segments. "
                f"Return them in the same order, separated by '{delimiter.strip()}'.\n\n"
                f"{batch_text}"
            )

            try:
                messages = [
                    LLMMessage.system(prompt),
                    LLMMessage.user(batch_prompt),
                ]
                response = self.llm_provider.complete(
                    messages=messages, model=self.restore_model
                )
                batch_result = response.content
            except Exception as e:
                logger.error(
                    f"LLM API request failed for batch {batch_num}: {e}"
                )
                raise PreprocessError(f"Semantic restore failed: {e}") from e

            # Split response back into individual segments
            cleaned_chunks = batch_result.split(delimiter)

            # Handle case where LLM doesn't return exact number
            if len(cleaned_chunks) == len(chunk):
                out.extend([c.strip() for c in cleaned_chunks])
            else:
                # Fallback: if batch processing failed, keep originals
                logger.warning(
                    f"Batch restore returned {len(cleaned_chunks)} segments, "
                    f"expected {len(chunk)}. Using original texts for this batch."
                )
                out.extend(chunk)

        return out

    def preprocess(self, transcript: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess transcript with configured options.

        Args:
            transcript: Transcript dictionary with segments field

        Returns:
            Processed transcript dictionary

        Raises:
            PreprocessError: If preprocessing fails
            ValueError: If transcript format invalid
        """
        if not transcript or "segments" not in transcript:
            raise ValueError("Transcript must contain 'segments' field")

        # Copy through metadata
        out: Dict[str, Any] = {
            "audio_path": transcript.get("audio_path"),
            "language": transcript.get("language"),
            "asr_model": transcript.get("asr_model"),
            "asr_provider": transcript.get("asr_provider"),
            "decoder_options": transcript.get("decoder_options"),
        }

        # Process segments
        segs = transcript.get("segments", [])

        if self.merge:
            logger.debug(
                f"Merging segments (max_gap={self.max_gap}s, max_len={self.max_len})"
            )
            segs = self.merge_segments(segs)

        if self.normalize:
            logger.debug("Normalizing text")
            segs = self.normalize_segments(segs)

        if self.restore and segs:
            logger.debug(f"Semantic restore with {self.restore_model}")
            try:
                restored_texts = self.semantic_restore(
                    [s.get("text", "") for s in segs]
                )
                for i, txt in enumerate(restored_texts):
                    segs[i]["text"] = txt
            except PreprocessError as e:
                logger.warning(f"Semantic restore failed: {e}")
                raise

        out["segments"] = segs
        out["text"] = "\n".join([s.get("text", "") for s in segs]).strip()

        return out


# Convenience functions for direct use
def merge_segments(
    segments: List[Dict[str, Any]], max_gap: float = 1.0, max_len: int = 800
) -> List[Dict[str, Any]]:
    """Merge adjacent transcript segments.

    Args:
        segments: List of segments
        max_gap: Maximum gap in seconds
        max_len: Maximum merged text length

    Returns:
        List of merged segments
    """
    preprocessor = TranscriptPreprocessor(merge=True, max_gap=max_gap, max_len=max_len)
    return preprocessor.merge_segments(segments)


def normalize_text(text: str) -> str:
    """Normalize whitespace and punctuation in text.

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    preprocessor = TranscriptPreprocessor(normalize=True)
    return preprocessor.normalize_text(text)


def normalize_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize text in all segments.

    Args:
        segments: List of segments

    Returns:
        List of segments with normalized text
    """
    preprocessor = TranscriptPreprocessor(normalize=True)
    return preprocessor.normalize_segments(segments)


def preprocess_transcript(
    transcript: Dict[str, Any],
    merge: bool = False,
    normalize: bool = False,
    restore: bool = False,
    max_gap: float = 1.0,
    max_len: int = 800,
    restore_model: str = "gpt-4.1-mini",
    restore_batch_size: int = 20,
) -> Dict[str, Any]:
    """Preprocess a transcript with specified options.

    Args:
        transcript: Transcript dictionary
        merge: Merge adjacent segments
        normalize: Normalize text
        restore: Use LLM to restore punctuation
        max_gap: Maximum gap for merging
        max_len: Maximum merged length
        restore_model: LLM model for restore
        restore_batch_size: Batch size for restore

    Returns:
        Processed transcript dictionary
    """
    preprocessor = TranscriptPreprocessor(
        merge=merge,
        normalize=normalize,
        restore=restore,
        max_gap=max_gap,
        max_len=max_len,
        restore_model=restore_model,
        restore_batch_size=restore_batch_size,
    )
    return preprocessor.preprocess(transcript)
