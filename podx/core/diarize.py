"""Core diarization engine - pure business logic.

No UI dependencies, no CLI concerns. Just speaker diarization using WhisperX.
Two-step process: alignment (word-level timing) + diarization (speaker identification).
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import psutil
from scipy.spatial.distance import cosine

from ..device import detect_device_for_pytorch, log_device_usage
from ..logging import get_logger

logger = get_logger(__name__)


def get_memory_info() -> Tuple[float, float]:
    """Get available and total system memory in GB.

    Returns:
        Tuple of (available_gb, total_gb)
    """
    mem = psutil.virtual_memory()
    return mem.available / (1024**3), mem.total / (1024**3)


def calculate_embedding_batch_size(available_gb: float) -> int:
    """Calculate optimal embedding batch size based on available RAM.

    The pyannote diarization pipeline's embedding_batch_size parameter
    controls memory usage during speaker embedding extraction.
    Default is 32, which can use 10-14GB RAM for long audio.

    Args:
        available_gb: Available system memory in GB

    Returns:
        Recommended batch size (1, 8, 16, or 32)
    """
    # Conservative thresholds based on pyannote memory usage patterns
    # These leave headroom for other processes and spikes
    if available_gb < 4:
        return 1  # Minimum - ~0.5GB less RAM, often faster
    elif available_gb < 8:
        return 8  # Low memory mode
    elif available_gb < 12:
        return 16  # Moderate memory
    else:
        return 32  # Full speed (default)


# =============================================================================
# Memory-Aware Chunking Functions (v4.1.2)
# =============================================================================

# Memory model constants (empirical from pyannote testing)
DIARIZATION_BASE_MEMORY_GB = 2.0  # Models, overhead
DIARIZATION_PER_MINUTE_GB = 0.15  # O(n²) clustering overhead
MEMORY_SAFETY_FACTOR = 0.8  # Leave 20% headroom
MIN_CHUNK_MINUTES = 10.0  # Need context for speaker patterns
MAX_CHUNK_MINUTES = 30.0  # Reasonable memory ceiling
CHUNK_OVERLAP_SECONDS = 30.0  # Overlap for speaker continuity

# Alignment constants
# Segments shorter than this are too short for wav2vec2 alignment
# (produces zero emission frames → ZeroDivisionError in trellis)
MIN_SEGMENT_DURATION_FOR_ALIGNMENT = 0.1  # seconds


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in minutes without loading the full file.

    Uses ffprobe for efficient duration extraction.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in minutes

    Raises:
        DiarizationError: If duration cannot be determined
    """
    # Verify file exists first for clearer error messages
    if not audio_path.exists():
        raise DiarizationError(f"Audio file not found: {audio_path}")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration_seconds = float(result.stdout.strip())
        return duration_seconds / 60.0
    except subprocess.CalledProcessError as e:
        # Include stderr in error message for better debugging
        stderr_msg = e.stderr.strip() if e.stderr else "unknown error"
        raise DiarizationError(
            f"Failed to get audio duration for {audio_path.name}: {stderr_msg}"
        ) from e
    except (ValueError, FileNotFoundError) as e:
        raise DiarizationError(f"Failed to get audio duration: {e}") from e


def estimate_memory_required(duration_minutes: float) -> float:
    """Estimate GB of RAM needed for diarizing given duration.

    Based on empirical testing with pyannote's O(n²) clustering:
    - Base overhead: ~2 GB (models loaded)
    - Per-minute: ~0.15 GB (clustering matrix grows quadratically)

    Args:
        duration_minutes: Audio duration in minutes

    Returns:
        Estimated memory requirement in GB
    """
    return DIARIZATION_BASE_MEMORY_GB + (duration_minutes * DIARIZATION_PER_MINUTE_GB)


