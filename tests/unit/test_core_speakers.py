"""Unit tests for podx.core.speakers module."""

import json

import pytest

from podx.core.speakers import (
    SPEAKER_MAP_FILENAME,
    _segments_have_generic_speakers,
    apply_speaker_map_to_transcript,
    has_generic_speakers,
    load_speaker_map,
    save_speaker_map,
)


@pytest.fixture
def episode_dir(tmp_path):
    """Create a temporary episode directory with a diarized transcript."""
    transcript = {
        "audio_path": "/tmp/audio.wav",
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "Hello everyone.", "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 10.0, "text": "Thanks for having me.", "speaker": "SPEAKER_01"},
            {"start": 10.0, "end": 15.0, "text": "Let's get started.", "speaker": "SPEAKER_00"},
        ],
    }
    (tmp_path / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    return tmp_path


@pytest.fixture
def speaker_map():
    return {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}


class TestSaveLoadSpeakerMap:
    def test_round_trip(self, tmp_path, speaker_map):
        save_speaker_map(tmp_path, speaker_map)
        loaded = load_speaker_map(tmp_path)
        assert loaded == speaker_map

    def test_save_creates_file(self, tmp_path, speaker_map):
        path = save_speaker_map(tmp_path, speaker_map)
        assert path.exists()
        assert path.name == SPEAKER_MAP_FILENAME

    def test_load_nonexistent_returns_none(self, tmp_path):
        result = load_speaker_map(tmp_path)
        assert result is None

    def test_load_invalid_json_returns_none(self, tmp_path):
        (tmp_path / SPEAKER_MAP_FILENAME).write_text("not json", encoding="utf-8")
        result = load_speaker_map(tmp_path)
        assert result is None

    def test_load_non_dict_returns_none(self, tmp_path):
        (tmp_path / SPEAKER_MAP_FILENAME).write_text('["a", "b"]', encoding="utf-8")
        result = load_speaker_map(tmp_path)
        assert result is None


class TestApplySpeakerMap:
    def test_applies_names(self, episode_dir, speaker_map):
        result = apply_speaker_map_to_transcript(episode_dir, speaker_map)
        assert result is True

        transcript = json.loads((episode_dir / "transcript.json").read_text())
        assert transcript["segments"][0]["speaker"] == "Alice"
        assert transcript["segments"][1]["speaker"] == "Bob"
        assert transcript["segments"][2]["speaker"] == "Alice"

    def test_no_transcript_returns_false(self, tmp_path, speaker_map):
        result = apply_speaker_map_to_transcript(tmp_path, speaker_map)
        assert result is False

    def test_no_matching_speakers_returns_false(self, episode_dir):
        result = apply_speaker_map_to_transcript(episode_dir, {"SPEAKER_99": "Nobody"})
        assert result is False

    def test_save_transcript_false(self, episode_dir, speaker_map):
        original = (episode_dir / "transcript.json").read_text()
        apply_speaker_map_to_transcript(episode_dir, speaker_map, save_transcript=False)
        assert (episode_dir / "transcript.json").read_text() == original


class TestHasGenericSpeakers:
    def test_true_with_generic_ids(self, episode_dir):
        assert has_generic_speakers(episode_dir) is True

    def test_false_with_real_names(self, tmp_path):
        transcript = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello.", "speaker": "Alice"},
            ]
        }
        (tmp_path / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
        assert has_generic_speakers(tmp_path) is False

    def test_false_no_transcript(self, tmp_path):
        assert has_generic_speakers(tmp_path) is False

    def test_false_no_speakers(self, tmp_path):
        transcript = {"segments": [{"start": 0.0, "end": 5.0, "text": "Hello."}]}
        (tmp_path / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
        assert has_generic_speakers(tmp_path) is False


class TestSegmentsHaveGenericSpeakers:
    def test_generic_pattern(self):
        segments = [{"speaker": "SPEAKER_00"}, {"speaker": "SPEAKER_01"}]
        assert _segments_have_generic_speakers(segments) is True

    def test_real_names(self):
        segments = [{"speaker": "Alice"}, {"speaker": "Bob"}]
        assert _segments_have_generic_speakers(segments) is False

    def test_empty_segments(self):
        assert _segments_have_generic_speakers([]) is False

    def test_mixed(self):
        segments = [{"speaker": "Alice"}, {"speaker": "SPEAKER_01"}]
        assert _segments_have_generic_speakers(segments) is True
