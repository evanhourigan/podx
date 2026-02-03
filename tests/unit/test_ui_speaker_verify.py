"""Unit tests for speaker verification UI module."""

import pytest

from podx.ui.speaker_verify import (
    _format_time_range,
    _format_timecode,
    _get_segments_for_chunk,
    _get_speaker_samples,
    apply_speaker_names_to_transcript,
    apply_speaker_swap,
)


class TestFormatTimecode:
    """Test timecode formatting."""

    def test_seconds_only(self):
        """Test formatting seconds under a minute."""
        assert _format_timecode(45) == "0:45"

    def test_minutes_and_seconds(self):
        """Test formatting minutes and seconds."""
        assert _format_timecode(125) == "2:05"
        assert _format_timecode(600) == "10:00"

    def test_hours(self):
        """Test formatting with hours."""
        assert _format_timecode(3661) == "1:01:01"
        assert _format_timecode(7200) == "2:00:00"

    def test_zero(self):
        """Test formatting zero seconds."""
        assert _format_timecode(0) == "0:00"


class TestFormatTimeRange:
    """Test time range formatting."""

    def test_simple_range(self):
        """Test formatting a simple time range."""
        assert _format_time_range(0, 600) == "0:00 - 10:00"

    def test_range_with_hours(self):
        """Test formatting a range spanning hours."""
        assert _format_time_range(3600, 7200) == "1:00:00 - 2:00:00"


class TestGetSpeakerSamples:
    """Test speaker sample extraction."""

    @pytest.fixture
    def sample_segments(self):
        """Sample segments for testing."""
        return [
            {"speaker": "SPEAKER_00", "text": "This is a longer sample text for testing.", "start": 0},
            {"speaker": "SPEAKER_00", "text": "Short.", "start": 10},  # Too short
            {"speaker": "SPEAKER_01", "text": "Another speaker says something interesting here.", "start": 20},
            {"speaker": "SPEAKER_00", "text": "Back to the first speaker with more content.", "start": 30},
            {"speaker": "SPEAKER_01", "text": "The second speaker continues talking.", "start": 40},
        ]

    def test_gets_samples_for_speaker(self, sample_segments):
        """Test extracting samples for a specific speaker."""
        samples = _get_speaker_samples(sample_segments, "SPEAKER_00")
        assert len(samples) == 2  # "Short." is filtered out
        assert samples[0][0] == 0  # First sample at time 0
        assert "longer sample" in samples[0][1]

    def test_respects_max_samples(self, sample_segments):
        """Test that max_samples limit is respected."""
        samples = _get_speaker_samples(sample_segments, "SPEAKER_00", max_samples=1)
        assert len(samples) == 1

    def test_empty_for_unknown_speaker(self, sample_segments):
        """Test that unknown speaker returns empty list."""
        samples = _get_speaker_samples(sample_segments, "SPEAKER_99")
        assert samples == []


class TestGetSegmentsForChunk:
    """Test chunk segment extraction."""

    @pytest.fixture
    def sample_segments(self):
        """Sample segments spanning multiple chunks."""
        return [
            {"speaker": "SPEAKER_00", "text": "Segment 1", "start": 0, "end": 10},
            {"speaker": "SPEAKER_01", "text": "Segment 2", "start": 15, "end": 25},
            {"speaker": "SPEAKER_00", "text": "Segment 3", "start": 30, "end": 40},
            {"speaker": "SPEAKER_01", "text": "Segment 4", "start": 65, "end": 75},
            {"speaker": "SPEAKER_00", "text": "Segment 5", "start": 120, "end": 130},
        ]

    def test_extracts_segments_in_range(self, sample_segments):
        """Test extracting segments within a time range."""
        chunk_segments = _get_segments_for_chunk(sample_segments, 0, 60)
        assert len(chunk_segments) == 3
        texts = [s["text"] for s in chunk_segments]
        assert "Segment 1" in texts
        assert "Segment 2" in texts
        assert "Segment 3" in texts

    def test_excludes_segments_outside_range(self, sample_segments):
        """Test that segments outside range are excluded."""
        chunk_segments = _get_segments_for_chunk(sample_segments, 60, 120)
        assert len(chunk_segments) == 1
        assert chunk_segments[0]["text"] == "Segment 4"

    def test_empty_chunk(self, sample_segments):
        """Test chunk with no segments."""
        chunk_segments = _get_segments_for_chunk(sample_segments, 200, 300)
        assert chunk_segments == []


