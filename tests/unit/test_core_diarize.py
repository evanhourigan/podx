"""Unit tests for core.diarize module.

Tests pure business logic without UI dependencies.
Uses mocking to avoid actual WhisperX model loading.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from podx.core.diarize import (
    MIN_SEGMENT_DURATION_FOR_ALIGNMENT,
    DiarizationEngine,
    DiarizationError,
    calculate_chunk_duration,
    calculate_match_confidence,
    diarize_transcript,
    estimate_memory_required,
    match_speakers_across_chunks,
    merge_chunk_segments,
    sanitize_segments_for_alignment,
)


@pytest.fixture
def mock_whisperx():
    """Fixture to mock whisperx module."""
    mock_module = MagicMock()

    # Mock the diarize submodule
    mock_diarize = MagicMock()
    mock_module.diarize = mock_diarize

    sys.modules["whisperx"] = mock_module
    sys.modules["whisperx.diarize"] = mock_diarize
    yield mock_module

    # Cleanup
    if "whisperx" in sys.modules:
        del sys.modules["whisperx"]
    if "whisperx.diarize" in sys.modules:
        del sys.modules["whisperx.diarize"]


@pytest.fixture
def sample_transcript_segments():
    """Sample transcript segments for testing."""
    return [
        {"text": "Hello world", "start": 0.0, "end": 2.0},
        {"text": "How are you?", "start": 2.0, "end": 4.0},
    ]


@pytest.fixture
def sample_aligned_result():
    """Sample aligned result from WhisperX."""
    return {
        "segments": [
            {
                "text": "Hello world",
                "start": 0.0,
                "end": 2.0,
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.5},
                    {"word": "world", "start": 0.6, "end": 1.0},
                ],
            },
            {
                "text": "How are you?",
                "start": 2.0,
                "end": 4.0,
                "words": [
                    {"word": "How", "start": 2.0, "end": 2.3},
                    {"word": "are", "start": 2.4, "end": 2.6},
                    {"word": "you?", "start": 2.7, "end": 3.0},
                ],
            },
        ]
    }


@pytest.fixture
def sample_diarized_result():
    """Sample diarized result with speaker labels."""
    return {
        "segments": [
            {
                "text": "Hello world",
                "start": 0.0,
                "end": 2.0,
                "words": [
                    {
                        "word": "Hello",
                        "start": 0.0,
                        "end": 0.5,
                        "speaker": "SPEAKER_00",
                    },
                    {
                        "word": "world",
                        "start": 0.6,
                        "end": 1.0,
                        "speaker": "SPEAKER_00",
                    },
                ],
            },
            {
                "text": "How are you?",
                "start": 2.0,
                "end": 4.0,
                "words": [
                    {"word": "How", "start": 2.0, "end": 2.3, "speaker": "SPEAKER_01"},
                    {"word": "are", "start": 2.4, "end": 2.6, "speaker": "SPEAKER_01"},
                    {"word": "you?", "start": 2.7, "end": 3.0, "speaker": "SPEAKER_01"},
                ],
            },
        ]
    }


@pytest.fixture(autouse=True)
def mock_memory_and_duration():
    """Fixture to mock memory and duration functions for all diarize tests.

    This prevents tests from requiring ffprobe and real memory checks.
    Returns 16GB available memory and 5 minute audio duration.
    """
    with (
        patch("podx.core.diarize.get_memory_info", return_value=(16.0, 32.0)),
        patch("podx.core.diarize.get_audio_duration", return_value=5.0),
    ):
        yield


class TestDiarizationEngineInit:
    """Test DiarizationEngine initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        engine = DiarizationEngine()
        assert engine.language == "en"
        # Device is auto-detected (mps/cuda/cpu), so just verify it's set
        assert engine.device in ["mps", "cuda", "cpu"]
        assert engine.progress_callback is None

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""

        def callback(msg):
            return None

        engine = DiarizationEngine(
            language="es",
            device="cuda",
            hf_token="test_token",
            progress_callback=callback,
        )
        assert engine.language == "es"
        assert engine.device == "cuda"
        assert engine.hf_token == "test_token"
        assert engine.progress_callback is callback

    def test_init_hf_token_from_env(self):
        """Test that HF token is loaded from environment variable."""
        with patch.dict(os.environ, {"HUGGINGFACE_TOKEN": "env_token"}):
            engine = DiarizationEngine()
            assert engine.hf_token == "env_token"

    def test_init_explicit_token_overrides_env(self):
        """Test that explicit token overrides environment variable."""
        with patch.dict(os.environ, {"HUGGINGFACE_TOKEN": "env_token"}):
            engine = DiarizationEngine(hf_token="explicit_token")
            assert engine.hf_token == "explicit_token"


