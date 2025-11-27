"""Tests for the PodxClient API."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podx.api import (
    ClientConfig,
    CostEstimate,
    DeepcastResponse,
    ModelInfo,
    ModelPricingInfo,
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

    @patch("podx.api.sync_client._transcribe")
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
        result = client.transcribe(
            "test_audio.mp3", model="base", out_dir=str(tmp_path)
        )

        assert result.success is True
        assert result.transcript_path == str(transcript_path)
        assert result.duration_seconds == 2
        assert result.model_used == "base"
        assert result.segments_count == 2
        mock_transcribe.assert_called_once_with("test_audio.mp3", "base", str(tmp_path))

    @patch("podx.api.sync_client._transcribe")
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

    @patch("podx.api.sync_client._transcribe")
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

    def test_transcribe_validation_error_missing_file(self, tmp_path):
        """Test transcription fails when local file doesn't exist."""

        client = PodxClient()
        # Use tmp_path to ensure cross-platform non-existent file
        nonexistent = tmp_path / "definitely_does_not_exist_12345.mp3"

        with pytest.raises(ValidationError, match="Audio file not found"):
            client.transcribe(str(nonexistent), model="base")

    def test_transcribe_validation_disabled(self):
        """Test transcription with validation disabled."""
        config = ClientConfig(validate_inputs=False)
        client = PodxClient(config=config)

        # Should not raise validation error (will fail later in _transcribe)
        # This just tests that validation is skipped
        assert client.config.validate_inputs is False

    @patch("podx.api.sync_client._transcribe")
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
    """Test deepcast API method (backwards compatibility)."""

    @patch("podx.api.sync_client._analyze")
    def test_deepcast_success(self, mock_analyze, tmp_path):
        """Test successful deepcast analysis."""
        # Create markdown output
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("# Analysis")

        # Mock API response
        mock_analyze.return_value = {
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

    @patch("podx.api.sync_client._analyze")
    def test_deepcast_uses_default_model(self, mock_analyze, tmp_path):
        """Test deepcast uses default LLM model from config."""
        markdown_path = tmp_path / "analysis.md"
        markdown_path.write_text("")

        mock_analyze.return_value = {
            "markdown_path": str(markdown_path),
        }

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text("{}")

        config = ClientConfig(default_llm_model="claude-3")
        client = PodxClient(config=config)
        result = client.deepcast(str(transcript_path), out_dir=str(tmp_path))

        # Should use default LLM model from config
        mock_analyze.assert_called_once()
        call_args = mock_analyze.call_args
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

    @patch("podx.api.sync_client._analyze")
    def test_deepcast_handles_ai_error(self, mock_analyze, tmp_path):
        """Test deepcast handles AI errors gracefully."""
        from podx.errors import AIError

        mock_analyze.side_effect = AIError("API key invalid")

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text("{}")

        client = PodxClient()
        result = client.deepcast(str(transcript_path), out_dir=str(tmp_path))

        assert result.success is False
        assert result.error is not None
        assert "AI_ERROR" in result.error


class TestTranscribeAndAnalyze:
    """Test transcribe_and_analyze combined API."""

    @patch("podx.api.sync_client._transcribe")
    @patch("podx.api.sync_client._analyze")
    def test_transcribe_and_analyze_success(
        self, mock_analyze, mock_transcribe, tmp_path
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

        mock_analyze.return_value = {
            "markdown_path": str(markdown_path),
        }

        client = PodxClient()
        result = client.transcribe_and_analyze("audio.mp3", out_dir=str(tmp_path))

        assert result["success"] is True
        assert isinstance(result["transcript"], TranscribeResponse)
        assert isinstance(result["analysis"], DeepcastResponse)
        assert result["transcript"].success is True
        assert result["analysis"].success is True

    @patch("podx.api.sync_client._transcribe")
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

    @patch("podx.api.sync_client._has_transcript")
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

    @patch("podx.api.sync_client._has_transcript")
    def test_check_transcript_exists_false(self, mock_has_transcript):
        """Test checking for existing transcript - doesn't exist."""
        mock_has_transcript.return_value = None

        client = PodxClient()
        result = client.check_transcript_exists("ep123", "base", "/tmp")

        assert result.exists is False
        assert result.path is None
        assert result.resource_type == "transcript"

    @patch("podx.api.sync_client._has_markdown")
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

    @patch("podx.api.sync_client._has_markdown")
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
        result = client._validate_deepcast_inputs(
            str(transcript_path), "gpt-4o", "/tmp"
        )

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

    @patch("podx.core.fetch.PodcastFetcher")
    def test_fetch_episode_by_show_name(self, mock_fetcher_class, tmp_path):
        """Test fetching episode by show name."""
        # Setup mock
        audio_path = tmp_path / "episode.mp3"
        audio_path.write_text("fake audio")
        meta_path = tmp_path / "episode.json"
        meta_path.write_text('{"title": "Test Episode"}')

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_episode.return_value = {
            "audio_path": str(audio_path),
            "meta_path": str(meta_path),
            "meta": {"title": "Test Episode"},
        }
        mock_fetcher_class.return_value = mock_fetcher

        client = PodxClient()
        result = client.fetch_episode(
            show_name="Test Show", date="latest", output_dir=tmp_path
        )

        assert result.success is True
        assert result.audio_path == str(audio_path)
        assert result.episode_meta["title"] == "Test Episode"

    @patch("podx.core.fetch.PodcastFetcher")
    def test_fetch_episode_by_rss_url(self, mock_fetcher_class, tmp_path):
        """Test fetching episode by RSS URL."""
        audio_path = tmp_path / "episode.mp3"
        audio_path.write_text("fake audio")

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_episode.return_value = {
            "audio_path": str(audio_path),
            "meta": {"title": "RSS Episode"},
        }
        mock_fetcher_class.return_value = mock_fetcher

        client = PodxClient()
        result = client.fetch_episode(
            rss_url="https://example.com/feed.rss", output_dir=tmp_path
        )

        assert result.success is True
        assert result.audio_path == str(audio_path)

    def test_fetch_episode_validation_error(self):
        """Test fetch_episode raises ValidationError with no show_name or rss_url."""
        client = PodxClient()

        # Should raise validation error
        with pytest.raises(
            ValidationError, match="Either show_name or rss_url must be provided"
        ):
            client.fetch_episode()

    @patch("podx.core.fetch.PodcastFetcher")
    def test_fetch_episode_handles_network_error(self, mock_fetcher_class):
        """Test fetch_episode handles network errors gracefully."""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_episode.side_effect = NetworkError("Failed to download")
        mock_fetcher_class.return_value = mock_fetcher

        client = PodxClient()
        result = client.fetch_episode(show_name="Test Show")

        assert result.success is False
        assert result.error is not None


class TestDiarizeAPI:
    """Test diarize API method."""

    @patch("podx.core.diarize.DiarizationEngine")
    def test_diarize_success(self, mock_engine_class, tmp_path):
        """Test successful diarization."""
        # Create input transcript
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "segments": [{"text": "Hello world", "start": 0.0, "end": 2.0}],
            "asr_model": "base",
        }
        transcript_path.write_text(json.dumps(transcript_data))

        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        # Create diarized output
        diarized_path = tmp_path / "transcript-diarized.json"
        diarized_data = {
            "segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                    "speaker": "SPEAKER_00",
                }
            ]
        }
        diarized_path.write_text(json.dumps(diarized_data))

        # Mock engine
        mock_engine = MagicMock()
        mock_engine.diarize.return_value = diarized_data["segments"]
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.diarize(
            transcript_path=transcript_path, audio_path=audio_path, output_dir=tmp_path
        )

        assert result.success is True
        assert result.speakers_found == 1
        assert "_diarized" in result.transcript_path

    @patch("podx.core.diarize.DiarizationEngine")
    def test_diarize_with_language(self, mock_engine_class, tmp_path):
        """Test diarization with language specified."""
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": [], "asr_model": "base"}')
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        mock_engine = MagicMock()
        mock_engine.diarize.return_value = []
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.diarize(
            transcript_path=transcript_path,
            audio_path=audio_path,
            language="es",
            output_dir=tmp_path,
        )

        assert result.success is True
        # Verify language was passed to engine constructor
        assert mock_engine_class.call_args.kwargs["language"] == "es"

    def test_diarize_validation_error_missing_transcript(self):
        """Test diarization raises ValidationError when transcript doesn't exist."""
        client = PodxClient()

        with pytest.raises(ValidationError, match="Transcript file not found"):
            client.diarize(
                transcript_path=Path("/nonexistent/transcript.json"),
                audio_path=Path("/tmp/audio.mp3"),
            )

    def test_diarize_validation_error_missing_audio(self, tmp_path):
        """Test diarization handles missing audio file gracefully."""
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text(
            '{"segments": [], "asr_model": "base", "audio_path": "/nonexistent/audio.mp3"}'
        )

        client = PodxClient()
        result = client.diarize(transcript_path=transcript_path)

        assert result.success is False
        assert result.error is not None
        assert "Audio file not found" in result.error

    @patch("podx.core.diarize.DiarizationEngine")
    def test_diarize_handles_audio_error(self, mock_engine_class, tmp_path):
        """Test diarization handles audio errors gracefully."""
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": [], "asr_model": "base"}')
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        mock_engine = MagicMock()
        mock_engine.diarize.side_effect = AudioError("Invalid audio format")
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.diarize(
            transcript_path=transcript_path, audio_path=audio_path, output_dir=tmp_path
        )

        assert result.success is False
        assert result.error is not None

    @patch("podx.core.diarize.DiarizationEngine")
    def test_diarize_loads_transcript_metadata(self, mock_engine_class, tmp_path):
        """Test that diarize loads transcript metadata into response."""
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "segments": [{"text": "Test", "start": 0.0, "end": 1.0}],
            "asr_model": "base",
            "language": "en",
        }
        transcript_path.write_text(json.dumps(transcript_data))

        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        mock_engine = MagicMock()
        mock_engine.diarize.return_value = [
            {"text": "Test", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}
        ]
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.diarize(
            transcript_path=transcript_path, audio_path=audio_path, output_dir=tmp_path
        )

        assert result.success is True
        assert result.transcript is not None
        assert len(result.transcript["segments"]) == 1


