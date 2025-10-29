"""Unit tests for core.diarize module.

Tests pure business logic without UI dependencies.
Uses mocking to avoid actual WhisperX model loading.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from podx.core.diarize import (
    DiarizationEngine,
    DiarizationError,
    diarize_transcript,
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
                    {"word": "Hello", "start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"},
                    {"word": "world", "start": 0.6, "end": 1.0, "speaker": "SPEAKER_00"},
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


class TestDiarizationEngineInit:
    """Test DiarizationEngine initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        engine = DiarizationEngine()
        assert engine.language == "en"
        assert engine.device == "cpu"
        assert engine.progress_callback is None

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        def callback(msg):
            return None
        engine = DiarizationEngine(
            language="es", device="cuda", hf_token="test_token", progress_callback=callback
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
        mock_whisperx.load_align_model.assert_called_once_with(
            language_code="en", device="cpu"
        )
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

    def test_diarize_audio_load_failure(
        self, mock_whisperx, sample_transcript_segments, tmp_path
    ):
        """Test handling of audio loading failure."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        # Mock successful model load but failed audio load
        mock_whisperx.load_align_model.return_value = (MagicMock(), MagicMock())
        mock_whisperx.load_audio.side_effect = Exception("Audio load failed")

        engine = DiarizationEngine()

        with pytest.raises(DiarizationError, match="Failed to load audio"):
            engine.diarize(audio_file, sample_transcript_segments)

    def test_diarize_alignment_failure(
        self, mock_whisperx, sample_transcript_segments, tmp_path
    ):
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
        assert any("diarization model" in msg.lower() or "speakers" in msg.lower() for msg in progress_messages)

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
        mock_whisperx.load_align_model.assert_called_once_with(
            language_code="en", device="cuda"
        )
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
        mock_whisperx.load_align_model.assert_called_once_with(
            language_code="es", device="cpu"
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
        mock_whisperx.load_align_model.assert_called_once_with(
            language_code="es", device="cuda"
        )


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_diarize_empty_segments(
        self, mock_whisperx, sample_aligned_result, sample_diarized_result, tmp_path
    ):
        """Test diarization with empty transcript segments."""
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
        result = engine.diarize(audio_file, [])

        # Should still work with empty segments
        assert result == sample_diarized_result

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