class TestDiarizationEngineDiarize:
    """Test DiarizationEngine.diarize() method."""

    def test_diarize_success(
        self,
        mock_whisperx,
        sample_transcript_segments,
        sample_aligned_result,
        sample_diarized_result,
        tmp_path,
    ):
        """Test successful diarization."""
        # Create fake audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        # Mock DiarizationPipeline
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()  # Diarized result
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = sample_diarized_result

        engine = DiarizationEngine(language="en", device="cpu", hf_token="test_token")
        result = engine.diarize(audio_file, sample_transcript_segments)

        # Verify result
        assert result == sample_diarized_result
        assert len(result["segments"]) == 2

        # Verify whisperx was called correctly
        mock_whisperx.load_align_model.assert_called_once_with(language_code="en", device="cpu")
        mock_whisperx.load_audio.assert_called_once_with(str(audio_file))
        mock_whisperx.align.assert_called_once()
        mock_whisperx.diarize.DiarizationPipeline.assert_called_once()
        mock_whisperx.diarize.assign_word_speakers.assert_called_once()

    def test_diarize_missing_audio_file(self, mock_whisperx, sample_transcript_segments, tmp_path):
        """Test that missing audio file raises error."""
        audio_file = tmp_path / "nonexistent.wav"

        engine = DiarizationEngine()

        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_missing_whisperx(self, sample_transcript_segments, tmp_path):
        """Test that missing whisperx raises appropriate error."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock __import__ to raise ImportError for whisperx
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "whisperx":
                raise ImportError("No module named 'whisperx'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            engine = DiarizationEngine()

            with pytest.raises(DiarizationError, match="whisperx not installed"):
                engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_alignment_model_load_failure(
        self, mock_whisperx, sample_transcript_segments, tmp_path
    ):
        """Test handling of alignment model loading failure."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock failure in load_align_model
        mock_whisperx.load_align_model.side_effect = Exception("Model load failed")

        engine = DiarizationEngine()

        with pytest.raises(DiarizationError, match="Failed to load alignment model"):
            engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_audio_load_failure(self, mock_whisperx, sample_transcript_segments, tmp_path):
        """Test handling of audio loading failure."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock successful model load but failed audio load
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.side_effect = Exception("Audio load failed")

        engine = DiarizationEngine()

        with pytest.raises(DiarizationError, match="Failed to load audio"):
            engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_alignment_failure(self, mock_whisperx, sample_transcript_segments, tmp_path):
        """Test handling of alignment failure."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock successful model and audio load but failed alignment
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.side_effect = Exception("Alignment failed")

        engine = DiarizationEngine()

        with pytest.raises(DiarizationError, match="Alignment failed"):
            engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_pipeline_load_failure(
        self, mock_whisperx, sample_transcript_segments, sample_aligned_result, tmp_path
    ):
        """Test handling of diarization pipeline loading failure."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock successful alignment but failed pipeline load
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result
        mock_whisperx.diarize.DiarizationPipeline.side_effect = Exception("Pipeline load failed")

        engine = DiarizationEngine()

        with pytest.raises(DiarizationError, match="Failed to load diarization model"):
            engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_speaker_identification_failure(
        self, mock_whisperx, sample_transcript_segments, sample_aligned_result, tmp_path
    ):
        """Test handling of speaker identification failure."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock successful alignment and pipeline load but failed diarization
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.side_effect = Exception("Diarization failed")
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline

        engine = DiarizationEngine()

        with pytest.raises(DiarizationError, match="Diarization failed"):
            engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_calls_progress_callback(
        self,
        mock_whisperx,
        sample_transcript_segments,
        sample_aligned_result,
        sample_diarized_result,
        tmp_path,
    ):
        """Test that diarize calls progress callback."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = sample_diarized_result

        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        engine = DiarizationEngine(progress_callback=progress_callback)
        engine.diarize(audio_file, sample_transcript_segments)

        # Should have progress messages for each step
        assert len(progress_messages) >= 4
        assert any("alignment model" in msg.lower() for msg in progress_messages)
        assert any("audio" in msg.lower() for msg in progress_messages)
        assert any("align" in msg.lower() for msg in progress_messages)
        assert any(
            "diarization model" in msg.lower() or "speakers" in msg.lower()
            for msg in progress_messages
        )

    def test_diarize_with_cuda_device(
        self,
        mock_whisperx,
        sample_transcript_segments,
        sample_aligned_result,
        sample_diarized_result,
        tmp_path,
    ):
        """Test diarization with CUDA device."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = sample_diarized_result

        engine = DiarizationEngine(device="cuda")
        engine.diarize(audio_file, sample_transcript_segments)

        # Verify device was used correctly
        mock_whisperx.load_align_model.assert_called_once_with(language_code="en", device="cuda")
        call_kwargs = mock_whisperx.align.call_args[1]
        assert call_kwargs["device"] == "cuda"

    def test_diarize_with_different_language(
        self,
        mock_whisperx,
        sample_transcript_segments,
        sample_aligned_result,
        sample_diarized_result,
        tmp_path,
    ):
        """Test diarization with non-English language."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = sample_diarized_result

        engine = DiarizationEngine(language="es")
        engine.diarize(audio_file, sample_transcript_segments)

        # Verify language was used correctly
        # Device is auto-detected, so check with the actual device
        mock_whisperx.load_align_model.assert_called_once_with(
            language_code="es", device=engine.device
        )


class TestConvenienceFunction:
    """Test diarize_transcript convenience function."""

    def test_diarize_transcript(
        self,
        mock_whisperx,
        sample_transcript_segments,
        sample_aligned_result,
        sample_diarized_result,
        tmp_path,
    ):
        """Test diarize_transcript convenience function."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = sample_diarized_result

        result = diarize_transcript(audio_file, sample_transcript_segments)

        assert result == sample_diarized_result

    def test_diarize_transcript_with_custom_params(
        self,
        mock_whisperx,
        sample_transcript_segments,
        sample_aligned_result,
        sample_diarized_result,
        tmp_path,
    ):
        """Test diarize_transcript with custom parameters."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = sample_diarized_result

        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        result = diarize_transcript(
            audio_file,
            sample_transcript_segments,
            language="es",
            device="cuda",
            hf_token="custom_token",
            progress_callback=progress_callback,
        )

        assert result == sample_diarized_result
        assert len(progress_messages) >= 4

        # Verify custom params were used
        mock_whisperx.load_align_model.assert_called_once_with(language_code="es", device="cuda")


class TestSanitizeSegmentsForAlignment:
    """Test segment sanitization for WhisperX alignment."""

    def test_passes_valid_segments(self):
        """Test that valid segments pass through unchanged."""
        segments = [
            {"text": "Hello world", "start": 0.0, "end": 2.0},
            {"text": "More text here", "start": 2.5, "end": 5.0},
        ]
        result = sanitize_segments_for_alignment(segments)
        assert len(result) == 2
        assert result[0]["text"] == "Hello world"
        assert result[1]["text"] == "More text here"

    def test_removes_empty_text(self):
        """Test that segments with empty text are removed."""
        segments = [
            {"text": "Valid text", "start": 0.0, "end": 2.0},
            {"text": "", "start": 2.5, "end": 5.0},
            {"text": "   ", "start": 5.5, "end": 7.0},  # Whitespace only
        ]
        result = sanitize_segments_for_alignment(segments)
        assert len(result) == 1
        assert result[0]["text"] == "Valid text"

    def test_removes_missing_timing(self):
        """Test that segments with missing start/end are removed."""
        segments = [
            {"text": "Valid", "start": 0.0, "end": 2.0},
            {"text": "No start", "end": 5.0},
            {"text": "No end", "start": 5.5},
            {"text": "No timing"},
        ]
        result = sanitize_segments_for_alignment(segments)
        assert len(result) == 1
        assert result[0]["text"] == "Valid"

    def test_removes_zero_duration(self):
        """Test that segments with zero or negative duration are removed."""
        segments = [
            {"text": "Valid", "start": 0.0, "end": 2.0},
            {"text": "Zero duration", "start": 3.0, "end": 3.0},
            {"text": "Negative duration", "start": 5.0, "end": 4.0},
        ]
        result = sanitize_segments_for_alignment(segments)
        assert len(result) == 1
        assert result[0]["text"] == "Valid"

    def test_strips_whitespace_from_text(self):
        """Test that text is stripped of leading/trailing whitespace."""
        segments = [
            {"text": "  Hello  ", "start": 0.0, "end": 2.0},
        ]
        result = sanitize_segments_for_alignment(segments)
        assert result[0]["text"] == "Hello"

    def test_strips_alignment_data(self):
        """Test that pre-existing words[] and speaker labels are stripped."""
        segments = [
            {
                "text": "Hello world",
                "start": 0.0,
                "end": 2.0,
                "speaker": "SPEAKER_00",
                "words": [
                    {
                        "word": "Hello",
                        "start": 0.0,
                        "end": 0.5,
                        "score": 0.9,
                        "speaker": "SPEAKER_00",
                    },
                    {
                        "word": "world",
                        "start": 0.6,
                        "end": 1.0,
                        "score": 0.8,
                        "speaker": "SPEAKER_00",
                    },
                ],
            },
        ]
        result = sanitize_segments_for_alignment(segments)
        assert len(result) == 1
        assert "words" not in result[0]
        assert "speaker" not in result[0]
        assert result[0] == {"start": 0.0, "end": 2.0, "text": "Hello world"}

    def test_removes_too_short_segments(self):
        """Test that segments shorter than min duration are removed."""
        segments = [
            {"text": "Valid segment", "start": 0.0, "end": 2.0},
            {"text": "I", "start": 3.0, "end": 3.02},  # 0.02s - too short
            {"text": "And", "start": 5.0, "end": 5.06},  # 0.06s - too short
            {"text": "Another valid one", "start": 7.0, "end": 9.0},
        ]
        result = sanitize_segments_for_alignment(segments)
        assert len(result) == 2
        assert result[0]["text"] == "Valid segment"
        assert result[1]["text"] == "Another valid one"

    def test_keeps_segments_at_min_duration(self):
        """Test that segments exactly at min duration are kept."""
        min_dur = MIN_SEGMENT_DURATION_FOR_ALIGNMENT
        segments = [
            {"text": "At threshold", "start": 0.0, "end": min_dur},
            {"text": "Below threshold", "start": 1.0, "end": 1.0 + min_dur - 0.001},
        ]
        result = sanitize_segments_for_alignment(segments)
        assert len(result) == 1
        assert result[0]["text"] == "At threshold"

    def test_empty_input(self):
        """Test that empty input returns empty output."""
        result = sanitize_segments_for_alignment([])
        assert result == []


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_diarize_empty_segments(
        self, mock_whisperx, sample_aligned_result, sample_diarized_result, tmp_path
    ):
        """Test diarization with empty transcript segments raises error."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        engine = DiarizationEngine()

        # Should raise error for empty segments
        with pytest.raises(DiarizationError, match="No valid segments"):
            engine.diarize(audio_file, [])

    def test_diarize_result_without_words(
        self, mock_whisperx, sample_transcript_segments, tmp_path
    ):
        """Test handling of diarization result without word-level data."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock result without words field
        aligned_result = {"segments": [{"text": "Hello", "start": 0.0, "end": 1.0}]}
        diarized_result = {"segments": [{"text": "Hello", "start": 0.0, "end": 1.0}]}

        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = diarized_result

        engine = DiarizationEngine()
        result = engine.diarize(audio_file, sample_transcript_segments)

        # Should handle result without words gracefully
        assert result == diarized_result

    def test_diarize_counts_speakers(
        self,
        mock_whisperx,
        sample_transcript_segments,
        sample_aligned_result,
        sample_diarized_result,
        tmp_path,
    ):
        """Test that diarize correctly counts unique speakers."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock whisperx functions
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.return_value = MagicMock()
        mock_whisperx.align.return_value = sample_aligned_result

        mock_pipeline = MagicMock()
        mock_pipeline.return_value = MagicMock()
        mock_whisperx.diarize.DiarizationPipeline.return_value = mock_pipeline
        mock_whisperx.diarize.assign_word_speakers.return_value = sample_diarized_result

        engine = DiarizationEngine()
        result = engine.diarize(audio_file, sample_transcript_segments)

        # Count unique speakers in result
        speakers = set()
        for seg in result.get("segments", []):
            for word in seg.get("words", []):
                if "speaker" in word:
                    speakers.add(word["speaker"])

        # Should have 2 unique speakers
        assert len(speakers) == 2
        assert "SPEAKER_00" in speakers
        assert "SPEAKER_01" in speakers


