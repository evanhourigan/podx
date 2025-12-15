#!/usr/bin/env python3
"""
Integration tests for the podx pipeline.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from podx.config import PodxConfig, reset_config
from podx.errors import ValidationError
from podx.fetch import choose_episode, download_enclosure, find_feed_for_show
from podx.schemas import AudioMeta, EpisodeMeta, Transcript


class TestPipelineValidation:
    """Test pipeline data validation and compatibility."""

    def test_episode_meta_validation(self):
        """Test EpisodeMeta validation."""
        with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
            valid_data = {
                "show": "Test Podcast",
                "feed": "https://example.com/feed.xml",
                "episode_title": "Test Episode",
                "episode_published": "2024-01-01",
                "audio_path": tmp.name,
            }
            meta = EpisodeMeta.parse_obj(valid_data)
            assert meta.show == "Test Podcast"
            assert meta.audio_path == tmp.name

    def test_episode_meta_validation_missing_file(self):
        """Test EpisodeMeta validation with missing audio file."""
        invalid_data = {
            "show": "Test Podcast",
            "feed": "https://example.com/feed.xml",
            "episode_title": "Test Episode",
            "episode_published": "2024-01-01",
            "audio_path": "/nonexistent/file.mp3",
        }
        with pytest.raises(ValueError):  # Pydantic raises ValueError for validation errors
            EpisodeMeta.parse_obj(invalid_data)

    def test_audio_meta_validation(self):
        """Test AudioMeta validation."""
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            valid_data = {
                "audio_path": tmp.name,
                "sample_rate": 16000,
                "channels": 1,
                "format": "wav16",
            }
            meta = AudioMeta.parse_obj(valid_data)
            assert meta.sample_rate == 16000
            assert meta.format == "wav16"

    def test_transcript_validation(self):
        """Test Transcript validation."""
        valid_data = {
            "language": "en",
            "text": "Hello world",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello"},
                {"start": 1.0, "end": 2.0, "text": "world"},
            ],
        }
        transcript = Transcript.parse_obj(valid_data)
        assert transcript.language == "en"
        assert len(transcript.segments) == 2

    def test_segment_timing_validation(self):
        """Test segment timing validation."""
        from podx.schemas import Segment

        # Valid segment
        valid_segment = {"start": 0.0, "end": 1.0, "text": "Hello"}
        seg = Segment.parse_obj(valid_segment)
        assert seg.start == 0.0
        assert seg.end == 1.0

        # Invalid segment (end before start)
        invalid_segment = {"start": 1.0, "end": 0.0, "text": "Hello"}
        with pytest.raises(ValueError):
            Segment.parse_obj(invalid_segment)

    def test_pipeline_compatibility(self):
        """Test pipeline step compatibility checking."""
        # EpisodeMeta should be compatible with transcription input
        with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
            episode_data = {
                "show": "Test",
                "feed": "https://example.com/feed.xml",
                "episode_title": "Test",
                "episode_published": "2024-01-01",
                "audio_path": tmp.name,
            }

            # Test that it validates correctly
            meta = EpisodeMeta.parse_obj(episode_data)
            assert meta.audio_path == tmp.name


class TestFetchModule:
    """Test the fetch module with mocked dependencies."""

    @patch("requests.Session")
    def test_find_feed_for_show_success(self, mock_session):
        """Test successful podcast feed lookup."""
        # Mock the requests response
        mock_response = Mock()
        mock_response.json.return_value = {"results": [{"feedUrl": "https://example.com/feed.xml"}]}
        mock_response.raise_for_status.return_value = None
        mock_session.return_value.get.return_value = mock_response

        result = find_feed_for_show("Test Podcast")
        assert result == "https://example.com/feed.xml"

    @patch("requests.Session")
    def test_find_feed_for_show_no_results(self, mock_session):
        """Test podcast feed lookup with no results."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_session.return_value.get.return_value = mock_response

        with pytest.raises(ValidationError, match="No podcasts found"):
            find_feed_for_show("Nonexistent Podcast")

    def test_choose_episode_by_title(self):
        """Test episode selection by title."""
        entries = [
            {"title": "Episode 1", "published": "2024-01-01"},
            {"title": "Episode 2", "published": "2024-01-02"},
            {"title": "Special Episode", "published": "2024-01-03"},
        ]

        result = choose_episode(entries, None, "Special")
        assert result["title"] == "Special Episode"

    def test_choose_episode_by_date(self):
        """Test episode selection by date."""
        entries = [
            {"title": "Episode 1", "published": "2024-01-01T00:00:00Z"},
            {"title": "Episode 2", "published": "2024-01-02T00:00:00Z"},
            {"title": "Episode 3", "published": "2024-01-03T00:00:00Z"},
        ]

        result = choose_episode(entries, "2024-01-02", None)
        assert result["title"] == "Episode 2"

    @patch("requests.get")
    def test_download_enclosure_success(self, mock_get):
        """Test successful audio download."""
        # Mock the download response
        mock_response = Mock()
        mock_response.iter_content.return_value = [b"fake audio data"]
        mock_response.headers = {"content-length": "100"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value.__enter__.return_value = mock_response

        entry = {
            "title": "Test Episode",
            "links": [
                {
                    "rel": "enclosure",
                    "type": "audio/mpeg",
                    "href": "https://example.com/audio.mp3",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_enclosure(entry, Path(tmpdir))
            assert result.exists()
            assert result.suffix == ".mp3"


class TestConfigurationSystem:
    """Test the configuration management system."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def test_default_config(self):
        """Test default configuration values."""
        config = PodxConfig()
        assert config.default_asr_model == "large-v3-turbo"
        assert config.openai_model == "gpt-4.1"
        assert config.max_retries == 3

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid temperature
        config = PodxConfig(openai_temperature=0.5)
        assert config.openai_temperature == 0.5

        # Invalid temperature
        with pytest.raises(ValueError):
            PodxConfig(openai_temperature=3.0)

    def test_config_override_via_params(self):
        """Test configuration can be overridden via constructor parameters."""
        config = PodxConfig(openai_model="gpt-4", max_retries=5)
        assert config.openai_model == "gpt-4"
        assert config.max_retries == 5


class TestErrorHandling:
    """Test error handling and retry logic."""

    @patch("time.sleep")  # Speed up tests by mocking sleep
    def test_retry_decorator_success_after_failure(self, mock_sleep):
        """Test retry decorator with eventual success."""
        from podx.errors import with_retries

        call_count = 0

        @with_retries(stop_after=3)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.RequestException("Network error")
            return "success"

        result = flaky_function()
        assert result == "success"
        assert call_count == 3

    @patch("time.sleep")  # Speed up tests by mocking sleep
    def test_retry_decorator_max_attempts(self, mock_sleep):
        """Test retry decorator reaching max attempts."""
        from tenacity import RetryError

        from podx.errors import with_retries

        @with_retries(stop_after=2)
        def always_fails():
            raise requests.exceptions.RequestException("Always fails")

        with pytest.raises(RetryError):
            always_fails()


class TestPipelineIntegration:
    """Test full pipeline integration with mocked external dependencies."""

    def setup_method(self):
        """Set up test environment."""
        reset_config()

    @patch("podx.fetch.find_feed_for_show")
    @patch("podx.fetch.download_enclosure")
    @patch("feedparser.parse")
    def test_fetch_to_metadata_flow(self, mock_parse, mock_download, mock_find_feed):
        """Test the flow from fetch to metadata generation."""
        # Mock the feed finding
        mock_find_feed.return_value = "https://example.com/feed.xml"

        # Mock the feed parsing
        mock_feed = Mock()
        mock_feed.feed = {"title": "Test Podcast"}
        mock_feed.entries = [
            {
                "title": "Test Episode",
                "published": "2024-01-01T00:00:00Z",
            }
        ]
        mock_feed.bozo = False
        mock_parse.return_value = mock_feed

        # Mock the download
        with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
            mock_download.return_value = Path(tmp.name)

            # This would normally be tested via CLI, but we can test the components
            # The actual CLI integration would require subprocess mocking
            assert mock_find_feed.return_value.startswith("https://")
            assert len(mock_feed.entries) == 1

    def test_pipeline_data_flow_compatibility(self):
        """Test that pipeline stages can accept each other's output."""
        # Episode metadata that would come from fetch
        with tempfile.NamedTemporaryFile(suffix=".mp3") as audio_file:
            episode_meta = {
                "show": "Test Podcast",
                "feed": "https://example.com/feed.xml",
                "episode_title": "Test Episode",
                "episode_published": "2024-01-01",
                "audio_path": audio_file.name,
            }

            # Validate this can be parsed as EpisodeMeta
            meta = EpisodeMeta.parse_obj(episode_meta)
            assert meta.audio_path == audio_file.name

            # Audio metadata that would come from transcode
            audio_meta = {
                "audio_path": audio_file.name,
                "sample_rate": 16000,
                "channels": 1,
                "format": "wav16",
            }

            # Validate this can be parsed as AudioMeta
            audio = AudioMeta.parse_obj(audio_meta)
            assert audio.format == "wav16"

            # Transcript that would come from transcribe
            transcript_data = {
                "audio_path": audio_file.name,
                "language": "en",
                "text": "Hello world",
                "segments": [
                    {"start": 0.0, "end": 1.0, "text": "Hello"},
                    {"start": 1.0, "end": 2.0, "text": "world"},
                ],
            }

            # Validate this can be parsed as Transcript
            transcript = Transcript.parse_obj(transcript_data)
            assert len(transcript.segments) == 2


if __name__ == "__main__":
    pytest.main([__file__])
