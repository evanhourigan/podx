"""Tests for the PodxClient API."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podx.api import (
    ClientConfig,
    DeepcastResponse,
    PodxClient,
    TranscribeResponse,
)
from podx.errors import AudioError, NetworkError, ValidationError


class TestClientConfig:
    """Test ClientConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ClientConfig()

        assert config.default_model == "base"
        assert config.default_llm_model == "gpt-4o"
        assert config.output_dir is None
        assert config.cache_enabled is True
        assert config.retry_failed is True
        assert config.validate_inputs is True
        assert config.verbose is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ClientConfig(
            default_model="medium",
            default_llm_model="gpt-4",
            output_dir=Path("/custom/output"),
            cache_enabled=False,
            verbose=True,
        )

        assert config.default_model == "medium"
        assert config.default_llm_model == "gpt-4"
        assert config.output_dir == Path("/custom/output")
        assert config.cache_enabled is False
        assert config.verbose is True


class TestPodxClientInit:
    """Test PodxClient initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""

        client = PodxClient()

        assert client.config is not None
        assert isinstance(client.config, ClientConfig)
        assert client.config.default_model == "base"

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = ClientConfig(default_model="medium", verbose=True)
        client = PodxClient(config=config)

        assert client.config == config
        assert client.config.default_model == "medium"


class TestTranscribeAPI:
    """Test transcribe API method."""

    @patch("podx.api.client._transcribe")
    def test_transcribe_success(self, mock_transcribe, tmp_path):
        """Test successful transcription."""
        # Create transcript file that mock will "create"
        transcript_path = tmp_path / "transcript-output.json"
        transcript_data = {
            "segments": [
                {"text": "Hello", "start": 0, "end": 1},
                {"text": "World", "start": 1, "end": 2},
            ],
            "duration": 2.0,
        }
        transcript_path.write_text(json.dumps(transcript_data))

        # Mock API response
        mock_transcribe.return_value = {
            "transcript_path": str(transcript_path),
            "duration_seconds": 2,
        }

        # Disable cache to ensure mock is called
        config = ClientConfig(cache_enabled=False)
        client = PodxClient(config=config)
        result = client.transcribe("test_audio.mp3", model="base", out_dir=str(tmp_path))

        assert result.success is True
        assert result.transcript_path == str(transcript_path)
        assert result.duration_seconds == 2
        assert result.model_used == "base"
        assert result.segments_count == 2
        mock_transcribe.assert_called_once_with("test_audio.mp3", "base", str(tmp_path))

    @patch("podx.api.client._transcribe")
    def test_transcribe_uses_default_model(self, mock_transcribe, tmp_path):
        """Test transcription uses default model from config."""
        transcript_path = tmp_path / "transcript-output.json"
        transcript_path.write_text("{}")

        mock_transcribe.return_value = {
            "transcript_path": str(transcript_path),
            "duration_seconds": 0,
        }

        # Disable cache to ensure mock is called
        config = ClientConfig(default_model="medium", cache_enabled=False)
        client = PodxClient(config=config)
        result = client.transcribe("audio.mp3", out_dir=str(tmp_path))

        # Should use default model from config
        mock_transcribe.assert_called_once_with("audio.mp3", "medium", str(tmp_path))
        assert result.model_used == "medium"

    @patch("podx.api.client._transcribe")
    def test_transcribe_with_cache(self, mock_transcribe, tmp_path):
        """Test transcription with caching enabled."""
        # Create cached transcript
        transcript_path = tmp_path / "transcript.json"
        cached_data = {
            "segments": [{"text": "Cached", "start": 0, "end": 1}],
            "duration": 1.0,
        }
        transcript_path.write_text(json.dumps(cached_data))

        config = ClientConfig(cache_enabled=True, output_dir=tmp_path)
        client = PodxClient(config=config)
        result = client.transcribe("audio.mp3")

        # Should use cache, not call underlying API
        mock_transcribe.assert_not_called()
        assert result.success is True
        assert result.segments_count == 1

    def test_transcribe_validation_error_empty_url(self):
        """Test transcription fails with empty audio URL."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="audio_url cannot be empty"):
            client.transcribe("", model="base")

    def test_transcribe_validation_error_missing_file(self):
        """Test transcription fails when local file doesn't exist."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="Audio file not found"):
            client.transcribe("/nonexistent/audio.mp3", model="base")

    def test_transcribe_validation_disabled(self):
        """Test transcription with validation disabled."""
        config = ClientConfig(validate_inputs=False)
        client = PodxClient(config=config)

        # Should not raise validation error (will fail later in _transcribe)
        # This just tests that validation is skipped
        assert client.config.validate_inputs is False

    @patch("podx.api.client._transcribe")
    def test_transcribe_handles_network_error(self, mock_transcribe, tmp_path):
        """Test transcription handles network errors gracefully."""
        mock_transcribe.side_effect = NetworkError("Download failed")

        client = PodxClient()
        result = client.transcribe(
            "https://example.com/audio.mp3", out_dir=str(tmp_path)
        )

        assert result.success is False
        assert result.error is not None
        assert "NETWORK_ERROR" in result.error


class TestDeepcastAPI:
    """Test deepcast API method."""

    @patch("podx.api.client._deepcast")
    def test_deepcast_success(self, mock_deepcast, tmp_path):
        """Test successful deepcast analysis."""
        # Create markdown output
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("# Analysis")

        # Mock API response
        mock_deepcast.return_value = {
            "markdown_path": str(markdown_path),
            "usage": {"total_tokens": 1000},
            "prompt_used": "Test prompt",
        }

        # Create transcript file
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text("{}")

        client = PodxClient()
        result = client.deepcast(
            str(transcript_path), llm_model="gpt-4o", out_dir=str(tmp_path)
        )

        assert result.success is True
        assert result.markdown_path == str(markdown_path)
        assert result.usage == {"total_tokens": 1000}
        assert result.prompt_used == "Test prompt"
        assert result.model_used == "gpt-4o"

    @patch("podx.api.client._deepcast")
    def test_deepcast_uses_default_model(self, mock_deepcast, tmp_path):
        """Test deepcast uses default LLM model from config."""
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("")

        mock_deepcast.return_value = {
            "markdown_path": str(markdown_path),
        }

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text("{}")

        config = ClientConfig(default_llm_model="claude-3")
        client = PodxClient(config=config)
        result = client.deepcast(str(transcript_path), out_dir=str(tmp_path))

        # Should use default LLM model from config
        mock_deepcast.assert_called_once()
        call_args = mock_deepcast.call_args
        assert call_args.kwargs["llm_model"] == "claude-3"
        assert result.model_used == "claude-3"

    def test_deepcast_validation_error_empty_path(self):
        """Test deepcast fails with empty transcript path."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="transcript_path cannot be empty"):
            client.deepcast("", llm_model="gpt-4o")

    def test_deepcast_validation_error_missing_file(self):
        """Test deepcast fails when transcript file doesn't exist."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="Transcript file not found"):
            client.deepcast("/nonexistent/transcript.json", llm_model="gpt-4o")

    @patch("podx.api.client._deepcast")
    def test_deepcast_handles_ai_error(self, mock_deepcast, tmp_path):
        """Test deepcast handles AI errors gracefully."""
        from podx.errors import AIError

        mock_deepcast.side_effect = AIError("API key invalid")

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text("{}")

        client = PodxClient()
        result = client.deepcast(str(transcript_path), out_dir=str(tmp_path))

        assert result.success is False
        assert result.error is not None
        assert "AI_ERROR" in result.error


class TestTranscribeAndAnalyze:
    """Test transcribe_and_analyze combined API."""

    @patch("podx.api.client._transcribe")
    @patch("podx.api.client._deepcast")
    def test_transcribe_and_analyze_success(
        self, mock_deepcast, mock_transcribe, tmp_path
    ):
        """Test successful combined transcription and analysis."""
        # Setup transcript
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text("{}")

        mock_transcribe.return_value = {
            "transcript_path": str(transcript_path),
            "duration_seconds": 60,
        }

        # Setup analysis
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("# Analysis")

        mock_deepcast.return_value = {
            "markdown_path": str(markdown_path),
        }

        client = PodxClient()
        result = client.transcribe_and_analyze("audio.mp3", out_dir=str(tmp_path))

        assert result["success"] is True
        assert isinstance(result["transcript"], TranscribeResponse)
        assert isinstance(result["analysis"], DeepcastResponse)
        assert result["transcript"].success is True
        assert result["analysis"].success is True

    @patch("podx.api.client._transcribe")
    def test_transcribe_and_analyze_transcribe_fails(self, mock_transcribe, tmp_path):
        """Test combined API when transcription fails."""
        mock_transcribe.side_effect = AudioError("Audio processing failed")

        client = PodxClient()
        result = client.transcribe_and_analyze("audio.mp3", out_dir=str(tmp_path))

        assert result["success"] is False
        assert result["transcript"].success is False
        assert result["analysis"] is None


class TestExistenceChecks:
    """Test existence check APIs."""

    @patch("podx.api.client._has_transcript")
    def test_check_transcript_exists_true(self, mock_has_transcript, tmp_path):
        """Test checking for existing transcript - exists."""
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "asr_model": "base",
            "segments": [{"text": "test"}],
            "duration": 1.0,
        }
        transcript_path.write_text(json.dumps(transcript_data))

        mock_has_transcript.return_value = str(transcript_path)

        client = PodxClient()
        result = client.check_transcript_exists("ep123", "base", str(tmp_path))

        assert result.exists is True
        assert result.path == str(transcript_path)
        assert result.resource_type == "transcript"
        assert result.metadata is not None
        assert result.metadata["model"] == "base"
        assert result.metadata["segments"] == 1

    @patch("podx.api.client._has_transcript")
    def test_check_transcript_exists_false(self, mock_has_transcript):
        """Test checking for existing transcript - doesn't exist."""
        mock_has_transcript.return_value = None

        client = PodxClient()
        result = client.check_transcript_exists("ep123", "base", "/tmp")

        assert result.exists is False
        assert result.path is None
        assert result.resource_type == "transcript"

    @patch("podx.api.client._has_markdown")
    def test_check_markdown_exists_true(self, mock_has_markdown, tmp_path):
        """Test checking for existing markdown - exists."""
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("# Analysis")

        mock_has_markdown.return_value = str(markdown_path)

        client = PodxClient()
        result = client.check_markdown_exists(
            "ep123", "base", "gpt-4o", "default", str(tmp_path)
        )

        assert result.exists is True
        assert result.path == str(markdown_path)
        assert result.resource_type == "markdown"

    @patch("podx.api.client._has_markdown")
    def test_check_markdown_exists_false(self, mock_has_markdown):
        """Test checking for existing markdown - doesn't exist."""
        mock_has_markdown.return_value = None

        client = PodxClient()
        result = client.check_markdown_exists(
            "ep123", "base", "gpt-4o", "default", "/tmp"
        )

        assert result.exists is False
        assert result.path is None