class TestExportAPI:
    """Test export API method."""

    @patch("podx.core.export.ExportEngine")
    def test_export_success_multiple_formats(self, mock_engine_class, tmp_path):
        """Test successful export to multiple formats."""
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {"segments": [{"text": "Test", "start": 0.0, "end": 1.0}]}
        transcript_path.write_text(json.dumps(transcript_data))

        # Mock export engine
        mock_engine = MagicMock()
        mock_engine.export.return_value = {
            "txt": str(tmp_path / "transcript.txt"),
            "srt": str(tmp_path / "transcript.srt"),
            "vtt": str(tmp_path / "transcript.vtt"),
        }
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.export(
            transcript_path=transcript_path,
            formats=["txt", "srt", "vtt"],
            output_dir=tmp_path,
        )

        assert result.success is True
        assert len(result.output_files) == 3
        assert "txt" in result.output_files
        assert "srt" in result.output_files
        assert "vtt" in result.output_files

    @patch("podx.core.export.ExportEngine")
    def test_export_single_format(self, mock_engine_class, tmp_path):
        """Test export to single format."""
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": []}')

        mock_engine = MagicMock()
        mock_engine.export.return_value = {"md": str(tmp_path / "transcript.md")}
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.export(
            transcript_path=transcript_path, formats=["md"], output_dir=tmp_path
        )

        assert result.success is True
        assert len(result.output_files) == 1
        assert "md" in result.formats

    def test_export_validation_error_missing_file(self):
        """Test export raises ValidationError when transcript doesn't exist."""
        client = PodxClient()

        with pytest.raises(ValidationError, match="Transcript file not found"):
            client.export(
                transcript_path=Path("/nonexistent/transcript.json"), formats=["txt"]
            )


