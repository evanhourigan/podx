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
        skip_ads: bool = False,
        max_gap: float = 1.0,
        max_len: int = 800,
        restore_model: str = "gpt-4o-mini",
        ad_batch_size: int = 30,
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
            skip_ads: Filter out advertisement segments (requires LLM)
            max_gap: Maximum gap (seconds) between segments to merge
            max_len: Maximum merged text length (characters)
            restore_model: Model for LLM operations (restore and ad classification)
            ad_batch_size: Segments per LLM request for ad classification
            restore_batch_size: Segments per LLM request for restore
            llm_provider: Optional pre-configured LLM provider instance
            provider_name: Provider to use if llm_provider not provided (default: openai)
            progress: Optional progress reporter for status updates
        """
        self.merge = merge
        self.normalize = normalize
        self.restore = restore
        self.skip_ads = skip_ads
        self.max_gap = max_gap
        self.max_len = max_len
        self.restore_model = restore_model
        self.ad_batch_size = ad_batch_size
        self.restore_batch_size = restore_batch_size
        self.progress = progress or SilentProgressReporter()

        # Use provided provider or create one
        self.llm_provider: Optional[LLMProvider] = None
        if llm_provider:
            self.llm_provider = llm_provider
        elif restore or skip_ads:
            # Create provider if any LLM feature is enabled
            try:
                self.llm_provider = get_provider(provider_name)
            except Exception as e:
                raise PreprocessError(f"Failed to initialize LLM provider: {e}") from e

    def merge_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge adjacent segments based on timing gaps, length, and speaker.

        Args:
            segments: List of segment dictionaries with text, start, end, and optionally speaker

        Returns:
            List of merged segments (preserving speaker labels)
        """
        if not segments:
            return []

        merged: List[Dict[str, Any]] = []
        current = {
            "text": segments[0]["text"],
            "start": segments[0]["start"],
            "end": segments[0]["end"],
        }
        # Preserve speaker if present
        if "speaker" in segments[0]:
            current["speaker"] = segments[0]["speaker"]

        for seg in segments[1:]:
            gap = float(seg["start"]) - float(current["end"])
            same_speaker = current.get("speaker") == seg.get("speaker")

            # Only merge if: small gap, within length limit, AND same speaker (or both have no speaker)
            if (
                gap < self.max_gap
                and len(current["text"]) + len(seg["text"]) < self.max_len
                and same_speaker
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
                # Preserve speaker if present
                if "speaker" in seg:
                    current["speaker"] = seg["speaker"]

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

    def normalize_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply text normalization to all segments.

        Args:
            segments: List of segment dictionaries

        Returns:
            List of segments with normalized text
        """
        for s in segments:
            s["text"] = self.normalize_text(s.get("text", ""))
        return segments

    def classify_ad_segments(self, segments: List[Dict[str, Any]]) -> List[bool]:
        """Classify segments as advertisement or content using LLM.

        Args:
            segments: List of transcript segments

        Returns:
            List of booleans - True if segment is an ad, False if content

        Raises:
            PreprocessError: If LLM API fails
        """
        if not self.llm_provider:
            raise PreprocessError("LLM provider not configured. Enable skip_ads in constructor.")

        system_prompt = (
            "You are classifying podcast transcript segments as ADVERTISEMENT or CONTENT.\n\n"
            "ADVERTISEMENT includes:\n"
            '- Sponsor reads ("This episode is brought to you by...")\n'
            '- Promo codes, discount offers ("Use code X for 20% off")\n'
            "- Product/service pitches unrelated to episode topic\n"
            "- Pre-roll/mid-roll/post-roll ads\n"
            '- Calls to action for sponsors ("Check out example.com")\n\n'
            "CONTENT includes:\n"
            "- Main episode discussion\n"
            "- Host introductions/outros about the show itself\n"
            "- Guest introductions\n"
            "- Topic discussion, even if mentioning products relevant to the topic\n\n"
            'For each segment, output ONLY "AD" or "CONTENT" on a separate line.\n'
            "Output one classification per line, in the same order as the input segments."
        )

        is_ad: List[bool] = []
        total_batches = (len(segments) + self.ad_batch_size - 1) // self.ad_batch_size

        for i in range(0, len(segments), self.ad_batch_size):
            batch_num = i // self.ad_batch_size + 1
            batch = segments[i : i + self.ad_batch_size]

            # Report progress
            self.progress.update_step(
                f"Classifying ads batch {batch_num}/{total_batches}",
                step=batch_num,
                progress=batch_num / total_batches,
            )

            # Format segments for classification
            delimiter = "\n---SEGMENT---\n"
            batch_text = delimiter.join([s.get("text", "")[:500] for s in batch])
            user_prompt = (
                f"Classify these {len(batch)} transcript segments.\n"
                f"Segments are separated by '---SEGMENT---'.\n\n"
                f"{batch_text}"
            )

            try:
                messages = [
                    LLMMessage.system(system_prompt),
                    LLMMessage.user(user_prompt),
                ]
                response = self.llm_provider.complete(messages=messages, model=self.restore_model)
                result = response.content.strip()
            except Exception as e:
                logger.error(f"LLM API request failed for ad classification batch {batch_num}: {e}")
                raise PreprocessError(f"Ad classification failed: {e}") from e

            # Parse response - each line should be AD or CONTENT
            lines = [line.strip().upper() for line in result.split("\n") if line.strip()]

            # Map to booleans
            batch_results = []
            for j, line in enumerate(lines[: len(batch)]):
                # Conservative: only mark as ad if explicitly "AD"
                batch_results.append(line == "AD")

            # If LLM returned fewer results, assume remaining are content
            while len(batch_results) < len(batch):
                logger.warning(
                    f"Ad classification returned {len(lines)} results for {len(batch)} segments. "
                    "Assuming remaining are content."
                )
                batch_results.append(False)

            is_ad.extend(batch_results)

        return is_ad

    def filter_ad_segments(
        self, segments: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], int]:
        """Filter out advertisement segments.

        Args:
            segments: List of transcript segments

        Returns:
            Tuple of (filtered segments, count of ads removed)
        """
        if not segments:
            return [], 0

        # Classify all segments
        is_ad = self.classify_ad_segments(segments)

        # Filter out ads
        filtered = [seg for seg, ad in zip(segments, is_ad) if not ad]
        ads_removed = len(segments) - len(filtered)

        if ads_removed > 0:
            logger.info(f"Filtered {ads_removed} advertisement segment(s)")

        return filtered, ads_removed

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
            raise PreprocessError("LLM provider not configured. Enable restore in constructor.")

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
                response = self.llm_provider.complete(messages=messages, model=self.restore_model)
                batch_result = response.content
            except Exception as e:
                logger.error(f"LLM API request failed for batch {batch_num}: {e}")
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
        ads_removed = 0

        # Ad filtering first (before other processing)
        if self.skip_ads and segs:
            logger.debug(f"Filtering ads with {self.restore_model}")
            try:
                segs, ads_removed = self.filter_ad_segments(segs)
            except PreprocessError as e:
                logger.warning(f"Ad filtering failed: {e}")
                raise

        if self.merge:
            logger.debug(f"Merging segments (max_gap={self.max_gap}s, max_len={self.max_len})")
            segs = self.merge_segments(segs)

        if self.normalize:
            logger.debug("Normalizing text")
            segs = self.normalize_segments(segs)

        if self.restore and segs:
            logger.debug(f"Semantic restore with {self.restore_model}")
            try:
                restored_texts = self.semantic_restore([s.get("text", "") for s in segs])
                for i, txt in enumerate(restored_texts):
                    segs[i]["text"] = txt
            except PreprocessError as e:
                logger.warning(f"Semantic restore failed: {e}")
                raise

        out["segments"] = segs
        out["text"] = "\n".join([s.get("text", "") for s in segs]).strip()
        out["ads_removed"] = ads_removed

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