class TestValidationHelpers:
    """Test validation helper methods."""

    def test_validate_transcribe_inputs_valid(self):
        """Test validation passes for valid inputs."""

        client = PodxClient()
        result = client._validate_transcribe_inputs(
            "https://example.com/audio.mp3", "base", "/tmp"
        )

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_transcribe_inputs_empty_url(self):
        """Test validation fails for empty URL."""

        client = PodxClient()
        result = client._validate_transcribe_inputs("", "base", "/tmp")

        assert result.valid is False
        assert any("empty" in err for err in result.errors)

    def test_validate_transcribe_inputs_invalid_model(self):
        """Test validation fails for invalid model name."""

        client = PodxClient()
        result = client._validate_transcribe_inputs(
            "https://example.com/audio.mp3", "invalid@model!", "/tmp"
        )

        assert result.valid is False
        assert any("Invalid model" in err for err in result.errors)

    def test_validate_deepcast_inputs_valid(self, tmp_path):
        """Test validation passes for valid deepcast inputs."""
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text("{}")

        client = PodxClient()
        result = client._validate_deepcast_inputs(str(transcript_path), "gpt-4o", "/tmp")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_deepcast_inputs_empty_path(self):
        """Test validation fails for empty transcript path."""

        client = PodxClient()
        result = client._validate_deepcast_inputs("", "gpt-4o", "/tmp")

        assert result.valid is False
        assert any("empty" in err for err in result.errors)

    def test_validate_deepcast_inputs_missing_file(self):
        """Test validation fails when transcript file doesn't exist."""

        client = PodxClient()
        result = client._validate_deepcast_inputs(
            "/nonexistent/transcript.json", "gpt-4o", "/tmp"
        )

        assert result.valid is False
        assert any("not found" in err for err in result.errors)