class TestPublishToNotionAPI:
    """Test publish_to_notion API method."""

    @patch("podx.core.notion.NotionEngine")
    def test_publish_to_notion_success(self, mock_engine_class, tmp_path):
        """Test successful Notion publishing."""
        deepcast_path = tmp_path / "deepcast.json"
        deepcast_data = {
            "markdown": "# Test Episode",
            "metadata": {
                "episode_title": "Test Episode",
                "show": "Test Show",
            },
        }
        deepcast_path.write_text(json.dumps(deepcast_data))

        mock_engine = MagicMock()
        mock_engine.create_page.return_value = "page-123-id"
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.publish_to_notion(
            deepcast_path=deepcast_path,
            database_id="db123",
            notion_token="secret_token",
        )

        assert result.success is True
        assert "notion.so" in result.page_url
        assert result.page_id == "page-123-id"

    @patch("podx.core.notion.NotionEngine")
    @patch.dict("os.environ", {"NOTION_TOKEN": "env_token"})
    def test_publish_to_notion_uses_env_token(self, mock_engine_class, tmp_path):
        """Test Notion publishing uses environment token if not provided."""
        deepcast_path = tmp_path / "deepcast.json"
        deepcast_path.write_text('{"markdown": "test", "metadata": {}}')

        mock_engine = MagicMock()
        mock_engine.create_page.return_value = "page-123-id"
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.publish_to_notion(
            deepcast_path=deepcast_path, database_id="db123"
        )

        assert result.success is True
        # Verify engine was initialized with env token
        mock_engine_class.assert_called_once_with(api_token="env_token")

    def test_publish_to_notion_validation_error_missing_file(self):
        """Test Notion publish raises ValidationError when deepcast file doesn't exist."""
        client = PodxClient()

        with pytest.raises(ValidationError, match="Deepcast file not found"):
            client.publish_to_notion(
                deepcast_path=Path("/nonexistent/deepcast.json"),
                database_id="db123",
                notion_token="token",
            )

    @patch("podx.core.notion.NotionEngine")
    def test_publish_to_notion_handles_integration_error(
        self, mock_engine_class, tmp_path
    ):
        """Test Notion publish handles integration errors gracefully."""
        deepcast_path = tmp_path / "deepcast.json"
        deepcast_path.write_text('{"markdown": "test", "metadata": {}}')

        mock_engine = MagicMock()
        mock_engine.create_page.side_effect = Exception("Notion API error")
        mock_engine_class.return_value = mock_engine

        client = PodxClient()
        result = client.publish_to_notion(
            deepcast_path=deepcast_path, database_id="db123", notion_token="token"
        )

        assert result.success is False
        assert result.error is not None


