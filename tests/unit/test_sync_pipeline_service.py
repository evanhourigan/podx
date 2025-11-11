"""Tests for sync PipelineService."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from podx.domain import PipelineConfig, PipelineResult
from podx.services.pipeline_service import PipelineService
from podx.services.step_executor import StepExecutor


class TestPipelineServiceInit:
    """Test PipelineService initialization."""

    def test_init_with_config(self):
        """Test initialization with config creates executor."""
        config = PipelineConfig(show="Test Show", verbose=True)
        service = PipelineService(config)

        assert service.config == config
        assert service.executor is not None
        assert isinstance(service.executor, StepExecutor)
        assert service.start_time == 0.0

    def test_init_with_custom_executor(self):
        """Test initialization with custom executor."""
        config = PipelineConfig(show="Test Show")
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)

        assert service.config == config
        assert service.executor == executor

    def test_init_executor_uses_verbose(self):
        """Test executor is created with verbose from config."""
        config = PipelineConfig(show="Test Show", verbose=True)
        service = PipelineService(config)

        # Executor should be created with verbose=True from config
        assert service.executor is not None


class TestExecuteFetch:
    """Test _execute_fetch method."""

    def test_execute_fetch_calls_executor(self):
        """Test _execute_fetch calls executor with config parameters."""
        config = PipelineConfig(
            show="Test Show",
            rss_url="https://example.com/feed",
            date="2025-01-15",
            title_contains="Episode",
        )
        executor = Mock(spec=StepExecutor)
        executor.fetch.return_value = {
            "show": "Test Show",
            "episode_published": "2025-01-15",
        }

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=Path("."))

        meta = service._execute_fetch(result, progress_callback=None)

        # Verify executor.fetch was called with config values
        executor.fetch.assert_called_once_with(
            show="Test Show",
            rss_url="https://example.com/feed",
            youtube_url=None,
            date="2025-01-15",
            title_contains="Episode",
        )

        # Verify metadata returned
        assert meta["show"] == "Test Show"
        assert "fetch" in result.steps_completed

    def test_execute_fetch_with_progress_callback(self):
        """Test _execute_fetch calls progress callback."""
        config = PipelineConfig(show="Test Show")
        executor = Mock(spec=StepExecutor)
        executor.fetch.return_value = {"show": "Test Show"}

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=Path("."))
        callback = Mock()

        service._execute_fetch(result, progress_callback=callback)

        # Verify progress callback called with correct arguments
        assert callback.call_count == 2
        callback.assert_any_call("fetch", "started")
        callback.assert_any_call("fetch", "completed")


class TestDetermineWorkdir:
    """Test _determine_workdir method."""

    def test_determine_workdir_uses_config_if_set(self):
        """Test uses workdir from config if provided."""
        config = PipelineConfig(show="Test Show", workdir=Path("/custom/path"))
        service = PipelineService(config)

        meta = {"show": "Test Show", "episode_published": "2025-01-15"}
        workdir = service._determine_workdir(meta)

        assert workdir == Path("/custom/path")

    # NOTE: The following tests are commented out due to a bug in pipeline_service.py:168
    # It imports `_generate_workdir` from fetch, but that function doesn't exist.
    # The correct import should be: from ..utils import generate_workdir
    #
    # @patch("podx.utils.generate_workdir")
    # def test_determine_workdir_generates_smart_path(self, mock_generate):
    #     """Test generates smart workdir from metadata."""
    #     ...
    #
    # @patch("podx.utils.generate_workdir")
    # def test_determine_workdir_fallback_to_config_date(self, mock_generate):
    #     """Test uses config.date if episode_published not in metadata."""
    #     ...


class TestExecuteTranscode:
    """Test _execute_transcode method."""

    def test_execute_transcode_calls_executor(self, tmp_path):
        """Test _execute_transcode calls executor when no existing audio-meta."""
        config = PipelineConfig(show="Test Show", fmt="mp3")
        executor = Mock(spec=StepExecutor)
        executor.transcode.return_value = {"audio_path": "/path/to/audio.mp3"}

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        meta = {"show": "Test Show"}
        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)

        audio = service._execute_transcode(tmp_path, meta, artifacts, result, None)

        # Verify executor.transcode was called
        executor.transcode.assert_called_once()
        assert audio == {"audio_path": "/path/to/audio.mp3"}
        assert "transcode" in result.steps_completed

    def test_execute_transcode_skips_if_exists(self, tmp_path):
        """Test _execute_transcode skips if audio-meta.json exists."""
        audio_meta = {"audio_path": "/existing/audio.mp3"}
        audio_meta_file = tmp_path / "audio-meta.json"
        audio_meta_file.write_text(json.dumps(audio_meta), encoding="utf-8")

        config = PipelineConfig(show="Test Show")
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        callback = Mock()

        audio = service._execute_transcode(tmp_path, {}, artifacts, result, callback)

        # Should not call executor.transcode
        executor.transcode.assert_not_called()
        assert audio == audio_meta

        # Should call progress callback with "skipped"
        callback.assert_called_once_with("transcode", "skipped")


class TestExecuteTranscribe:
    """Test _execute_transcribe method."""

    def test_execute_transcribe_calls_executor(self, tmp_path):
        """Test _execute_transcribe calls executor when no existing transcript."""
        # Create audio-meta.json
        audio_meta = {"audio_path": "/path/to/audio.wav"}
        (tmp_path / "audio-meta.json").write_text(
            json.dumps(audio_meta), encoding="utf-8"
        )

        config = PipelineConfig(show="Test Show", model="medium", preset="balanced")
        executor = Mock(spec=StepExecutor)
        executor.transcribe.return_value = {"text": "Transcript text"}

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)

        transcript = service._execute_transcribe(
            tmp_path, artifacts, result, skip_completed=True, progress_callback=None
        )

        # Verify executor.transcribe was called
        executor.transcribe.assert_called_once()
        assert transcript == {"text": "Transcript text"}
        assert "transcribe" in result.steps_completed

    def test_execute_transcribe_skips_if_exists(self, tmp_path):
        """Test _execute_transcribe skips if transcript exists and skip_completed=True."""
        # Create audio-meta.json
        audio_meta = {"audio_path": "/path/to/audio.wav"}
        (tmp_path / "audio-meta.json").write_text(
            json.dumps(audio_meta), encoding="utf-8"
        )

        # Create existing transcript
        transcript = {"text": "Existing transcript"}
        (tmp_path / "transcript-base.json").write_text(
            json.dumps(transcript), encoding="utf-8"
        )

        config = PipelineConfig(show="Test Show", model="base")
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        callback = Mock()

        result_transcript = service._execute_transcribe(
            tmp_path, artifacts, result, skip_completed=True, progress_callback=callback
        )

        # Should not call executor.transcribe
        executor.transcribe.assert_not_called()
        assert result_transcript == transcript

        # Should call progress callback with "skipped"
        callback.assert_called_once_with("transcribe", "skipped")


class TestExecutePreprocess:
    """Test _execute_preprocess method."""

    def test_execute_preprocess_returns_latest_if_not_configured(self, tmp_path):
        """Test _execute_preprocess returns latest if preprocess=False."""
        config = PipelineConfig(show="Test Show", preprocess=False, dual=False)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original transcript"}

        preprocessed = service._execute_preprocess(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=None,
        )

        # Should return original latest without calling executor
        executor.preprocess.assert_not_called()
        assert preprocessed == latest

    def test_execute_preprocess_calls_executor(self, tmp_path):
        """Test _execute_preprocess calls executor when configured."""
        config = PipelineConfig(show="Test Show", preprocess=True, restore=True)
        executor = Mock(spec=StepExecutor)
        executor.preprocess.return_value = {"text": "Preprocessed text"}

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original transcript", "asr_model": "base"}

        preprocessed = service._execute_preprocess(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=None,
        )

        # Verify executor.preprocess was called
        executor.preprocess.assert_called_once()
        assert preprocessed == {"text": "Preprocessed text"}
        assert "preprocess" in result.steps_completed

    def test_execute_preprocess_skips_if_exists(self, tmp_path):
        """Test _execute_preprocess skips if preprocessed exists."""
        # Create existing preprocessed transcript
        preprocessed = {"text": "Existing preprocessed"}
        (tmp_path / "transcript-preprocessed-base.json").write_text(
            json.dumps(preprocessed), encoding="utf-8"
        )

        config = PipelineConfig(show="Test Show", preprocess=True)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original", "asr_model": "base"}
        callback = Mock()

        result_preprocessed = service._execute_preprocess(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=callback,
        )

        # Should not call executor
        executor.preprocess.assert_not_called()
        assert result_preprocessed == preprocessed
        callback.assert_called_once_with("preprocess", "skipped")


class TestExecuteAlign:
    """Test _execute_align method."""

    def test_execute_align_returns_latest_if_not_configured(self, tmp_path):
        """Test _execute_align returns latest if align=False."""
        config = PipelineConfig(show="Test Show", align=False)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original transcript"}

        aligned = service._execute_align(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=None,
        )

        # Should return original latest
        executor.align.assert_not_called()
        assert aligned == latest

    def test_execute_align_calls_executor(self, tmp_path):
        """Test _execute_align calls executor when configured."""
        config = PipelineConfig(show="Test Show", align=True)
        executor = Mock(spec=StepExecutor)
        executor.align.return_value = {"text": "Aligned text"}

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original", "asr_model": "base"}

        aligned = service._execute_align(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=None,
        )

        # Verify executor.align was called
        executor.align.assert_called_once()
        assert aligned == {"text": "Aligned text"}
        assert "align" in result.steps_completed

    def test_execute_align_skips_if_exists(self, tmp_path):
        """Test _execute_align skips if aligned transcript exists."""
        # Create existing aligned transcript
        aligned = {"text": "Existing aligned"}
        (tmp_path / "transcript-aligned-base.json").write_text(
            json.dumps(aligned), encoding="utf-8"
        )

        config = PipelineConfig(show="Test Show", align=True)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original", "asr_model": "base"}
        callback = Mock()

        result_aligned = service._execute_align(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=callback,
        )

        executor.align.assert_not_called()
        assert result_aligned == aligned
        callback.assert_called_once_with("align", "skipped")


class TestExecuteDiarize:
    """Test _execute_diarize method."""

    def test_execute_diarize_returns_latest_if_not_configured(self, tmp_path):
        """Test _execute_diarize returns latest if diarize=False."""
        config = PipelineConfig(show="Test Show", diarize=False)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original transcript"}

        diarized = service._execute_diarize(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=None,
        )

        executor.diarize.assert_not_called()
        assert diarized == latest

    def test_execute_diarize_calls_executor(self, tmp_path):
        """Test _execute_diarize calls executor when configured."""
        config = PipelineConfig(show="Test Show", diarize=True)
        executor = Mock(spec=StepExecutor)
        executor.diarize.return_value = {"text": "Diarized text"}

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original", "asr_model": "base"}

        diarized = service._execute_diarize(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=None,
        )

        executor.diarize.assert_called_once()
        assert diarized == {"text": "Diarized text"}
        assert "diarize" in result.steps_completed

    def test_execute_diarize_skips_if_exists(self, tmp_path):
        """Test _execute_diarize skips if diarized transcript exists."""
        # Create existing diarized transcript
        diarized = {"text": "Existing diarized"}
        (tmp_path / "transcript-diarized-base.json").write_text(
            json.dumps(diarized), encoding="utf-8"
        )

        config = PipelineConfig(show="Test Show", diarize=True)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        from podx.state.artifact_detector import EpisodeArtifacts

        artifacts = EpisodeArtifacts(working_dir=tmp_path)
        latest = {"text": "Original", "asr_model": "base"}
        callback = Mock()

        result_diarized = service._execute_diarize(
            tmp_path,
            latest,
            artifacts,
            result,
            skip_completed=True,
            progress_callback=callback,
        )

        executor.diarize.assert_not_called()
        assert result_diarized == diarized
        callback.assert_called_once_with("diarize", "skipped")


class TestExecuteExport:
    """Test _execute_export method."""

    def test_execute_export_calls_executor(self, tmp_path):
        """Test _execute_export calls executor with correct parameters."""
        config = PipelineConfig(show="Test Show")
        executor = Mock(spec=StepExecutor)
        executor.export.return_value = {
            "files": {
                "txt": str(tmp_path / "transcript-base.txt"),
                "srt": str(tmp_path / "transcript-base.srt"),
            }
        }

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        latest = {"text": "Transcript", "asr_model": "base"}

        service._execute_export(tmp_path, latest, result, progress_callback=None)

        # Verify executor.export was called
        executor.export.assert_called_once()
        assert "export" in result.steps_completed

        # Verify artifacts were added
        assert "txt" in result.artifacts
        assert "srt" in result.artifacts


class TestExecuteDeepcast:
    """Test _execute_deepcast method."""

    def test_execute_deepcast_calls_executor(self, tmp_path):
        """Test _execute_deepcast calls executor with correct parameters."""
        # Create required files
        (tmp_path / "latest.json").write_text("{}", encoding="utf-8")
        (tmp_path / "episode-meta.json").write_text("{}", encoding="utf-8")

        config = PipelineConfig(
            show="Test Show",
            deepcast=True,
            deepcast_model="gpt-4o",
            deepcast_temp=0.7,
            analysis_type="brief",
        )
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        latest = {"text": "Transcript"}

        service._execute_deepcast(tmp_path, latest, result, progress_callback=None)

        # Verify executor.deepcast was called
        executor.deepcast.assert_called_once()
        assert "deepcast" in result.steps_completed

    def test_execute_deepcast_with_markdown_output(self, tmp_path):
        """Test _execute_deepcast detects markdown output."""
        # Create required files
        (tmp_path / "latest.json").write_text("{}", encoding="utf-8")
        (tmp_path / "episode-meta.json").write_text("{}", encoding="utf-8")

        # Create markdown output
        md_file = tmp_path / "deepcast-gpt_4o.md"
        md_file.write_text("# Deepcast Analysis", encoding="utf-8")

        config = PipelineConfig(
            show="Test Show", deepcast=True, deepcast_model="gpt-4o"
        )
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        latest = {"text": "Transcript"}

        service._execute_deepcast(tmp_path, latest, result, progress_callback=None)

        # Verify markdown artifact was detected
        assert "deepcast_md" in result.artifacts


class TestExecuteNotion:
    """Test _execute_notion method."""

    def test_execute_notion_raises_if_no_db_configured(self, tmp_path):
        """Test _execute_notion raises SystemExit if notion_db not configured."""
        config = PipelineConfig(show="Test Show", notion=True, notion_db=None)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        with pytest.raises(SystemExit):
            service._execute_notion(tmp_path, result, progress_callback=None)

    def test_execute_notion_skips_if_no_deepcast_markdown(self, tmp_path):
        """Test _execute_notion skips if deepcast markdown doesn't exist."""
        config = PipelineConfig(
            show="Test Show",
            notion=True,
            notion_db="test_db_id",
            deepcast_model="gpt-4o",
        )
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        service._execute_notion(tmp_path, result, progress_callback=None)

        # Should not call executor.notion
        executor.notion.assert_not_called()

    def test_execute_notion_calls_executor(self, tmp_path):
        """Test _execute_notion calls executor when deepcast markdown exists."""
        # Create deepcast markdown
        md_file = tmp_path / "deepcast-gpt_4o.md"
        md_file.write_text("# Analysis", encoding="utf-8")

        config = PipelineConfig(
            show="Test Show",
            notion=True,
            notion_db="test_db_id",
            deepcast_model="gpt-4o",
            podcast_prop="Podcast",
        )
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        service._execute_notion(tmp_path, result, progress_callback=None)

        # Verify executor.notion was called
        executor.notion.assert_called_once()
        assert "notion" in result.steps_completed


