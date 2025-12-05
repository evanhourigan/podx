"""Unit tests for core.preprocess module.

Tests pure business logic without UI dependencies.
Uses mocking to avoid actual LLM API calls.
"""

from unittest import mock

import pytest

from podx.core.preprocess import (
    TranscriptPreprocessor,
    merge_segments,
    normalize_segments,
    normalize_text,
    preprocess_transcript,
)


class TestTranscriptPreprocessor:
    """Test TranscriptPreprocessor class."""

    def test_init_defaults(self):
        """Test default initialization."""
        preprocessor = TranscriptPreprocessor()
        assert preprocessor.merge is False
        assert preprocessor.normalize is False
        assert preprocessor.restore is False
        assert preprocessor.max_gap == 1.0
        assert preprocessor.max_len == 800
        assert preprocessor.restore_model == "gpt-4o-mini"
        assert preprocessor.restore_batch_size == 20

    @mock.patch("podx.core.preprocess.get_provider")
    def test_init_custom_options(self, mock_get_provider):
        """Test initialization with custom options."""
        # Mock the LLM provider to avoid needing API keys
        mock_get_provider.return_value = mock.Mock()

        preprocessor = TranscriptPreprocessor(
            merge=True,
            normalize=True,
            restore=True,
            max_gap=2.0,
            max_len=1000,
            restore_model="gpt-4",
            restore_batch_size=10,
        )
        assert preprocessor.merge is True
        assert preprocessor.normalize is True
        assert preprocessor.restore is True
        assert preprocessor.max_gap == 2.0
        assert preprocessor.max_len == 1000
        assert preprocessor.restore_model == "gpt-4"
        assert preprocessor.restore_batch_size == 10

    def test_merge_segments_basic(self):
        """Test basic segment merging."""
        segments = [
            {"text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "world", "start": 1.5, "end": 2.5},
            {"text": "today", "start": 2.8, "end": 3.8},
        ]

        preprocessor = TranscriptPreprocessor(merge=True, max_gap=1.0)
        result = preprocessor.merge_segments(segments)

        # All three merge because gaps < 1.0 and total length < 800
        assert len(result) == 1
        assert result[0]["text"] == "Hello world today"

    def test_merge_segments_respect_max_len(self):
        """Test that merging respects max_len parameter."""
        segments = [
            {"text": "A" * 400, "start": 0.0, "end": 1.0},
            {"text": "B" * 400, "start": 1.1, "end": 2.0},  # Would exceed 800 chars
        ]

        preprocessor = TranscriptPreprocessor(merge=True, max_gap=1.0, max_len=800)
        result = preprocessor.merge_segments(segments)

        # Should NOT merge because combined length > 800
        assert len(result) == 2
        assert result[0]["text"] == "A" * 400
        assert result[1]["text"] == "B" * 400

    def test_merge_segments_empty_list(self):
        """Test merging with empty segment list."""
        preprocessor = TranscriptPreprocessor(merge=True)
        result = preprocessor.merge_segments([])
        assert result == []

    def test_normalize_text_whitespace(self):
        """Test text normalization collapses whitespace."""
        preprocessor = TranscriptPreprocessor(normalize=True)
        text = "Hello    world  \n\n  today"
        result = preprocessor.normalize_text(text)
        assert result == "Hello world today"

    def test_normalize_text_punctuation(self):
        """Test text normalization adds space after punctuation."""
        preprocessor = TranscriptPreprocessor(normalize=True)
        text = "Hello.World is here!How are you?"
        result = preprocessor.normalize_text(text)
        assert result == "Hello. World is here! How are you?"

    def test_normalize_segments(self):
        """Test normalizing multiple segments."""
        segments = [
            {"text": "Hello   world", "start": 0.0, "end": 1.0},
            {"text": "How  are\nyou", "start": 1.0, "end": 2.0},
        ]

        preprocessor = TranscriptPreprocessor(normalize=True)
        result = preprocessor.normalize_segments(segments)

        assert result[0]["text"] == "Hello world"
        assert result[1]["text"] == "How are you"

    @pytest.mark.skip("Complex OpenAI mocking - integration test instead")
    def test_semantic_restore_success(self):
        """Test successful semantic restore (skipped - needs integration test)."""
        pass

    @pytest.mark.skip("Complex OpenAI mocking - integration test instead")
    def test_semantic_restore_batch_mismatch_fallback(self):
        """Test fallback when LLM returns wrong number of segments (skipped)."""
        pass

    @pytest.mark.skip("Complex OpenAI mocking - integration test instead")
    def test_semantic_restore_api_error(self):
        """Test error handling when OpenAI API fails (skipped)."""
        pass

    @pytest.mark.skip("Complex OpenAI mocking - integration test instead")
    def test_semantic_restore_no_openai_library(self):
        """Test error when OpenAI library not installed (skipped)."""
        pass

    def test_preprocess_merge_only(self):
        """Test preprocessing with merge only."""
        transcript = {
            "audio_path": "/path/to/audio.mp3",
            "language": "en",
            "asr_model": "base",
            "segments": [
                {"text": "Hello", "start": 0.0, "end": 1.0},
                {"text": "world", "start": 1.5, "end": 2.5},
            ],
        }

        preprocessor = TranscriptPreprocessor(merge=True, max_gap=1.0)
        result = preprocessor.preprocess(transcript)

        # Metadata preserved
        assert result["audio_path"] == "/path/to/audio.mp3"
        assert result["language"] == "en"
        assert result["asr_model"] == "base"

        # Segments merged
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "Hello world"

        # Text field generated
        assert result["text"] == "Hello world"

    def test_preprocess_normalize_only(self):
        """Test preprocessing with normalize only."""
        transcript = {
            "segments": [
                {"text": "Hello   world", "start": 0.0, "end": 1.0},
            ],
        }

        preprocessor = TranscriptPreprocessor(normalize=True)
        result = preprocessor.preprocess(transcript)

        assert result["segments"][0]["text"] == "Hello world"

    @pytest.mark.skip("Complex OpenAI mocking - integration test instead")
    def test_preprocess_all_steps(self):
        """Test preprocessing with merge, normalize, and restore (skipped)."""
        pass

    def test_preprocess_invalid_transcript(self):
        """Test error with invalid transcript format."""
        preprocessor = TranscriptPreprocessor()

        with pytest.raises(ValueError, match="must contain 'segments'"):
            preprocessor.preprocess({})

    def test_preprocess_empty_segments(self):
        """Test preprocessing with empty segments list."""
        transcript = {"segments": []}

        preprocessor = TranscriptPreprocessor(merge=True, normalize=True)
        result = preprocessor.preprocess(transcript)

        assert result["segments"] == []
        assert result["text"] == ""


class TestConvenienceFunctions:
    """Test convenience functions for direct use."""

    def test_merge_segments_convenience(self):
        """Test merge_segments convenience function."""
        segments = [
            {"text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "world", "start": 1.5, "end": 2.5},
        ]

        result = merge_segments(segments, max_gap=1.0, max_len=800)

        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_normalize_text_convenience(self):
        """Test normalize_text convenience function."""
        text = "Hello   world"
        result = normalize_text(text)
        assert result == "Hello world"

    def test_normalize_segments_convenience(self):
        """Test normalize_segments convenience function."""
        segments = [{"text": "Hello   world", "start": 0.0, "end": 1.0}]
        result = normalize_segments(segments)
        assert result[0]["text"] == "Hello world"

    def test_preprocess_transcript_convenience(self):
        """Test preprocess_transcript convenience function."""
        transcript = {
            "segments": [
                {"text": "Hello", "start": 0.0, "end": 1.0},
                {"text": "world", "start": 1.5, "end": 2.5},
            ],
        }

        result = preprocess_transcript(transcript, merge=True, normalize=True)

        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "Hello world"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_merge_preserves_timing(self):
        """Test that merge preserves correct start/end times."""
        segments = [
            {"text": "A", "start": 0.0, "end": 1.0},
            {"text": "B", "start": 1.2, "end": 2.0},
        ]

        preprocessor = TranscriptPreprocessor(merge=True, max_gap=1.0)
        result = preprocessor.merge_segments(segments)

        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 2.0  # End of last merged segment

    def test_normalize_handles_empty_text(self):
        """Test normalization with empty text."""
        preprocessor = TranscriptPreprocessor(normalize=True)
        result = preprocessor.normalize_text("")
        assert result == ""

    def test_normalize_handles_only_whitespace(self):
        """Test normalization with only whitespace."""
        preprocessor = TranscriptPreprocessor(normalize=True)
        result = preprocessor.normalize_text("   \n\n  ")
        assert result == ""

    def test_merge_with_single_segment(self):
        """Test merging with only one segment."""
        segments = [{"text": "Hello", "start": 0.0, "end": 1.0}]

        preprocessor = TranscriptPreprocessor(merge=True)
        result = preprocessor.merge_segments(segments)

        assert len(result) == 1
        assert result[0]["text"] == "Hello"

    def test_preprocess_preserves_unknown_metadata(self):
        """Test that preprocessing preserves all known metadata fields."""
        transcript = {
            "audio_path": "/path/audio.mp3",
            "language": "en",
            "asr_model": "base",
            "asr_provider": "local",
            "decoder_options": {"beam_size": 5},
            "segments": [{"text": "Hello", "start": 0.0, "end": 1.0}],
        }

        preprocessor = TranscriptPreprocessor()
        result = preprocessor.preprocess(transcript)

        assert result["audio_path"] == "/path/audio.mp3"
        assert result["language"] == "en"
        assert result["asr_model"] == "base"
        assert result["asr_provider"] == "local"
        assert result["decoder_options"] == {"beam_size": 5}


class TestAdFiltering:
    """Test ad filtering functionality."""

    def test_init_skip_ads_default(self):
        """Test that skip_ads defaults to False."""
        preprocessor = TranscriptPreprocessor()
        assert preprocessor.skip_ads is False

    @mock.patch("podx.core.preprocess.get_provider")
    def test_init_with_skip_ads(self, mock_get_provider):
        """Test initialization with skip_ads enabled."""
        mock_get_provider.return_value = mock.Mock()

        preprocessor = TranscriptPreprocessor(skip_ads=True)
        assert preprocessor.skip_ads is True
        assert preprocessor.llm_provider is not None

    @mock.patch("podx.core.preprocess.get_provider")
    def test_classify_ad_segments_all_content(self, mock_get_provider):
        """Test classification when all segments are content."""
        mock_provider = mock.Mock()
        mock_response = mock.Mock()
        mock_response.content = "CONTENT\nCONTENT\nCONTENT"
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        preprocessor = TranscriptPreprocessor(skip_ads=True)
        segments = [
            {"text": "Welcome to the show", "start": 0.0, "end": 5.0},
            {"text": "Today we discuss AI", "start": 5.0, "end": 10.0},
            {"text": "It's really interesting", "start": 10.0, "end": 15.0},
        ]

        result = preprocessor.classify_ad_segments(segments)

        assert result == [False, False, False]

    @mock.patch("podx.core.preprocess.get_provider")
    def test_classify_ad_segments_mixed(self, mock_get_provider):
        """Test classification with mixed content and ads."""
        mock_provider = mock.Mock()
        mock_response = mock.Mock()
        mock_response.content = "CONTENT\nAD\nCONTENT"
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        preprocessor = TranscriptPreprocessor(skip_ads=True)
        segments = [
            {"text": "Welcome to the show", "start": 0.0, "end": 5.0},
            {
                "text": "This episode brought to you by Acme Corp",
                "start": 5.0,
                "end": 10.0,
            },
            {"text": "Now back to our discussion", "start": 10.0, "end": 15.0},
        ]

        result = preprocessor.classify_ad_segments(segments)

        assert result == [False, True, False]

    @mock.patch("podx.core.preprocess.get_provider")
    def test_filter_ad_segments(self, mock_get_provider):
        """Test filtering removes ad segments."""
        mock_provider = mock.Mock()
        mock_response = mock.Mock()
        mock_response.content = "CONTENT\nAD\nCONTENT"
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        preprocessor = TranscriptPreprocessor(skip_ads=True)
        segments = [
            {"text": "Welcome to the show", "start": 0.0, "end": 5.0},
            {
                "text": "This episode brought to you by Acme Corp",
                "start": 5.0,
                "end": 10.0,
            },
            {"text": "Now back to our discussion", "start": 10.0, "end": 15.0},
        ]

        filtered, ads_removed = preprocessor.filter_ad_segments(segments)

        assert len(filtered) == 2
        assert ads_removed == 1
        assert filtered[0]["text"] == "Welcome to the show"
        assert filtered[1]["text"] == "Now back to our discussion"

    @mock.patch("podx.core.preprocess.get_provider")
    def test_preprocess_with_skip_ads(self, mock_get_provider):
        """Test full preprocessing with ad filtering enabled."""
        mock_provider = mock.Mock()
        mock_response = mock.Mock()
        mock_response.content = "CONTENT\nAD\nCONTENT"
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        preprocessor = TranscriptPreprocessor(skip_ads=True, merge=True, normalize=True)
        transcript = {
            "segments": [
                {"text": "Welcome to the show", "start": 0.0, "end": 5.0},
                {"text": "Use code PODCAST for 20% off", "start": 5.0, "end": 10.0},
                {"text": "Now back to our discussion", "start": 10.0, "end": 15.0},
            ],
        }

        result = preprocessor.preprocess(transcript)

        # Ad should be removed
        assert result["ads_removed"] == 1
        # After ad removal, remaining 2 segments (gap is 5 seconds, won't merge with default max_gap=1.0)
        assert len(result["segments"]) == 2

    def test_preprocess_without_skip_ads(self):
        """Test preprocessing without ad filtering preserves all segments."""
        preprocessor = TranscriptPreprocessor(merge=False, normalize=False)
        transcript = {
            "segments": [
                {"text": "Welcome to the show", "start": 0.0, "end": 5.0},
                {"text": "Use code PODCAST for 20% off", "start": 5.0, "end": 10.0},
                {"text": "Now back to our discussion", "start": 10.0, "end": 15.0},
            ],
        }

        result = preprocessor.preprocess(transcript)

        assert result["ads_removed"] == 0
        assert len(result["segments"]) == 3

    @mock.patch("podx.core.preprocess.get_provider")
    def test_classify_conservative_unknown_response(self, mock_get_provider):
        """Test that unknown responses are treated as content (conservative)."""
        mock_provider = mock.Mock()
        mock_response = mock.Mock()
        # LLM returns unexpected format
        mock_response.content = "MAYBE\nUNKNOWN\nPOSSIBLY_AD"
        mock_provider.complete.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        preprocessor = TranscriptPreprocessor(skip_ads=True)
        segments = [
            {"text": "Segment 1", "start": 0.0, "end": 5.0},
            {"text": "Segment 2", "start": 5.0, "end": 10.0},
            {"text": "Segment 3", "start": 10.0, "end": 15.0},
        ]

        result = preprocessor.classify_ad_segments(segments)

        # All should be False (content) since none explicitly said "AD"
        assert result == [False, False, False]

    def test_filter_ad_segments_empty_list(self):
        """Test filtering with empty segment list."""
        preprocessor = TranscriptPreprocessor(skip_ads=False)
        filtered, ads_removed = preprocessor.filter_ad_segments([])

        assert filtered == []
        assert ads_removed == 0