class TestListModelsAPI:
    """Test list_models API method."""

    def test_list_models_all(self):
        """Test listing all models."""
        client = PodxClient()
        models = client.list_models()

        assert len(models) > 0
        assert all(isinstance(m, ModelInfo) for m in models)
        # Should include models from multiple providers
        providers = {m.provider for m in models}
        assert len(providers) >= 2  # At least OpenAI and Anthropic

    def test_list_models_by_provider(self):
        """Test filtering models by provider."""
        client = PodxClient()
        openai_models = client.list_models(provider="openai")

        assert len(openai_models) > 0
        assert all(m.provider == "openai" for m in openai_models)

    def test_list_models_default_only(self):
        """Test filtering to default CLI models only."""
        client = PodxClient()
        all_models = client.list_models()
        default_models = client.list_models(default_only=True)

        assert len(default_models) > 0
        assert len(default_models) <= len(all_models)
        assert all(m.default_in_cli for m in default_models)

    def test_list_models_by_capability(self):
        """Test filtering models by capability."""
        client = PodxClient()
        chat_models = client.list_models(capability="chat")

        assert len(chat_models) > 0
        assert all("chat" in m.capabilities for m in chat_models)

    def test_list_models_combined_filters(self):
        """Test combining multiple filters."""
        client = PodxClient()
        models = client.list_models(provider="openai", default_only=True)

        assert all(m.provider == "openai" for m in models)
        assert all(m.default_in_cli for m in models)

    def test_model_info_structure(self):
        """Test that ModelInfo has all expected fields."""
        client = PodxClient()
        models = client.list_models(provider="openai")

        model = models[0]
        assert isinstance(model.id, str)
        assert isinstance(model.name, str)
        assert isinstance(model.provider, str)
        assert isinstance(model.aliases, list)
        assert isinstance(model.description, str)
        assert isinstance(model.pricing, ModelPricingInfo)
        assert isinstance(model.context_window, int)
        assert isinstance(model.capabilities, list)
        assert isinstance(model.default_in_cli, bool)

    def test_model_pricing_info_structure(self):
        """Test that ModelPricingInfo has all expected fields."""
        client = PodxClient()
        models = client.list_models(provider="openai")

        pricing = models[0].pricing
        assert isinstance(pricing.input_per_1m, float)
        assert isinstance(pricing.output_per_1m, float)
        assert pricing.currency == "USD"
        assert isinstance(pricing.tier, str)