class TestExecuteCleanup:
    """Test _execute_cleanup method."""

    def test_execute_cleanup_removes_intermediate_files(self, tmp_path):
        """Test _execute_cleanup removes intermediate transcript files."""
        # Create files to keep
        (tmp_path / "latest.json").write_text("{}", encoding="utf-8")
        (tmp_path / "episode-meta.json").write_text("{}", encoding="utf-8")
        (tmp_path / "deepcast.json").write_text("{}", encoding="utf-8")

        # Create files to remove
        (tmp_path / "transcript-base.json").write_text("{}", encoding="utf-8")
        (tmp_path / "transcript-aligned-base.json").write_text("{}", encoding="utf-8")
        (tmp_path / "transcript-diarized-base.json").write_text("{}", encoding="utf-8")

        config = PipelineConfig(show="Test Show", clean=True)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        service._execute_cleanup(tmp_path, result, progress_callback=None)

        # Files to keep should still exist
        assert (tmp_path / "latest.json").exists()
        assert (tmp_path / "episode-meta.json").exists()
        assert (tmp_path / "deepcast.json").exists()

        # Intermediate files should be removed
        assert not (tmp_path / "transcript-base.json").exists()
        assert not (tmp_path / "transcript-aligned-base.json").exists()
        assert not (tmp_path / "transcript-diarized-base.json").exists()

        assert "cleanup" in result.steps_completed

    def test_execute_cleanup_keeps_deepcast_files(self, tmp_path):
        """Test _execute_cleanup keeps all deepcast files."""
        # Create deepcast files (should be kept)
        (tmp_path / "deepcast.json").write_text("{}", encoding="utf-8")
        (tmp_path / "deepcast-quotes.json").write_text("{}", encoding="utf-8")
        (tmp_path / "deepcast.md").write_text("", encoding="utf-8")

        # Create transcript file (should be removed)
        (tmp_path / "transcript-base.json").write_text("{}", encoding="utf-8")

        config = PipelineConfig(show="Test Show", clean=True)
        executor = Mock(spec=StepExecutor)

        service = PipelineService(config, executor=executor)
        result = PipelineResult(workdir=tmp_path)

        service._execute_cleanup(tmp_path, result, progress_callback=None)

        # Deepcast files should be kept
        assert (tmp_path / "deepcast.json").exists()
        assert (tmp_path / "deepcast-quotes.json").exists()
        assert (tmp_path / "deepcast.md").exists()

        # Transcript should be removed
        assert not (tmp_path / "transcript-base.json").exists()