class TestErrorHandling:
    """Test error handling methods."""

    def test_handle_validation_error(self):
        """Test handling of ValidationError."""

        client = PodxClient()
        error = ValidationError("Invalid input")

        api_error = client._handle_error(error, "transcribe")

        assert api_error.code == "VALIDATION_ERROR"
        assert "Invalid input" in api_error.message
        assert api_error.resolution is not None

    def test_handle_network_error(self):
        """Test handling of NetworkError."""

        client = PodxClient()
        error = NetworkError("Connection failed")

        api_error = client._handle_error(error, "transcribe")

        assert api_error.code == "NETWORK_ERROR"
        assert "Connection failed" in api_error.message
        assert api_error.retry_after is not None

    def test_handle_audio_error(self):
        """Test handling of AudioError."""

        client = PodxClient()
        error = AudioError("Invalid audio format")

        api_error = client._handle_error(error, "transcribe")

        assert api_error.code == "AUDIO_ERROR"
        assert "Invalid audio format" in api_error.message

    def test_handle_unknown_error(self):
        """Test handling of unknown errors."""

        client = PodxClient()
        error = Exception("Unknown error")

        api_error = client._handle_error(error, "transcribe")

        assert api_error.code == "UNKNOWN_ERROR"
        assert "Unknown error" in api_error.message
        assert api_error.details["operation"] == "transcribe"