class TestApplySpeakerSwap:
    """Test speaker swap within chunk."""

    @pytest.fixture
    def sample_segments(self):
        """Sample segments for swap testing."""
        return [
            {"speaker": "SPEAKER_00", "text": "First", "start": 0, "end": 10},
            {"speaker": "SPEAKER_01", "text": "Second", "start": 15, "end": 25},
            {"speaker": "SPEAKER_00", "text": "Third", "start": 30, "end": 40},
            {"speaker": "SPEAKER_01", "text": "Fourth", "start": 65, "end": 75},
        ]

    def test_swaps_speakers_in_chunk(self, sample_segments):
        """Test that speakers are swapped within chunk range."""
        apply_speaker_swap(sample_segments, 0, 50, "SPEAKER_00", "SPEAKER_01")

        # Segments in range should be swapped
        assert sample_segments[0]["speaker"] == "SPEAKER_01"  # Was SPEAKER_00
        assert sample_segments[1]["speaker"] == "SPEAKER_00"  # Was SPEAKER_01
        assert sample_segments[2]["speaker"] == "SPEAKER_01"  # Was SPEAKER_00

        # Segment outside range should be unchanged
        assert sample_segments[3]["speaker"] == "SPEAKER_01"

    def test_swaps_speakers_in_words(self):
        """Test that speakers are swapped in word-level data too."""
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "Hello",
                "start": 0,
                "end": 5,
                "words": [
                    {"word": "Hello", "start": 0, "end": 1, "speaker": "SPEAKER_00"},
                ],
            },
        ]
        apply_speaker_swap(segments, 0, 10, "SPEAKER_00", "SPEAKER_01")

        assert segments[0]["speaker"] == "SPEAKER_01"
        assert segments[0]["words"][0]["speaker"] == "SPEAKER_01"


class TestApplySpeakerNamesToTranscript:
    """Test applying speaker names to transcript."""

    def test_applies_names(self):
        """Test that speaker IDs are replaced with names."""
        segments = [
            {"speaker": "SPEAKER_00", "text": "Hello"},
            {"speaker": "SPEAKER_01", "text": "Hi there"},
            {"speaker": "SPEAKER_00", "text": "How are you?"},
        ]
        speaker_names = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}

        apply_speaker_names_to_transcript(segments, speaker_names)

        assert segments[0]["speaker"] == "Alice"
        assert segments[1]["speaker"] == "Bob"
        assert segments[2]["speaker"] == "Alice"

    def test_applies_names_to_words(self):
        """Test that speaker names are applied to word-level data."""
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "Hello",
                "words": [{"word": "Hello", "speaker": "SPEAKER_00"}],
            },
        ]
        speaker_names = {"SPEAKER_00": "Alice"}

        apply_speaker_names_to_transcript(segments, speaker_names)

        assert segments[0]["speaker"] == "Alice"
        assert segments[0]["words"][0]["speaker"] == "Alice"

    def test_ignores_unmapped_speakers(self):
        """Test that unmapped speakers are left unchanged."""
        segments = [
            {"speaker": "SPEAKER_00", "text": "Hello"},
            {"speaker": "SPEAKER_02", "text": "Unknown speaker"},
        ]
        speaker_names = {"SPEAKER_00": "Alice"}

        apply_speaker_names_to_transcript(segments, speaker_names)

        assert segments[0]["speaker"] == "Alice"
        assert segments[1]["speaker"] == "SPEAKER_02"  # Unchanged

    def test_handles_missing_speaker_field(self):
        """Test that segments without speaker field are handled."""
        segments = [
            {"text": "No speaker"},
            {"speaker": "SPEAKER_00", "text": "Has speaker"},
        ]
        speaker_names = {"SPEAKER_00": "Alice"}

        # Should not raise
        apply_speaker_names_to_transcript(segments, speaker_names)

        assert "speaker" not in segments[0]
        assert segments[1]["speaker"] == "Alice"