def calculate_chunk_duration(
    available_gb: float, audio_duration_minutes: float
) -> Tuple[float, bool]:
    """Determine optimal chunk size based on available memory.

    Returns full duration if memory allows, otherwise calculates
    the largest chunk size that fits in available memory.

    Args:
        available_gb: Available system memory in GB
        audio_duration_minutes: Total audio duration in minutes

    Returns:
        Tuple of (chunk_minutes, needs_chunking)
        - chunk_minutes: Duration per chunk (or full duration if no chunking)
        - needs_chunking: True if audio must be split into chunks
    """
    usable_memory = available_gb * MEMORY_SAFETY_FACTOR
    processable_minutes = (usable_memory - DIARIZATION_BASE_MEMORY_GB) / DIARIZATION_PER_MINUTE_GB

    # Can we process the whole file?
    if processable_minutes >= audio_duration_minutes:
        return audio_duration_minutes, False

    # Need to chunk - calculate optimal size within bounds
    chunk_minutes = max(MIN_CHUNK_MINUTES, min(MAX_CHUNK_MINUTES, processable_minutes))

    return chunk_minutes, True


def split_audio_into_chunks(
    audio_path: Path,
    chunk_duration_minutes: float,
    overlap_seconds: float = CHUNK_OVERLAP_SECONDS,
    output_dir: Optional[Path] = None,
) -> List[Tuple[Path, float, float]]:
    """Split audio into overlapping chunks using ffmpeg.

    Creates temporary chunk files for independent diarization.

    Args:
        audio_path: Path to source audio file
        chunk_duration_minutes: Duration of each chunk in minutes
        overlap_seconds: Overlap between chunks for speaker continuity
        output_dir: Directory for chunk files (default: same as source)

    Returns:
        List of (chunk_path, start_seconds, end_seconds) tuples

    Raises:
        DiarizationError: If splitting fails
    """
    if output_dir is None:
        output_dir = audio_path.parent

    total_duration_minutes = get_audio_duration(audio_path)
    total_duration_seconds = total_duration_minutes * 60
    chunk_duration_seconds = chunk_duration_minutes * 60

    chunks: List[Tuple[Path, float, float]] = []
    start_seconds = 0.0
    chunk_index = 0

    while start_seconds < total_duration_seconds:
        end_seconds = min(start_seconds + chunk_duration_seconds, total_duration_seconds)

        # Create chunk filename
        chunk_path = output_dir / f".chunk_{chunk_index:03d}_{audio_path.stem}.wav"

        # Use ffmpeg to extract chunk
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",  # Overwrite
                    "-i",
                    str(audio_path),
                    "-ss",
                    str(start_seconds),
                    "-t",
                    str(end_seconds - start_seconds),
                    "-ar",
                    "16000",  # 16kHz for diarization
                    "-ac",
                    "1",  # Mono
                    "-c:a",
                    "pcm_s16le",  # WAV format
                    str(chunk_path),
                ],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise DiarizationError(f"Failed to split audio chunk {chunk_index}: {e}") from e

        chunks.append((chunk_path, start_seconds, end_seconds))

        # Move to next chunk with overlap
        start_seconds = end_seconds - overlap_seconds
        chunk_index += 1

        # Safety: don't create tiny final chunks
        if total_duration_seconds - start_seconds < MIN_CHUNK_MINUTES * 60 * 0.5:
            break

    logger.info(
        "Split audio into chunks",
        num_chunks=len(chunks),
        chunk_duration_minutes=chunk_duration_minutes,
        overlap_seconds=overlap_seconds,
    )

    return chunks


def calculate_match_confidence(distance: float, threshold: float = 0.4) -> float:
    """Convert cosine distance to confidence percentage.

    Args:
        distance: Cosine distance (0 = identical, 2 = opposite)
        threshold: Distance threshold for matching

    Returns:
        Confidence as a float from 0.0 to 1.0
        - distance=0 -> 100% confidence
        - distance=threshold -> 60% confidence
        - distance>=threshold -> 50% confidence (low)
    """
    if distance >= threshold:
        return 0.5  # Below threshold = low confidence
    # Scale to 60-100% based on distance
    return 1.0 - (distance / threshold) * 0.4


