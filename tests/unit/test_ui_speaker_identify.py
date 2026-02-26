"""Unit tests for speaker identification UI module."""

from unittest.mock import patch

import pytest

from podx.ui.speaker_identify import (
    MORE_COMMANDS,
    PLAY_COMMANDS,
    get_all_speaker_utterances,
    get_speaker_samples,
    has_generic_speaker_ids,
    identify_speakers_interactive,
    resolve_audio_path,
)


class TestGetSpeakerSamples:
    """Test speaker sample extraction."""

    @pytest.fixture
    def sample_segments(self):
        """Sample segments for testing."""
        return [
            {
                "speaker": "SPEAKER_00",
                "text": "This is a longer sample text for testing purposes.",
                "start": 0,
            },
            {"speaker": "SPEAKER_00", "text": "Short.", "start": 10},  # Too short
            {
                "speaker": "SPEAKER_01",
                "text": "Another speaker says something interesting here.",
                "start": 20,
            },
            {
                "speaker": "SPEAKER_00",
                "text": "Back to the first speaker with more content here.",
                "start": 30,
            },
        ]

    def test_gets_samples_per_speaker(self, sample_segments):
        """Test extracting samples grouped by speaker."""
        samples = get_speaker_samples(sample_segments)
        assert "SPEAKER_00" in samples
        assert "SPEAKER_01" in samples
        # Short utterance should be filtered
        assert len(samples["SPEAKER_00"]) == 2

    def test_respects_max_samples(self, sample_segments):
        """Test max_samples limit."""
        samples = get_speaker_samples(sample_segments, max_samples=1)
        assert len(samples["SPEAKER_00"]) == 1


class TestGetAllSpeakerUtterances:
    """Test getting all utterances for a speaker."""

    def test_returns_all_utterances(self):
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "First utterance that is long enough to display.",
                "start": 0,
            },
            {
                "speaker": "SPEAKER_01",
                "text": "Other speaker talking about something.",
                "start": 10,
            },
            {
                "speaker": "SPEAKER_00",
                "text": "Second utterance that is also long enough.",
                "start": 20,
            },
        ]
        result = get_all_speaker_utterances(segments, "SPEAKER_00")
        assert len(result) == 2
        assert result[0][1] == 0  # segment index
        assert result[1][1] == 2  # segment index


class TestHasGenericSpeakerIds:
    """Test generic speaker ID detection."""

    def test_detects_generic_ids(self):
        segments = [{"speaker": "SPEAKER_00", "text": "Hello"}]
        assert has_generic_speaker_ids(segments) is True

    def test_no_generic_ids(self):
        segments = [{"speaker": "John Smith", "text": "Hello"}]
        assert has_generic_speaker_ids(segments) is False

    def test_empty_segments(self):
        assert has_generic_speaker_ids([]) is False


class TestPlayCommands:
    """Test play command constants."""

    def test_play_commands_exist(self):
        """Verify play commands are defined."""
        assert "play" in PLAY_COMMANDS
        assert "p" in PLAY_COMMANDS

    def test_play_and_more_commands_disjoint(self):
        """Play and more commands should not overlap."""
        assert PLAY_COMMANDS.isdisjoint(MORE_COMMANDS)