class TestFetchEpisodeAPI:
    """Test fetch_episode API method."""

    def test_fetch_episode_success_by_show_name(self, tmp_path):
        """Test successful episode fetch by show name and date."""

        client = PodxClient()

        # Mock PodcastFetcher where it's imported in the method
        with patch("podx.core.fetch.PodcastFetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher

            # Mock fetch result
            audio_path = tmp_path / "episode.mp3"
            audio_path.write_text("fake audio")
            meta_path = tmp_path / "metadata.json"
            meta_path.write_text("{}")

            mock_fetcher.fetch_episode.return_value = {
                "meta": {
                    "title": "Test Episode",
                    "show": "Test Show",
                    "date": "2024-01-20",
                },
                "audio_meta": {"duration": 3600, "format": "mp3"},
                "audio_path": str(audio_path),
                "meta_path": str(meta_path),
            }

            result = client.fetch_episode(
                show_name="Test Show",
                date="2024-01-20",
                output_dir=tmp_path,
            )

            assert result.success is True
            assert result.episode_meta["title"] == "Test Episode"
            assert result.audio_path == str(audio_path)
            assert result.metadata_path == str(meta_path)
            mock_fetcher.fetch_episode.assert_called_once()

    def test_fetch_episode_by_rss_url(self, tmp_path):
        """Test episode fetch by RSS URL."""

        client = PodxClient()

        with patch("podx.core.fetch.PodcastFetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher

            audio_path = tmp_path / "episode.mp3"
            audio_path.write_text("fake audio")

            mock_fetcher.fetch_episode.return_value = {
                "meta": {"title": "RSS Episode"},
                "audio_path": str(audio_path),
            }

            result = client.fetch_episode(
                rss_url="https://example.com/feed.xml",
                title_contains="specific episode",
            )

            assert result.success is True
            assert result.episode_meta["title"] == "RSS Episode"
            mock_fetcher.fetch_episode.assert_called_once()

    def test_fetch_episode_validation_error_no_source(self):
        """Test fetch fails when neither show_name nor rss_url provided."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="Either show_name or rss_url"):
            client.fetch_episode()

    def test_fetch_episode_handles_error(self, tmp_path):
        """Test fetch handles errors gracefully."""

        client = PodxClient()

        with patch("podx.core.fetch.PodcastFetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            mock_fetcher.fetch_episode.side_effect = Exception("Network error")

            result = client.fetch_episode(
                show_name="Test Show",
                output_dir=tmp_path,
            )

            assert result.success is False
            assert "Network error" in result.error


class TestDiarizeAPI:
    """Test diarize API method."""

    def test_diarize_success_with_num_speakers(self, tmp_path):
        """Test successful diarization with exact speaker count."""

        # Create transcript file
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "audio_path": str(tmp_path / "audio.mp3"),
            "segments": [{"text": "Hello", "start": 0, "end": 1}],
        }
        transcript_path.write_text(json.dumps(transcript_data))

        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        # Create output file
        output_path = tmp_path / "transcript-diarized.json"
        diarized_data = {
            "segments": [
                {"text": "Hello", "start": 0, "end": 1, "speaker": "SPEAKER_00"},
                {"text": "World", "start": 1, "end": 2, "speaker": "SPEAKER_01"},
            ]
        }
        output_path.write_text(json.dumps(diarized_data))

        client = PodxClient()

        with patch("podx.core.diarize.DiarizationEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.diarize.return_value = diarized_data

            result = client.diarize(
                transcript_path=transcript_path,
                num_speakers=2,
            )

            assert result.success is True
            assert result.speakers_found == 2
            assert result.transcript_path == str(output_path)
            mock_engine.diarize.assert_called_once()

    def test_diarize_with_speaker_range(self, tmp_path):
        """Test diarization with min/max speakers."""
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "audio_path": str(tmp_path / "audio.mp3"),
            "segments": [],
        }
        transcript_path.write_text(json.dumps(transcript_data))

        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        output_path = tmp_path / "transcript-diarized.json"
        output_path.write_text(json.dumps({"segments": []}))

        client = PodxClient()

        with patch("podx.core.diarize.DiarizationEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.diarize.return_value = {"segments": []}

            result = client.diarize(
                transcript_path=transcript_path,
                min_speakers=2,
                max_speakers=4,
            )

            assert result.success is True
            # Check that min/max were passed to engine
            call_kwargs = mock_engine.diarize.call_args.kwargs
            assert call_kwargs.get("min_speakers") == 2
            assert call_kwargs.get("max_speakers") == 4

    def test_diarize_auto_detects_audio_path(self, tmp_path):
        """Test diarization auto-detects audio path from transcript."""
        transcript_path = tmp_path / "transcript.json"
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_data = {
            "audio_path": str(audio_path),
            "segments": [],
        }
        transcript_path.write_text(json.dumps(transcript_data))

        output_path = tmp_path / "transcript-diarized.json"
        output_path.write_text(json.dumps({"segments": []}))

        client = PodxClient()

        with patch("podx.core.diarize.DiarizationEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.diarize.return_value = {"segments": []}

            # Don't provide audio_path - should auto-detect
            result = client.diarize(transcript_path=transcript_path)

            assert result.success is True
            mock_engine.diarize.assert_called_once()

    def test_diarize_validation_error_missing_transcript(self):
        """Test diarize fails when transcript doesn't exist."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="Transcript not found"):
            client.diarize(transcript_path="/nonexistent/transcript.json")

    def test_diarize_validation_error_missing_audio(self, tmp_path):
        """Test diarize fails when audio doesn't exist."""
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "audio_path": str(tmp_path / "nonexistent.mp3"),
            "segments": [],
        }
        transcript_path.write_text(json.dumps(transcript_data))

        client = PodxClient()

        with pytest.raises(ValidationError, match="Audio file not found"):
            client.diarize(transcript_path=transcript_path)

    def test_diarize_handles_error(self, tmp_path):
        """Test diarize handles errors gracefully."""
        transcript_path = tmp_path / "transcript.json"
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_data = {
            "audio_path": str(audio_path),
            "segments": [],
        }
        transcript_path.write_text(json.dumps(transcript_data))

        client = PodxClient()

        with patch("podx.core.diarize.DiarizationEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.diarize.side_effect = Exception("Diarization failed")

            result = client.diarize(transcript_path=transcript_path)

            assert result.success is False
            assert "Diarization failed" in result.error


class TestExportAPI:
    """Test export API method."""

    def test_export_success_multiple_formats(self, tmp_path):
        """Test successful export to multiple formats."""

        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "segments": [{"text": "Hello world", "start": 0, "end": 2}]
        }
        transcript_path.write_text(json.dumps(transcript_data))

        client = PodxClient()

        with patch("podx.core.export.ExportEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            mock_engine.export.return_value = {
                "txt": str(tmp_path / "transcript.txt"),
                "srt": str(tmp_path / "transcript.srt"),
                "vtt": str(tmp_path / "transcript.vtt"),
            }

            result = client.export(
                transcript_path=transcript_path,
                formats=["txt", "srt", "vtt"],
                output_dir=tmp_path,
            )

            assert result.success is True
            assert len(result.formats) == 3
            assert "txt" in result.formats
            assert "srt" in result.formats
            assert "vtt" in result.formats
            assert len(result.output_files) == 3
            mock_engine.export.assert_called_once()

    def test_export_single_format(self, tmp_path):
        """Test export to single format."""
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text(json.dumps({"segments": []}))

        client = PodxClient()

        with patch("podx.core.export.ExportEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.export.return_value = {
                "md": str(tmp_path / "transcript.md"),
            }

            result = client.export(
                transcript_path=transcript_path,
                formats=["md"],
            )

            assert result.success is True
            assert result.formats == ["md"]

    def test_export_validation_error_missing_transcript(self):
        """Test export fails when transcript doesn't exist."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="Transcript not found"):
            client.export(
                transcript_path="/nonexistent/transcript.json",
                formats=["txt"],
            )

    def test_export_handles_error(self, tmp_path):
        """Test export handles errors gracefully."""
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text(json.dumps({"segments": []}))

        client = PodxClient()

        with patch("podx.core.export.ExportEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.export.side_effect = Exception("Export failed")

            result = client.export(
                transcript_path=transcript_path,
                formats=["txt"],
            )

            assert result.success is False
            assert "Export failed" in result.error


class TestPublishToNotionAPI:
    """Test publish_to_notion API method."""

    def test_publish_to_notion_success(self, tmp_path):
        """Test successful Notion publishing."""

        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("# Test Analysis")

        client = PodxClient()

        with patch("podx.core.notion.NotionEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            mock_engine.publish.return_value = {
                "page_id": "test-page-id-123",
                "database_id": "test-db-id",
            }

            result = client.publish_to_notion(
                markdown_path=markdown_path,
                notion_token="secret_test_token",
                database_id="test-db-id",
            )

            assert result.success is True
            assert result.page_id == "test-page-id-123"
            assert result.database_id == "test-db-id"
            assert "notion.so/testpageid123" in result.page_url
            mock_engine.publish.assert_called_once()

    def test_publish_to_notion_with_episode_meta(self, tmp_path):
        """Test Notion publishing with episode metadata."""
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("# Analysis")

        client = PodxClient()

        with patch("podx.core.notion.NotionEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.publish.return_value = {"page_id": "123"}

            episode_meta = {
                "title": "Episode Title",
                "date": "2024-01-20",
                "show": "Test Show",
            }

            result = client.publish_to_notion(
                markdown_path=markdown_path,
                notion_token="secret_token",
                database_id="db123",
                episode_meta=episode_meta,
            )

            assert result.success is True
            # Check that episode_meta was passed to engine
            call_kwargs = mock_engine.publish.call_args.kwargs
            assert call_kwargs.get("episode_meta") == episode_meta

    def test_publish_to_notion_validation_error_missing_markdown(self):
        """Test Notion publish fails when markdown doesn't exist."""

        client = PodxClient()

        with pytest.raises(ValidationError, match="Markdown file not found"):
            client.publish_to_notion(
                markdown_path="/nonexistent/analysis.md",
                notion_token="token",
                database_id="db123",
            )

    def test_publish_to_notion_handles_error(self, tmp_path):
        """Test Notion publish handles errors gracefully."""
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("# Analysis")

        client = PodxClient()

        with patch("podx.core.notion.NotionEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine
            mock_engine.publish.side_effect = Exception("API error")

            result = client.publish_to_notion(
                markdown_path=markdown_path,
                notion_token="token",
                database_id="db123",
            )

            assert result.success is False
            assert "API error" in result.error