def match_speakers_across_chunks(
    embeddings_prev: Dict[str, np.ndarray],
    embeddings_curr: Dict[str, np.ndarray],
    threshold: float = 0.4,
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Match speakers from current chunk to previous chunk.

    Uses cosine similarity of speaker embeddings to find the best match.
    Unmatched speakers get new IDs.

    Args:
        embeddings_prev: {speaker_id: embedding_vector} from previous chunk
        embeddings_curr: {speaker_id: embedding_vector} from current chunk
        threshold: Maximum cosine distance to consider a match (0.3-0.5 typical)

    Returns:
        Tuple of:
        - Mapping of {current_speaker: matched_or_new_speaker_id}
        - Distances dict {current_speaker: best_distance} for confidence scoring
    """
    if not embeddings_prev:
        # First chunk - no mapping needed
        return {spk: spk for spk in embeddings_curr}, {spk: 0.0 for spk in embeddings_curr}

    mapping: Dict[str, str] = {}
    distances: Dict[str, float] = {}
    used_prev_speakers: set = set()

    # Find max speaker ID from previous chunk for new speaker numbering
    max_id = 0
    for spk in embeddings_prev:
        try:
            num = int(spk.split("_")[-1])
            max_id = max(max_id, num)
        except (ValueError, IndexError):
            pass

    next_new_id = max_id + 1

    for spk_curr, emb_curr in embeddings_curr.items():
        best_match: Optional[str] = None
        best_distance = float("inf")

        for spk_prev, emb_prev in embeddings_prev.items():
            if spk_prev in used_prev_speakers:
                continue  # Already matched

            dist = cosine(emb_prev, emb_curr)
            if dist < best_distance:
                best_distance = dist
                best_match = spk_prev

        distances[spk_curr] = best_distance

        if best_distance < threshold and best_match is not None:
            mapping[spk_curr] = best_match
            used_prev_speakers.add(best_match)
            logger.debug(
                "Speaker matched",
                current=spk_curr,
                previous=best_match,
                distance=f"{best_distance:.3f}",
            )
        else:
            # New speaker
            new_id = f"SPEAKER_{next_new_id:02d}"
            mapping[spk_curr] = new_id
            next_new_id += 1
            logger.debug(
                "New speaker detected",
                current=spk_curr,
                assigned=new_id,
                best_distance=(f"{best_distance:.3f}" if best_distance != float("inf") else "N/A"),
            )

    return mapping, distances


def merge_chunk_segments(
    all_chunk_results: List[Dict[str, Any]],
    chunk_times: List[Tuple[float, float]],
    speaker_mappings: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Merge segments from all chunks with speaker re-mapping.

    Adjusts timestamps to absolute time and applies speaker mappings.
    Handles overlap regions by preferring earlier chunk's assignments.

    Args:
        all_chunk_results: List of diarization results from each chunk
        chunk_times: List of (start_seconds, end_seconds) for each chunk
        speaker_mappings: List of speaker mappings for each chunk

    Returns:
        Merged list of segments with absolute timestamps and consistent speaker IDs
    """
    merged_segments: List[Dict[str, Any]] = []
    prev_chunk_end = 0.0

    for chunk_idx, (result, (chunk_start, chunk_end), mapping) in enumerate(
        zip(all_chunk_results, chunk_times, speaker_mappings)
    ):
        segments = result.get("segments", [])

        for seg in segments:
            # Adjust timestamps to absolute time
            seg_start = seg.get("start", 0) + chunk_start
            seg_end = seg.get("end", 0) + chunk_start

            # Skip segments in overlap region that were already covered by previous chunk
            # The overlap region is [chunk_start, prev_chunk_end)
            if chunk_idx > 0 and seg_start < prev_chunk_end:
                continue

            # Create new segment with adjusted times and mapped speaker
            new_seg = seg.copy()
            new_seg["start"] = seg_start
            new_seg["end"] = seg_end

            # Map speaker ID if present
            if "speaker" in new_seg:
                new_seg["speaker"] = mapping.get(new_seg["speaker"], new_seg["speaker"])

            # Also map speakers in words
            if "words" in new_seg:
                new_words = []
                for word in new_seg["words"]:
                    new_word = word.copy()
                    new_word["start"] = word.get("start", 0) + chunk_start
                    new_word["end"] = word.get("end", 0) + chunk_start
                    if "speaker" in new_word:
                        new_word["speaker"] = mapping.get(new_word["speaker"], new_word["speaker"])
                    new_words.append(new_word)
                new_seg["words"] = new_words

            merged_segments.append(new_seg)

        # Track end of this chunk for overlap handling in next chunk
        prev_chunk_end = chunk_end

    logger.info(
        "Merged chunk segments",
        total_segments=len(merged_segments),
        num_chunks=len(all_chunk_results),
    )

    return merged_segments


def cleanup_chunk_files(chunks: List[Tuple[Path, float, float]]) -> None:
    """Remove temporary chunk files.

    Args:
        chunks: List of (chunk_path, start, end) tuples
    """
    for chunk_path, _, _ in chunks:
        try:
            if chunk_path.exists():
                chunk_path.unlink()
                logger.debug("Removed chunk file", path=str(chunk_path))
        except OSError as e:
            logger.warning("Failed to remove chunk file", path=str(chunk_path), error=str(e))


def sanitize_segments_for_alignment(
    segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filter and fix segments that could cause WhisperX alignment to fail.

    WhisperX alignment can crash with "float division by zero" when:
    - Segments have empty or whitespace-only text
    - Segments have zero or negative duration
    - Segments have missing start/end times
    - Segments contain pre-existing alignment data (words[], speaker)
      from a previous diarization run
    - Segments are too short for the wav2vec2 model to produce
      emission frames (< MIN_SEGMENT_DURATION_FOR_ALIGNMENT)

    Args:
        segments: List of transcript segments

    Returns:
        Sanitized list of segments safe for alignment, containing only
        the fields WhisperX expects (start, end, text)
    """
    sanitized = []
    removed_count = 0

    for seg in segments:
        text = seg.get("text", "").strip()
        start = seg.get("start")
        end = seg.get("end")

        # Skip segments with empty text
        if not text:
            removed_count += 1
            continue

        # Skip segments with missing timing
        if start is None or end is None:
            removed_count += 1
            continue

        # Skip segments with zero or negative duration
        if end <= start:
            removed_count += 1
            continue

        # Skip segments too short for alignment model.
        # wav2vec2 produces zero emission frames for very short segments,
        # causing ZeroDivisionError in trellis ratio calculation.
        duration = end - start
        if duration < MIN_SEGMENT_DURATION_FOR_ALIGNMENT:
            removed_count += 1
            continue

        # Only keep fields that WhisperX alignment expects.
        # Pre-existing words[] and speaker labels from previous diarization
        # cause "float division by zero" crashes during re-alignment.
        clean_seg = {
            "start": start,
            "end": end,
            "text": text,
        }
        sanitized.append(clean_seg)

    if removed_count > 0:
        logger.info(
            "Sanitized segments for alignment",
            removed=removed_count,
            remaining=len(sanitized),
        )

    return sanitized


class DiarizationError(Exception):
    """Raised when diarization fails."""

    pass


class DiarizationEngine:
    """Pure diarization logic with no UI dependencies.

    Uses WhisperX for two-step process:
    1. Alignment: Add word-level timing to transcript segments
    2. Diarization: Identify speakers and assign to words

    Can be used by CLI, web API, or any other interface.
    """

    def __init__(
        self,
        language: str = "en",
        device: Optional[str] = None,
        hf_token: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        num_speakers: Optional[int] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ):
        """Initialize diarization engine.

        Args:
            language: Language code for alignment model (e.g., 'en', 'es')
            device: Device to use (auto-detect if None: mps/cuda/cpu)
            hf_token: Hugging Face token for diarization pipeline (optional)
            progress_callback: Optional callback for progress updates
            num_speakers: Exact number of speakers (if known)
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
        """
        self.language = language
        # Auto-detect device if not specified (PyTorch supports MPS/CUDA/CPU)
        self.device = device if device is not None else detect_device_for_pytorch()
        self.hf_token = hf_token or os.getenv("HUGGINGFACE_TOKEN")
        self.progress_callback = progress_callback
        self.num_speakers = num_speakers
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

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

        Automatically uses chunked processing for long audio when memory is limited.

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

        # Check memory and audio duration to decide on chunking
        available_gb, total_gb = get_memory_info()
        audio_duration_minutes = get_audio_duration(audio_path)
        estimated_memory = estimate_memory_required(audio_duration_minutes)
        chunk_duration, needs_chunking = calculate_chunk_duration(
            available_gb, audio_duration_minutes
        )

        # Store chunking info for CLI display
        self._chunking_info = {
            "available_gb": available_gb,
            "total_gb": total_gb,
            "audio_duration_minutes": audio_duration_minutes,
            "estimated_memory_gb": estimated_memory,
            "needs_chunking": needs_chunking,
            "chunk_duration_minutes": chunk_duration if needs_chunking else None,
            "num_chunks": None,  # Set later if chunking
        }

        if needs_chunking:
            num_chunks = (
                int((audio_duration_minutes * 60) / (chunk_duration * 60 - CHUNK_OVERLAP_SECONDS))
                + 1
            )
            self._chunking_info["num_chunks"] = num_chunks

        logger.info(
            "Starting diarization",
            audio=str(audio_path),
            language=self.language,
            segments_count=len(transcript_segments),
            audio_duration_minutes=f"{audio_duration_minutes:.1f}",
            available_memory_gb=f"{available_gb:.1f}",
            estimated_memory_gb=f"{estimated_memory:.1f}",
            needs_chunking=needs_chunking,
        )

        # Log device usage for transparency
        log_device_usage(self.device, "N/A", "diarization")

        try:
            import whisperx
            from whisperx.diarize import assign_word_speakers
        except ImportError:
            raise DiarizationError("whisperx not installed. Install with: pip install whisperx")

        # Step 1: Alignment - add word-level timing (always done on full audio)
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

        # Sanitize segments to prevent alignment crashes (division by zero, etc.)
        clean_segments = sanitize_segments_for_alignment(transcript_segments)
        if not clean_segments:
            raise DiarizationError(
                "No valid segments after sanitization. "
                "Check that transcript has text with valid timing."
            )

        self._report_progress("Aligning transcript")
        try:
            aligned_result = whisperx.align(
                clean_segments,
                model_a,
                metadata,
                audio_data,
                device=self.device,
                return_char_alignments=False,
            )
        except Exception as e:
            raise DiarizationError(f"Alignment failed: {e}") from e

        logger.info(
            "Alignment completed",
            segments_count=len(aligned_result.get("segments", [])),
        )

        # Step 2: Diarization - branch based on chunking need
        if needs_chunking:
            final = self._diarize_chunked(
                audio_path, aligned_result, chunk_duration, assign_word_speakers
            )
        else:
            final = self._diarize_full(
                audio_path, aligned_result, available_gb, assign_word_speakers
            )

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
            chunked=needs_chunking,
        )

        return final

    def _diarize_full(
        self,
        audio_path: Path,
        aligned_result: Dict[str, Any],
        available_gb: float,
        assign_word_speakers: Callable,
    ) -> Dict[str, Any]:
        """Diarize full audio without chunking (original behavior)."""
        from whisperx.diarize import DiarizationPipeline

        batch_size = calculate_embedding_batch_size(available_gb)

        self._report_progress(f"Loading diarization model (batch={batch_size})")
        logger.info(
            "Memory-aware diarization (full)",
            embedding_batch_size=batch_size,
        )
        try:
            dia = DiarizationPipeline(use_auth_token=self.hf_token, device=self.device)
            if hasattr(dia.model, "embedding_batch_size"):
                dia.model.embedding_batch_size = batch_size
        except Exception as e:
            raise DiarizationError(f"Failed to load diarization model: {e}") from e

        self._report_progress("Identifying speakers")
        try:
            diarized = dia(
                str(audio_path),
                num_speakers=self.num_speakers,
                min_speakers=self.min_speakers,
                max_speakers=self.max_speakers,
            )
            return assign_word_speakers(diarized, aligned_result)
        except Exception as e:
            raise DiarizationError(f"Diarization failed: {e}") from e

    def _diarize_chunked(
        self,
        audio_path: Path,
        aligned_result: Dict[str, Any],
        chunk_duration_minutes: float,
        assign_word_speakers: Callable,
    ) -> Dict[str, Any]:
        """Diarize audio in chunks with speaker re-identification."""
        from whisperx.diarize import DiarizationPipeline

        # Split audio into chunks
        self._report_progress("Splitting audio into chunks")
        chunks = split_audio_into_chunks(audio_path, chunk_duration_minutes)

        try:
            # Initialize diarization pipeline once
            batch_size = calculate_embedding_batch_size(get_memory_info()[0])
            self._report_progress(f"Loading diarization model (batch={batch_size})")

            dia = DiarizationPipeline(use_auth_token=self.hf_token, device=self.device)
            if hasattr(dia.model, "embedding_batch_size"):
                dia.model.embedding_batch_size = batch_size

            all_chunk_results: List[Dict[str, Any]] = []
            chunk_times: List[Tuple[float, float]] = []
            speaker_mappings: List[Dict[str, str]] = []

            # Cumulative embedding storage for improved speaker matching
            # Key: global speaker ID, Value: list of embeddings from all chunks
            cumulative_embeddings: Dict[str, List[np.ndarray]] = {}
            cumulative_mapping: Dict[str, str] = {}

            # Store chunk info for verification workflow
            chunk_info: List[Dict[str, Any]] = []

            for chunk_idx, (chunk_path, start_sec, end_sec) in enumerate(chunks):
                self._report_progress(
                    f"Processing chunk {chunk_idx + 1}/{len(chunks)} "
                    f"({start_sec / 60:.0f}:{start_sec % 60:02.0f} - "
                    f"{end_sec / 60:.0f}:{end_sec % 60:02.0f})"
                )

                # Diarize this chunk with embeddings
                try:
                    diarized, embeddings = dia(
                        str(chunk_path),
                        num_speakers=self.num_speakers,
                        min_speakers=self.min_speakers,
                        max_speakers=self.max_speakers,
                        return_embeddings=True,
                    )
                except Exception as e:
                    raise DiarizationError(
                        f"Diarization failed on chunk {chunk_idx + 1}: {e}"
                    ) from e

                # Match speakers using cumulative embeddings (averaged across all chunks)
                chunk_confidence = 1.0  # First chunk has perfect confidence
                if embeddings:
                    if chunk_idx == 0:
                        # First chunk: establish baseline
                        chunk_mapping: Dict[str, str] = {spk: spk for spk in embeddings}
                        for spk, emb in embeddings.items():
                            cumulative_embeddings[spk] = [emb]
                            cumulative_mapping[spk] = spk
                    else:
                        # Compute averaged embeddings from all historical data
                        avg_embeddings = {
                            spk: np.mean(embs, axis=0)
                            for spk, embs in cumulative_embeddings.items()
                        }

                        # Match against averaged historical embeddings
                        chunk_mapping, distances = match_speakers_across_chunks(
                            avg_embeddings, embeddings
                        )

                        # Calculate overall confidence as average of match confidences
                        if distances:
                            confidences = [
                                calculate_match_confidence(d)
                                for d in distances.values()
                                if d != float("inf")
                            ]
                            chunk_confidence = (
                                sum(confidences) / len(confidences) if confidences else 0.5
                            )

                        # Update cumulative mapping for consistent IDs
                        for curr, mapped in list(chunk_mapping.items()):
                            if mapped in cumulative_mapping:
                                chunk_mapping[curr] = cumulative_mapping[mapped]
                            else:
                                cumulative_mapping[mapped] = mapped

                        # Accumulate new embeddings under global speaker IDs
                        for spk, emb in embeddings.items():
                            global_id = chunk_mapping[spk]
                            if global_id in cumulative_embeddings:
                                cumulative_embeddings[global_id].append(emb)
                            else:
                                cumulative_embeddings[global_id] = [emb]

                    matched_count = sum(1 for k, v in chunk_mapping.items() if k != v)
                    if matched_count > 0 and chunk_idx > 0:
                        logger.info(
                            f"Matched {matched_count} speakers "
                            f"(confidence: {chunk_confidence:.0%})"
                        )
                else:
                    chunk_mapping = {}

                # Get aligned segments for this chunk's time range
                chunk_aligned = self._get_aligned_segments_for_chunk(
                    aligned_result, start_sec, end_sec
                )

                # Assign speakers to words
                chunk_result = assign_word_speakers(diarized, chunk_aligned)

                all_chunk_results.append(chunk_result)
                chunk_times.append((start_sec, end_sec))
                speaker_mappings.append(chunk_mapping)

                # Store chunk info for verification workflow
                speakers_in_chunk = set()
                for seg in chunk_result.get("segments", []):
                    spk = seg.get("speaker")
                    if spk:
                        # Map to global ID
                        speakers_in_chunk.add(chunk_mapping.get(spk, spk))

                chunk_info.append(
                    {
                        "index": chunk_idx,
                        "start_time": start_sec,
                        "end_time": end_sec,
                        "confidence": chunk_confidence,
                        "speakers": list(speakers_in_chunk),
                        "mapping": chunk_mapping.copy(),
                    }
                )

            # Merge all chunks
            self._report_progress("Merging segments")
            merged_segments = merge_chunk_segments(all_chunk_results, chunk_times, speaker_mappings)

            # Store chunk info for CLI access
            self._chunk_info = chunk_info

            return {"segments": merged_segments}

        finally:
            # Clean up chunk files
            cleanup_chunk_files(chunks)

    def _get_aligned_segments_for_chunk(
        self,
        aligned_result: Dict[str, Any],
        start_sec: float,
        end_sec: float,
    ) -> Dict[str, Any]:
        """Extract aligned segments that fall within the chunk's time range."""
        chunk_segments = []
        for seg in aligned_result.get("segments", []):
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)

            # Check if segment overlaps with chunk
            if seg_end > start_sec and seg_start < end_sec:
                # Adjust segment to be relative to chunk start
                adjusted_seg = seg.copy()
                adjusted_seg["start"] = max(0, seg_start - start_sec)
                adjusted_seg["end"] = seg_end - start_sec

                # Also adjust words
                if "words" in adjusted_seg:
                    adjusted_words = []
                    for word in adjusted_seg["words"]:
                        adj_word = word.copy()
                        adj_word["start"] = max(0, word.get("start", 0) - start_sec)
                        adj_word["end"] = word.get("end", 0) - start_sec
                        adjusted_words.append(adj_word)
                    adjusted_seg["words"] = adjusted_words

                chunk_segments.append(adjusted_seg)

        return {"segments": chunk_segments}


# Convenience function for direct use
def diarize_transcript(
    audio_path: Path,
    transcript_segments: List[Dict[str, Any]],
    language: str = "en",
    device: Optional[str] = None,
    hf_token: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
) -> Dict[str, Any]:
    """Diarize transcript with speaker identification.

    Args:
        audio_path: Path to audio file
        transcript_segments: List of transcript segments
        language: Language code for alignment
        device: Device to use (auto-detect if None: mps/cuda/cpu)
        hf_token: Hugging Face token (optional)
        progress_callback: Optional progress callback
        num_speakers: Exact number of speakers (if known)
        min_speakers: Minimum number of speakers
        max_speakers: Maximum number of speakers

    Returns:
        Diarized transcript dictionary
    """
    engine = DiarizationEngine(
        language=language,
        device=device,
        hf_token=hf_token,
        progress_callback=progress_callback,
        num_speakers=num_speakers,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )
    return engine.diarize(audio_path, transcript_segments)