class TestGetModelInfoAPI:
    """Test get_model_info API method."""

    def test_get_model_info_by_id(self):
        """Test getting model info by canonical ID."""
        client = PodxClient()
        model = client.get_model_info("gpt-5.1")

        assert model.id == "gpt-5.1"
        assert model.provider == "openai"
        assert model.pricing.input_per_1m > 0
        assert model.pricing.output_per_1m > 0

    def test_get_model_info_by_alias(self):
        """Test getting model info by alias."""
        client = PodxClient()

        # These should all resolve to the same model
        model1 = client.get_model_info("gpt-5.1")
        model2 = client.get_model_info("gpt5.1")
        model3 = client.get_model_info("gpt-5-1")

        assert model1.id == model2.id == model3.id

    def test_get_model_info_case_insensitive(self):
        """Test that model lookup is case-insensitive."""
        client = PodxClient()

        model1 = client.get_model_info("gpt-5.1")
        model2 = client.get_model_info("GPT-5.1")
        model3 = client.get_model_info("Gpt-5.1")

        assert model1.id == model2.id == model3.id

    def test_get_model_info_not_found(self):
        """Test that invalid model raises KeyError."""
        client = PodxClient()

        with pytest.raises(KeyError, match="Model not found"):
            client.get_model_info("nonexistent-model-xyz")

    def test_get_model_info_anthropic(self):
        """Test getting Anthropic model info."""
        client = PodxClient()
        model = client.get_model_info("claude-sonnet-4.5")

        assert model.provider == "anthropic"
        assert "claude" in model.name.lower()

    def test_model_info_to_dict(self):
        """Test converting ModelInfo to dictionary."""
        client = PodxClient()
        model = client.get_model_info("gpt-5.1")
        model_dict = model.to_dict()

        assert isinstance(model_dict, dict)
        assert model_dict["id"] == "gpt-5.1"
        assert "pricing" in model_dict
        assert model_dict["pricing"]["currency"] == "USD"