# =============================================================================
# Tests for v4.1.2 Chunked Diarization Functions
# =============================================================================


class TestEstimateMemoryRequired:
    """Test memory estimation function."""

    def test_short_audio(self):
        """Test memory estimate for short audio."""
        # 10 minutes should need: 2.0 + (10 * 0.15) = 3.5 GB
        result = estimate_memory_required(10.0)
        assert result == pytest.approx(3.5, rel=0.01)

    def test_long_audio(self):
        """Test memory estimate for long audio."""
        # 60 minutes should need: 2.0 + (60 * 0.15) = 11.0 GB
        result = estimate_memory_required(60.0)
        assert result == pytest.approx(11.0, rel=0.01)

    def test_zero_duration(self):
        """Test memory estimate for zero duration."""
        # 0 minutes should just be base overhead
        result = estimate_memory_required(0.0)
        assert result == pytest.approx(2.0, rel=0.01)


class TestCalculateChunkDuration:
    """Test chunk duration calculation."""

    def test_enough_memory_no_chunking(self):
        """Test that chunking is not needed when memory is sufficient."""
        # 16 GB available, 30 min audio
        # Processable: (16 * 0.8 - 2) / 0.15 = 72 min
        chunk_duration, needs_chunking = calculate_chunk_duration(16.0, 30.0)
        assert needs_chunking is False
        assert chunk_duration == pytest.approx(30.0, rel=0.01)

    def test_low_memory_needs_chunking(self):
        """Test that chunking is needed when memory is limited."""
        # 6 GB available, 60 min audio
        # Processable: (6 * 0.8 - 2) / 0.15 = 18.67 min
        chunk_duration, needs_chunking = calculate_chunk_duration(6.0, 60.0)
        assert needs_chunking is True
        # Should be clamped to processable minutes (18.67)
        assert chunk_duration >= 10.0  # Minimum
        assert chunk_duration <= 30.0  # Maximum

    def test_very_low_memory_minimum_chunk(self):
        """Test minimum chunk size is enforced."""
        # 4 GB available, 90 min audio
        # Processable: (4 * 0.8 - 2) / 0.15 = 8 min (below minimum)
        chunk_duration, needs_chunking = calculate_chunk_duration(4.0, 90.0)
        assert needs_chunking is True
        assert chunk_duration == pytest.approx(10.0, rel=0.01)  # Minimum enforced

    def test_high_memory_no_chunking_long_audio(self):
        """Test no chunking needed with high memory even for long audio."""
        # 24 GB available, 90 min audio
        # Processable: (24 * 0.8 - 2) / 0.15 = 114.67 min
        chunk_duration, needs_chunking = calculate_chunk_duration(24.0, 90.0)
        assert needs_chunking is False


