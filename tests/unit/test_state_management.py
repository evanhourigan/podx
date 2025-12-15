"""Tests for state management (ArtifactDetector and RunState)."""

import json
from datetime import datetime

from podx.domain import PipelineStep
from podx.state.artifact_detector import ArtifactDetector, EpisodeArtifacts
from podx.state.run_state import RunState


class TestEpisodeArtifacts:
    """Test EpisodeArtifacts dataclass and properties."""

    def test_initialization(self, tmp_path):
        """Test basic initialization."""
        artifacts = EpisodeArtifacts(working_dir=tmp_path)

        assert artifacts.working_dir == tmp_path
        assert artifacts.episode_meta is None
        assert artifacts.audio_meta is None
        assert artifacts.transcripts == []
        assert artifacts.aligned_transcripts == []
        assert artifacts.diarized_transcripts == []
        assert artifacts.preprocessed_transcripts == []
        assert artifacts.deepcasts == []
        assert artifacts.agreements == []
        assert artifacts.consensus == []
        assert artifacts.notion_output is None

    def test_has_transcripts_empty(self, tmp_path):
        """Test has_transcripts returns False when no transcripts."""
        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        assert artifacts.has_transcripts is False

    def test_has_transcripts_with_files(self, tmp_path):
        """Test has_transcripts returns True when transcripts exist."""
        artifacts = EpisodeArtifacts(
            working_dir=tmp_path,
            transcripts=[tmp_path / "transcript.json"],
        )
        assert artifacts.has_transcripts is True

    def test_has_aligned_empty(self, tmp_path):
        """Test has_aligned returns False when no aligned transcripts."""
        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        assert artifacts.has_aligned is False

    def test_has_aligned_with_files(self, tmp_path):
        """Test has_aligned returns True when aligned transcripts exist."""
        artifacts = EpisodeArtifacts(
            working_dir=tmp_path,
            aligned_transcripts=[tmp_path / "aligned-transcript.json"],
        )
        assert artifacts.has_aligned is True

    def test_has_diarized_empty(self, tmp_path):
        """Test has_diarized returns False when no diarized transcripts."""
        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        assert artifacts.has_diarized is False

    def test_has_diarized_with_files(self, tmp_path):
        """Test has_diarized returns True when diarized transcripts exist."""
        artifacts = EpisodeArtifacts(
            working_dir=tmp_path,
            diarized_transcripts=[tmp_path / "diarized-transcript.json"],
        )
        assert artifacts.has_diarized is True

    def test_has_preprocessed_empty(self, tmp_path):
        """Test has_preprocessed returns False when no preprocessed transcripts."""
        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        assert artifacts.has_preprocessed is False

    def test_has_preprocessed_with_files(self, tmp_path):
        """Test has_preprocessed returns True when preprocessed transcripts exist."""
        artifacts = EpisodeArtifacts(
            working_dir=tmp_path,
            preprocessed_transcripts=[tmp_path / "transcript-preprocessed-base.json"],
        )
        assert artifacts.has_preprocessed is True

    def test_has_deepcast_empty(self, tmp_path):
        """Test has_deepcast returns False when no deepcast analyses."""
        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        assert artifacts.has_deepcast is False

    def test_has_deepcast_with_files(self, tmp_path):
        """Test has_deepcast returns True when deepcast analyses exist."""
        artifacts = EpisodeArtifacts(
            working_dir=tmp_path,
            deepcasts=[tmp_path / "deepcast.json"],
        )
        assert artifacts.has_deepcast is True

    def test_has_notion_no_file(self, tmp_path):
        """Test has_notion returns False when notion_output is None."""
        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        assert artifacts.has_notion is False

    def test_has_notion_file_not_exists(self, tmp_path):
        """Test has_notion returns False when notion_output file doesn't exist."""
        artifacts = EpisodeArtifacts(
            working_dir=tmp_path,
            notion_output=tmp_path / "notion.out.json",
        )
        assert artifacts.has_notion is False

    def test_has_notion_file_exists(self, tmp_path):
        """Test has_notion returns True when notion_output file exists."""
        notion_file = tmp_path / "notion.out.json"
        notion_file.write_text("{}", encoding="utf-8")

        artifacts = EpisodeArtifacts(
            working_dir=tmp_path,
            notion_output=notion_file,
        )
        assert artifacts.has_notion is True