class TestEstimateCostAPI:
    """Test estimate_cost API method."""

    def test_estimate_cost_with_token_count(self):
        """Test cost estimation with pre-calculated token count."""
        client = PodxClient()
        estimate = client.estimate_cost(model="gpt-5.1", token_count=100000)

        assert isinstance(estimate, CostEstimate)
        assert estimate.model_id == "gpt-5.1"
        assert estimate.input_tokens == 100000
        assert estimate.output_tokens == 30000  # 30% default ratio
        assert estimate.total_cost_usd > 0
        assert estimate.currency == "USD"

    def test_estimate_cost_with_text(self):
        """Test cost estimation with raw text."""
        client = PodxClient()
        text = "Hello world. " * 1000  # ~13,000 characters
        estimate = client.estimate_cost(model="gpt-5.1", text=text)

        assert estimate.input_tokens > 0
        assert estimate.text_length == len(text)
        assert estimate.total_cost_usd > 0

    def test_estimate_cost_with_transcript(self, tmp_path):
        """Test cost estimation from transcript file."""
        transcript_path = tmp_path / "transcript.json"
        transcript_data = {
            "segments": [
                {"text": "Hello world."},
                {"text": "This is a test."},
                {"text": "More content here."},
            ]
        }
        transcript_path.write_text(json.dumps(transcript_data))

        client = PodxClient()
        estimate = client.estimate_cost(
            model="gpt-5.1", transcript_path=str(transcript_path)
        )

        assert estimate.input_tokens > 0
        assert estimate.transcript_path == str(transcript_path)

    def test_estimate_cost_custom_output_ratio(self):
        """Test cost estimation with custom output ratio."""
        client = PodxClient()
        estimate = client.estimate_cost(
            model="gpt-5.1", token_count=100000, output_ratio=0.5
        )

        assert estimate.output_tokens == 50000  # 50% of input

    def test_estimate_cost_model_alias(self):
        """Test cost estimation works with model aliases."""
        client = PodxClient()
        estimate = client.estimate_cost(model="gpt5.1", token_count=1000)

        assert estimate.model_id == "gpt-5.1"  # Canonical ID

    def test_estimate_cost_no_input_raises_error(self):
        """Test that estimate_cost requires at least one input."""
        client = PodxClient()

        with pytest.raises(ValueError, match="Must provide one of"):
            client.estimate_cost(model="gpt-5.1")

    def test_estimate_cost_multiple_inputs_raises_error(self):
        """Test that estimate_cost rejects multiple inputs."""
        client = PodxClient()

        with pytest.raises(ValueError, match="Provide only one of"):
            client.estimate_cost(
                model="gpt-5.1", text="hello", token_count=1000
            )

    def test_estimate_cost_invalid_model(self):
        """Test that invalid model raises KeyError."""
        client = PodxClient()

        with pytest.raises(KeyError):
            client.estimate_cost(model="nonexistent-model", token_count=1000)

    def test_estimate_cost_missing_transcript(self):
        """Test that missing transcript file raises FileNotFoundError."""
        client = PodxClient()

        with pytest.raises(FileNotFoundError, match="Transcript not found"):
            client.estimate_cost(
                model="gpt-5.1", transcript_path="/nonexistent/transcript.json"
            )

    def test_estimate_cost_invalid_transcript_json(self, tmp_path):
        """Test that invalid transcript JSON raises ValueError."""
        transcript_path = tmp_path / "invalid.json"
        transcript_path.write_text("not valid json{{{")

        client = PodxClient()

        with pytest.raises(ValueError, match="Invalid transcript JSON"):
            client.estimate_cost(model="gpt-5.1", transcript_path=str(transcript_path))

    def test_estimate_cost_to_dict(self):
        """Test converting CostEstimate to dictionary."""
        client = PodxClient()
        estimate = client.estimate_cost(model="gpt-5.1", token_count=1000)
        estimate_dict = estimate.to_dict()

        assert isinstance(estimate_dict, dict)
        assert estimate_dict["model_id"] == "gpt-5.1"
        assert "total_cost_usd" in estimate_dict

    def test_estimate_cost_calculation_accuracy(self):
        """Test that cost calculation is mathematically correct."""
        client = PodxClient()
        model = client.get_model_info("gpt-5.1")
        estimate = client.estimate_cost(
            model="gpt-5.1", token_count=1000000, output_ratio=0.3
        )

        # Manually calculate expected cost
        expected_input_cost = model.pricing.input_per_1m  # 1M tokens
        expected_output_cost = model.pricing.output_per_1m * 0.3  # 300K tokens
        expected_total = expected_input_cost + expected_output_cost

        assert abs(estimate.total_cost_usd - expected_total) < 0.01