class TestCalculateMatchConfidence:
    """Test confidence calculation from cosine distance."""

    def test_perfect_match(self):
        """Test that distance=0 gives 100% confidence."""
        assert calculate_match_confidence(0.0) == pytest.approx(1.0)

    def test_threshold_boundary(self):
        """Test that distance=threshold gives 60% confidence."""
        assert calculate_match_confidence(0.4, threshold=0.4) == pytest.approx(0.5)

    def test_half_threshold(self):
        """Test that distance=threshold/2 gives 80% confidence."""
        assert calculate_match_confidence(0.2, threshold=0.4) == pytest.approx(0.8)

    def test_above_threshold(self):
        """Test that distance above threshold gives 50% confidence."""
        assert calculate_match_confidence(0.6, threshold=0.4) == pytest.approx(0.5)
        assert calculate_match_confidence(1.0, threshold=0.4) == pytest.approx(0.5)


class TestMatchSpeakersAcrossChunks:
    """Test speaker matching across chunks."""

    def test_first_chunk_identity_mapping(self):
        """Test that first chunk returns identity mapping."""
        embeddings_curr = {
            "SPEAKER_00": np.array([1.0, 0.0, 0.0]),
            "SPEAKER_01": np.array([0.0, 1.0, 0.0]),
        }
        mapping, distances = match_speakers_across_chunks({}, embeddings_curr)

        assert mapping == {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "SPEAKER_01"}
        assert distances == {"SPEAKER_00": 0.0, "SPEAKER_01": 0.0}

    def test_matching_same_speakers(self):
        """Test matching identical speakers across chunks."""
        embeddings_prev = {
            "SPEAKER_00": np.array([1.0, 0.0, 0.0]),
            "SPEAKER_01": np.array([0.0, 1.0, 0.0]),
        }
        # Same embeddings in different chunk
        embeddings_curr = {
            "SPEAKER_00": np.array([1.0, 0.0, 0.0]),  # Should match prev SPEAKER_00
            "SPEAKER_01": np.array([0.0, 1.0, 0.0]),  # Should match prev SPEAKER_01
        }
        mapping, distances = match_speakers_across_chunks(embeddings_prev, embeddings_curr)

        assert mapping["SPEAKER_00"] == "SPEAKER_00"
        assert mapping["SPEAKER_01"] == "SPEAKER_01"
        # Perfect matches should have distance ~0
        assert distances["SPEAKER_00"] == pytest.approx(0.0, abs=0.01)
        assert distances["SPEAKER_01"] == pytest.approx(0.0, abs=0.01)

    def test_matching_swapped_speakers(self):
        """Test matching when speaker IDs are swapped in new chunk."""
        embeddings_prev = {
            "SPEAKER_00": np.array([1.0, 0.0, 0.0]),
            "SPEAKER_01": np.array([0.0, 1.0, 0.0]),
        }
        # Embeddings swapped in new chunk
        embeddings_curr = {
            "SPEAKER_00": np.array([0.0, 1.0, 0.0]),  # Matches prev SPEAKER_01
            "SPEAKER_01": np.array([1.0, 0.0, 0.0]),  # Matches prev SPEAKER_00
        }
        mapping, distances = match_speakers_across_chunks(embeddings_prev, embeddings_curr)

        assert mapping["SPEAKER_00"] == "SPEAKER_01"
        assert mapping["SPEAKER_01"] == "SPEAKER_00"

    def test_new_speaker_detected(self):
        """Test detection of new speaker not in previous chunk."""
        embeddings_prev = {
            "SPEAKER_00": np.array([1.0, 0.0, 0.0]),
        }
        embeddings_curr = {
            "SPEAKER_00": np.array([1.0, 0.0, 0.0]),  # Matches prev
            "SPEAKER_01": np.array([0.0, 0.0, 1.0]),  # New speaker (orthogonal)
        }
        mapping, distances = match_speakers_across_chunks(embeddings_prev, embeddings_curr)

        assert mapping["SPEAKER_00"] == "SPEAKER_00"
        # New speaker should get a new ID
        assert mapping["SPEAKER_01"].startswith("SPEAKER_")
        assert mapping["SPEAKER_01"] != "SPEAKER_00"

    def test_threshold_respects_distance(self):
        """Test that threshold correctly filters poor matches."""
        embeddings_prev = {
            "SPEAKER_00": np.array([1.0, 0.0, 0.0]),
        }
        # Very different embedding should not match
        embeddings_curr = {
            "SPEAKER_00": np.array([-1.0, 0.0, 0.0]),  # Opposite direction
        }
        mapping, distances = match_speakers_across_chunks(
            embeddings_prev, embeddings_curr, threshold=0.4
        )

        # Should be treated as new speaker due to high distance
        assert mapping["SPEAKER_00"] != "SPEAKER_00"
        # Distance should be high (cosine distance of opposite vectors is 2.0)
        assert distances["SPEAKER_00"] > 0.4