class TestArtifactDetector:
    """Test ArtifactDetector class."""

    def test_initialization(self, tmp_path):
        """Test basic initialization."""
        detector = ArtifactDetector(tmp_path)
        assert detector.working_dir == tmp_path

    def test_detect_all_empty_directory(self, tmp_path):
        """Test detect_all with no artifacts."""
        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert artifacts.working_dir == tmp_path
        assert artifacts.episode_meta is None
        assert artifacts.audio_meta is None
        assert len(artifacts.transcripts) == 0
        assert len(artifacts.aligned_transcripts) == 0
        assert len(artifacts.diarized_transcripts) == 0
        assert len(artifacts.preprocessed_transcripts) == 0
        assert len(artifacts.deepcasts) == 0
        assert artifacts.notion_output is None

    def test_detect_episode_meta(self, tmp_path):
        """Test detection of episode-meta.json."""
        episode_meta = tmp_path / "episode-meta.json"
        episode_meta.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert artifacts.episode_meta == episode_meta
        assert artifacts.episode_meta.exists()

    def test_detect_audio_meta(self, tmp_path):
        """Test detection of audio-meta.json."""
        audio_meta = tmp_path / "audio-meta.json"
        audio_meta.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert artifacts.audio_meta == audio_meta
        assert artifacts.audio_meta.exists()

    def test_detect_transcript_new_format(self, tmp_path):
        """Test detection of new format transcript (transcript-*.json)."""
        transcript = tmp_path / "transcript-base.json"
        transcript.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.transcripts) == 1
        assert transcript in artifacts.transcripts

    def test_detect_transcript_legacy_format(self, tmp_path):
        """Test detection of legacy format transcript (transcript.json)."""
        transcript = tmp_path / "transcript.json"
        transcript.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.transcripts) == 1
        assert transcript in artifacts.transcripts

    def test_detect_multiple_transcripts(self, tmp_path):
        """Test detection of multiple transcripts."""
        t1 = tmp_path / "transcript-base.json"
        t2 = tmp_path / "transcript-medium.json"
        t1.write_text("{}", encoding="utf-8")
        t2.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.transcripts) == 2
        assert t1 in artifacts.transcripts
        assert t2 in artifacts.transcripts

    def test_detect_aligned_new_format(self, tmp_path):
        """Test detection of new format aligned transcript."""
        aligned = tmp_path / "transcript-aligned-base.json"
        aligned.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.aligned_transcripts) == 1
        assert aligned in artifacts.aligned_transcripts

    def test_detect_aligned_legacy_format(self, tmp_path):
        """Test detection of legacy format aligned transcript."""
        aligned = tmp_path / "aligned-transcript.json"
        aligned.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.aligned_transcripts) == 1
        assert aligned in artifacts.aligned_transcripts

    def test_detect_diarized_new_format(self, tmp_path):
        """Test detection of new format diarized transcript."""
        diarized = tmp_path / "transcript-diarized-base.json"
        diarized.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.diarized_transcripts) == 1
        assert diarized in artifacts.diarized_transcripts

    def test_detect_diarized_legacy_format(self, tmp_path):
        """Test detection of legacy format diarized transcript."""
        diarized = tmp_path / "diarized-transcript.json"
        diarized.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.diarized_transcripts) == 1
        assert diarized in artifacts.diarized_transcripts

    def test_detect_preprocessed(self, tmp_path):
        """Test detection of preprocessed transcripts."""
        preprocessed = tmp_path / "transcript-preprocessed-base.json"
        preprocessed.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.preprocessed_transcripts) == 1
        assert preprocessed in artifacts.preprocessed_transcripts

    def test_detect_deepcast(self, tmp_path):
        """Test detection of deepcast analyses."""
        deepcast1 = tmp_path / "deepcast.json"
        deepcast2 = tmp_path / "deepcast-quotes.json"
        deepcast1.write_text("{}", encoding="utf-8")
        deepcast2.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert len(artifacts.deepcasts) == 2
        assert deepcast1 in artifacts.deepcasts
        assert deepcast2 in artifacts.deepcasts

    def test_detect_notion_output(self, tmp_path):
        """Test detection of Notion output."""
        notion = tmp_path / "notion.out.json"
        notion.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifacts = detector.detect_all()

        assert artifacts.notion_output == notion
        assert artifacts.notion_output.exists()

    def test_detect_completed_steps_empty(self, tmp_path):
        """Test detect_completed_steps with no artifacts."""
        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert len(completed) == 0
        assert isinstance(completed, set)

    def test_detect_completed_steps_fetch(self, tmp_path):
        """Test detect_completed_steps detects FETCH step."""
        (tmp_path / "episode-meta.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.FETCH in completed

    def test_detect_completed_steps_transcode(self, tmp_path):
        """Test detect_completed_steps detects TRANSCODE step."""
        (tmp_path / "audio-meta.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.TRANSCODE in completed

    def test_detect_completed_steps_transcribe(self, tmp_path):
        """Test detect_completed_steps detects TRANSCRIBE step."""
        (tmp_path / "transcript-base.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.TRANSCRIBE in completed

    def test_detect_completed_steps_align(self, tmp_path):
        """Test detect_completed_steps detects ALIGN step."""
        (tmp_path / "transcript-aligned-base.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.ALIGN in completed

    def test_detect_completed_steps_diarize(self, tmp_path):
        """Test detect_completed_steps detects DIARIZE step."""
        (tmp_path / "transcript-diarized-base.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.DIARIZE in completed

    def test_detect_completed_steps_preprocess(self, tmp_path):
        """Test detect_completed_steps detects PREPROCESS step."""
        (tmp_path / "transcript-preprocessed-base.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.PREPROCESS in completed

    def test_detect_completed_steps_deepcast(self, tmp_path):
        """Test detect_completed_steps detects DEEPCAST step."""
        (tmp_path / "deepcast.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.DEEPCAST in completed

    def test_detect_completed_steps_notion(self, tmp_path):
        """Test detect_completed_steps detects NOTION step."""
        (tmp_path / "notion.out.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert PipelineStep.NOTION in completed

    def test_detect_completed_steps_multiple(self, tmp_path):
        """Test detect_completed_steps with multiple completed steps."""
        (tmp_path / "episode-meta.json").write_text("{}", encoding="utf-8")
        (tmp_path / "audio-meta.json").write_text("{}", encoding="utf-8")
        (tmp_path / "transcript-base.json").write_text("{}", encoding="utf-8")
        (tmp_path / "deepcast.json").write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        completed = detector.detect_completed_steps()

        assert len(completed) == 4
        assert PipelineStep.FETCH in completed
        assert PipelineStep.TRANSCODE in completed
        assert PipelineStep.TRANSCRIBE in completed
        assert PipelineStep.DEEPCAST in completed

    def test_get_artifact_for_step_fetch(self, tmp_path):
        """Test get_artifact_for_step returns episode-meta.json for FETCH."""
        episode_meta = tmp_path / "episode-meta.json"
        episode_meta.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifact = detector.get_artifact_for_step(PipelineStep.FETCH)

        assert artifact == episode_meta

    def test_get_artifact_for_step_transcode(self, tmp_path):
        """Test get_artifact_for_step returns audio-meta.json for TRANSCODE."""
        audio_meta = tmp_path / "audio-meta.json"
        audio_meta.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifact = detector.get_artifact_for_step(PipelineStep.TRANSCODE)

        assert artifact == audio_meta

    def test_get_artifact_for_step_transcribe(self, tmp_path):
        """Test get_artifact_for_step returns first transcript for TRANSCRIBE."""
        t1 = tmp_path / "transcript-base.json"
        t2 = tmp_path / "transcript-medium.json"
        t1.write_text("{}", encoding="utf-8")
        t2.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        artifact = detector.get_artifact_for_step(PipelineStep.TRANSCRIBE)

        # Should return first transcript (sorted)
        assert artifact in [t1, t2]

    def test_get_artifact_for_step_not_found(self, tmp_path):
        """Test get_artifact_for_step returns None when artifact not found."""
        detector = ArtifactDetector(tmp_path)
        artifact = detector.get_artifact_for_step(PipelineStep.FETCH)

        assert artifact is None

    def test_find_files_removes_duplicates(self, tmp_path):
        """Test _find_files removes duplicate matches."""
        # Create a file that matches multiple patterns
        transcript = tmp_path / "transcript.json"
        transcript.write_text("{}", encoding="utf-8")

        detector = ArtifactDetector(tmp_path)
        # Use patterns that both match the same file
        files = detector._find_files(["transcript.json", "transcript*.json"])

        # Should only return the file once
        assert len(files) == 1
        assert transcript in files


class TestRunState:
    """Test RunState class."""

    def test_initialization(self, tmp_path):
        """Test basic initialization."""
        state = RunState(tmp_path)

        assert state.working_dir == tmp_path
        assert state.config is not None
        assert len(state.completed_steps) == 0
        assert state.metadata == {}
        assert isinstance(state.created_at, datetime)
        assert isinstance(state.updated_at, datetime)

    def test_initialization_with_config(self, tmp_path):
        """Test initialization with custom config."""
        from podx.domain import PipelineConfig

        config = PipelineConfig(show="Test Show", model="medium")
        state = RunState(tmp_path, config=config)

        assert state.config == config
        assert state.config.show == "Test Show"
        assert state.config.model == "medium"

    def test_mark_completed(self, tmp_path):
        """Test marking a step as completed."""
        state = RunState(tmp_path)
        state.mark_completed(PipelineStep.FETCH)

        assert PipelineStep.FETCH in state.completed_steps
        assert len(state.completed_steps) == 1

    def test_mark_completed_multiple(self, tmp_path):
        """Test marking multiple steps as completed."""
        state = RunState(tmp_path)
        state.mark_completed(PipelineStep.FETCH)
        state.mark_completed(PipelineStep.TRANSCRIBE)
        state.mark_completed(PipelineStep.DEEPCAST)

        assert len(state.completed_steps) == 3
        assert PipelineStep.FETCH in state.completed_steps
        assert PipelineStep.TRANSCRIBE in state.completed_steps
        assert PipelineStep.DEEPCAST in state.completed_steps

    def test_is_completed_true(self, tmp_path):
        """Test is_completed returns True for completed step."""
        state = RunState(tmp_path)
        state.mark_completed(PipelineStep.FETCH)

        assert state.is_completed(PipelineStep.FETCH) is True

    def test_is_completed_false(self, tmp_path):
        """Test is_completed returns False for non-completed step."""
        state = RunState(tmp_path)

        assert state.is_completed(PipelineStep.FETCH) is False

    def test_save_creates_file(self, tmp_path):
        """Test save creates run-state.json file."""
        state = RunState(tmp_path)
        state.mark_completed(PipelineStep.FETCH)
        state.save()

        state_file = tmp_path / "run-state.json"
        assert state_file.exists()

    def test_save_content_format(self, tmp_path):
        """Test save creates valid JSON with expected structure."""
        state = RunState(tmp_path)
        state.mark_completed(PipelineStep.FETCH)
        state.metadata["test_key"] = "test_value"
        state.save()

        state_file = tmp_path / "run-state.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))

        assert "completed_steps" in data
        assert "metadata" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "fetch" in data["completed_steps"]
        assert data["metadata"]["test_key"] == "test_value"

    def test_load_nonexistent_file(self, tmp_path):
        """Test load returns None when run-state.json doesn't exist."""
        state = RunState.load(tmp_path)
        assert state is None

    def test_load_existing_file(self, tmp_path):
        """Test load restores state from run-state.json."""
        # Create and save initial state
        state1 = RunState(tmp_path)
        state1.mark_completed(PipelineStep.FETCH)
        state1.mark_completed(PipelineStep.TRANSCRIBE)
        state1.metadata["test_key"] = "test_value"
        state1.save()

        # Load state in new instance
        state2 = RunState.load(tmp_path)

        assert state2 is not None
        assert len(state2.completed_steps) == 2
        assert PipelineStep.FETCH in state2.completed_steps
        assert PipelineStep.TRANSCRIBE in state2.completed_steps
        assert state2.metadata["test_key"] == "test_value"

    def test_load_preserves_timestamps(self, tmp_path):
        """Test load preserves created_at and updated_at timestamps."""
        # Create and save initial state
        state1 = RunState(tmp_path)
        state1.save()

        original_created = state1.created_at
        original_updated = state1.updated_at

        # Load state in new instance
        state2 = RunState.load(tmp_path)

        assert state2 is not None
        # Timestamps should be preserved (within 1 second tolerance for datetime parsing)
        assert abs((state2.created_at - original_created).total_seconds()) < 1
        assert abs((state2.updated_at - original_updated).total_seconds()) < 1

    def test_load_invalid_json(self, tmp_path):
        """Test load returns None for invalid JSON file."""
        state_file = tmp_path / "run-state.json"
        state_file.write_text("invalid json", encoding="utf-8")

        state = RunState.load(tmp_path)
        assert state is None

    def test_get_artifact_path(self, tmp_path):
        """Test get_artifact_path delegates to detector."""
        # Create artifact
        episode_meta = tmp_path / "episode-meta.json"
        episode_meta.write_text("{}", encoding="utf-8")

        state = RunState(tmp_path)
        artifact = state.get_artifact_path(PipelineStep.FETCH)

        assert artifact == episode_meta

    def test_detect_completed_steps(self, tmp_path):
        """Test detect_completed_steps scans for artifacts."""
        # Create artifacts
        (tmp_path / "episode-meta.json").write_text("{}", encoding="utf-8")
        (tmp_path / "transcript-base.json").write_text("{}", encoding="utf-8")

        state = RunState(tmp_path)
        detected = state.detect_completed_steps()

        assert len(detected) == 2
        assert PipelineStep.FETCH in detected
        assert PipelineStep.TRANSCRIBE in detected

        # Should also update state.completed_steps
        assert len(state.completed_steps) == 2
        assert PipelineStep.FETCH in state.completed_steps
        assert PipelineStep.TRANSCRIBE in state.completed_steps

    def test_detect_completed_steps_updates_existing(self, tmp_path):
        """Test detect_completed_steps updates existing completed_steps."""
        state = RunState(tmp_path)
        state.mark_completed(PipelineStep.FETCH)

        # Create new artifact
        (tmp_path / "transcript-base.json").write_text("{}", encoding="utf-8")

        state.detect_completed_steps()

        # Should have both the manually marked and detected steps
        assert len(state.completed_steps) == 2
        assert PipelineStep.FETCH in state.completed_steps
        assert PipelineStep.TRANSCRIBE in state.completed_steps

    def test_get_artifacts(self, tmp_path):
        """Test get_artifacts returns EpisodeArtifacts."""
        # Create artifacts
        (tmp_path / "episode-meta.json").write_text("{}", encoding="utf-8")
        (tmp_path / "deepcast.json").write_text("{}", encoding="utf-8")

        state = RunState(tmp_path)
        artifacts = state.get_artifacts()

        assert isinstance(artifacts, EpisodeArtifacts)
        assert artifacts.episode_meta is not None
        assert len(artifacts.deepcasts) == 1

    def test_to_dict(self, tmp_path):
        """Test to_dict converts state to dictionary."""
        state = RunState(tmp_path)
        state.mark_completed(PipelineStep.FETCH)
        state.mark_completed(PipelineStep.TRANSCRIBE)
        state.metadata["test_key"] = "test_value"

        result = state.to_dict()

        assert isinstance(result, dict)
        assert result["working_dir"] == str(tmp_path)
        assert len(result["completed_steps"]) == 2
        assert "fetch" in result["completed_steps"]
        assert "transcribe" in result["completed_steps"]
        assert result["metadata"]["test_key"] == "test_value"
        assert "created_at" in result
        assert "updated_at" in result

    def test_to_dict_isoformat_timestamps(self, tmp_path):
        """Test to_dict uses ISO format for timestamps."""
        state = RunState(tmp_path)
        result = state.to_dict()

        # Should be parseable as ISO format
        created_at = datetime.fromisoformat(result["created_at"])
        updated_at = datetime.fromisoformat(result["updated_at"])

        assert isinstance(created_at, datetime)
        assert isinstance(updated_at, datetime)

    def test_round_trip_save_load(self, tmp_path):
        """Test complete round trip: create, save, load, verify."""
        # Create and populate state
        state1 = RunState(tmp_path)
        state1.mark_completed(PipelineStep.FETCH)
        state1.mark_completed(PipelineStep.TRANSCRIBE)
        state1.mark_completed(PipelineStep.DEEPCAST)
        state1.metadata["episode_title"] = "Test Episode"
        state1.metadata["duration"] = 1234.56
        state1.save()

        # Load in new instance
        state2 = RunState.load(tmp_path)

        # Verify everything matches
        assert state2 is not None
        assert state2.working_dir == state1.working_dir
        assert state2.completed_steps == state1.completed_steps
        assert state2.metadata == state1.metadata
        assert abs((state2.created_at - state1.created_at).total_seconds()) < 1
        assert abs((state2.updated_at - state1.updated_at).total_seconds()) < 1