class TestIdentifySpeakersInteractive:
    """Test identify_speakers_interactive function."""

    @pytest.fixture
    def sample_segments(self):
        """Segments with two speakers."""
        return [
            {
                "speaker": "SPEAKER_00",
                "text": "This is a longer sample text for testing purposes.",
                "start": 0,
                "end": 10,
            },
            {
                "speaker": "SPEAKER_01",
                "text": "Another speaker says something interesting here.",
                "start": 20,
                "end": 30,
            },
        ]

    @patch("podx.ui.speaker_identify.input")
    def test_basic_identification(self, mock_input, sample_segments):
        """Test basic speaker name entry."""
        mock_input.side_effect = ["Alice", "Bob"]

        result = identify_speakers_interactive(sample_segments)

        assert result["SPEAKER_00"] == "Alice"
        assert result["SPEAKER_01"] == "Bob"

    @patch("podx.ui.speaker_identify.input")
    def test_empty_input_keeps_original(self, mock_input, sample_segments):
        """Test that empty input keeps original speaker ID."""
        mock_input.side_effect = ["", "Bob"]

        result = identify_speakers_interactive(sample_segments)

        assert result["SPEAKER_00"] == "SPEAKER_00"
        assert result["SPEAKER_01"] == "Bob"

    @patch("podx.ui.speaker_identify.input")
    def test_play_without_audio_path(self, mock_input, sample_segments):
        """Test that play command shows message when no audio available."""
        mock_input.side_effect = ["play", "Alice", "Bob"]

        result = identify_speakers_interactive(sample_segments, audio_path=None)

        assert result["SPEAKER_00"] == "Alice"
        assert result["SPEAKER_01"] == "Bob"

    @patch("podx.ui.speaker_identify.input")
    def test_play_with_nonexistent_audio(self, mock_input, sample_segments, tmp_path):
        """Test play with audio_path that doesn't exist."""
        fake_audio = tmp_path / "nonexistent.wav"
        mock_input.side_effect = ["play", "Alice", "Bob"]

        result = identify_speakers_interactive(sample_segments, audio_path=fake_audio)

        # Should fall through since playback_available is False
        assert result["SPEAKER_00"] == "Alice"

    @patch("podx.ui.speaker_identify._play_speaker_sample")
    @patch("podx.ui.speaker_identify.input")
    def test_play_command_prompts_for_sample(
        self, mock_input, mock_play, sample_segments, tmp_path
    ):
        """Test that play command prompts for which sample to play."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")

        # "play" -> "1" (sample choice) -> "Alice" -> "Bob"
        mock_input.side_effect = ["play", "1", "Alice", "Bob"]
        mock_play.return_value = None

        result = identify_speakers_interactive(sample_segments, audio_path=audio_file)

        assert result["SPEAKER_00"] == "Alice"
        assert result["SPEAKER_01"] == "Bob"
        # Verify play was called with the right sample
        mock_play.assert_called_once()


class TestResolveAudioPath:
    """Test resolve_audio_path function."""

    def test_finds_audio_wav_in_episode_dir(self, tmp_path):
        """Test finding audio.wav directly in episode directory."""
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake")

        result = resolve_audio_path(tmp_path)
        assert result == audio_file

    def test_finds_audio_mp3_in_episode_dir(self, tmp_path):
        """Test finding audio.mp3 when no .wav exists."""
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake")

        result = resolve_audio_path(tmp_path)
        assert result == audio_file

    def test_uses_transcript_audio_path_absolute(self, tmp_path):
        """Test using absolute path from transcript."""
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake")

        result = resolve_audio_path(tmp_path, str(audio_file))
        assert result == audio_file

    def test_uses_transcript_audio_path_relative(self, tmp_path):
        """Test using relative path from transcript."""
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake")

        result = resolve_audio_path(tmp_path, "audio.wav")
        assert result == audio_file

    def test_extracts_filename_from_stale_path(self, tmp_path):
        """Test extracting filename when stored path is stale."""
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake")

        # Simulate a stale absolute path from a different machine
        stale_path = "/old/machine/episodes/2024-01-01-episode/audio.wav"
        result = resolve_audio_path(tmp_path, stale_path)
        assert result == audio_file

    def test_fallback_to_directory_scan(self, tmp_path):
        """Test fallback when transcript audio_path is None."""
        audio_file = tmp_path / "episode-audio.wav"
        audio_file.write_bytes(b"fake")

        result = resolve_audio_path(tmp_path, None)
        # Should find via glob since no audio.wav exists but episode-audio.wav does
        assert result == audio_file

    def test_returns_none_when_no_audio(self, tmp_path):
        """Test returning None when no audio file exists."""
        result = resolve_audio_path(tmp_path)
        assert result is None

    def test_prefers_stored_path_over_fallback(self, tmp_path):
        """Test that stored path is preferred over directory scan."""
        # Create two audio files
        stored = tmp_path / "original.wav"
        stored.write_bytes(b"fake")
        other = tmp_path / "audio.wav"
        other.write_bytes(b"fake")

        result = resolve_audio_path(tmp_path, str(stored))
        assert result == stored