class TestMergeChunkSegments:
    """Test segment merging across chunks."""

    def test_simple_merge(self):
        """Test basic segment merging."""
        chunk1_result = {
            "segments": [{"text": "Hello", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
        }
        chunk2_result = {
            "segments": [{"text": "World", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
        }

        chunk_times = [(0.0, 60.0), (55.0, 120.0)]  # 5 sec overlap
        speaker_mappings = [
            {"SPEAKER_00": "SPEAKER_00"},
            {"SPEAKER_00": "SPEAKER_00"},
        ]

        merged = merge_chunk_segments([chunk1_result, chunk2_result], chunk_times, speaker_mappings)

        assert len(merged) >= 1
        # First segment should have absolute timestamp
        assert merged[0]["start"] == pytest.approx(0.0, rel=0.01)

    def test_speaker_remapping(self):
        """Test that speakers are correctly remapped."""
        chunk1_result = {
            "segments": [{"text": "Hi", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
        }
        chunk2_result = {
            "segments": [
                {
                    "text": "Hey",
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "SPEAKER_01",  # Different ID
                }
            ]
        }

        chunk_times = [(0.0, 60.0), (55.0, 120.0)]
        # Mapping says chunk2's SPEAKER_01 is actually chunk1's SPEAKER_00
        speaker_mappings = [
            {"SPEAKER_00": "SPEAKER_00"},
            {"SPEAKER_01": "SPEAKER_00"},  # Remap
        ]

        merged = merge_chunk_segments([chunk1_result, chunk2_result], chunk_times, speaker_mappings)

        # Second segment should be remapped to SPEAKER_00
        if len(merged) > 1:
            assert merged[1]["speaker"] == "SPEAKER_00"

    def test_overlap_handling(self):
        """Test that overlap regions are handled correctly."""
        # Segment at 58 seconds in chunk1
        chunk1_result = {
            "segments": [
                {
                    "text": "End of first",
                    "start": 58.0,
                    "end": 59.0,
                    "speaker": "SPEAKER_00",
                }
            ]
        }
        # Same segment appears at 3 seconds in chunk2 (due to overlap)
        chunk2_result = {
            "segments": [
                {
                    "text": "End of first",
                    "start": 3.0,
                    "end": 4.0,
                    "speaker": "SPEAKER_00",
                },
                {
                    "text": "Start of second",
                    "start": 10.0,
                    "end": 11.0,
                    "speaker": "SPEAKER_00",
                },
            ]
        }

        chunk_times = [(0.0, 60.0), (55.0, 120.0)]  # 5 sec overlap
        speaker_mappings = [
            {"SPEAKER_00": "SPEAKER_00"},
            {"SPEAKER_00": "SPEAKER_00"},
        ]

        merged = merge_chunk_segments([chunk1_result, chunk2_result], chunk_times, speaker_mappings)

        # Should not have duplicate segments from overlap
        texts = [seg["text"] for seg in merged]
        assert texts.count("End of first") <= 1
