"""Unit tests for core.fetch module.

Tests pure business logic without UI dependencies.
Uses mocking to avoid actual network requests.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from podx.core.fetch import (PodcastFetcher, fetch_episode, find_feed_url,
                             search_podcasts)
from podx.errors import ValidationError


class TestPodcastFetcher:
    """Test PodcastFetcher class."""

    def test_init_defaults(self):
        """Test default initialization."""
        fetcher = PodcastFetcher()
        assert fetcher.user_agent == "podx/1.0 (+mac cli)"

    def test_init_custom_user_agent(self):
        """Test initialization with custom user agent."""
        fetcher = PodcastFetcher(user_agent="custom/agent")
        assert fetcher.user_agent == "custom/agent"

    @patch("podx.core.fetch.requests.Session")
    def test_search_podcasts_success(self, mock_session):
        """Test successful podcast search."""
        # Mock iTunes API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {"collectionName": "Test Podcast", "feedUrl": "http://feed.url"}
            ]
        }
        mock_session.return_value.get.return_value = mock_response

        fetcher = PodcastFetcher()
        results = fetcher.search_podcasts("Test Show")

        assert len(results) == 1
        assert results[0]["collectionName"] == "Test Podcast"

    @patch("podx.core.fetch.requests.Session")
    def test_search_podcasts_no_results(self, mock_session):
        """Test search with no results."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_session.return_value.get.return_value = mock_response

        fetcher = PodcastFetcher()

        with pytest.raises(ValidationError, match="No podcasts found"):
            fetcher.search_podcasts("Nonexistent Show")

    @patch("podx.core.fetch.subprocess.run")
    @patch("podx.core.fetch.requests.Session")
    def test_search_podcasts_curl_fallback(self, mock_session, mock_subprocess):
        """Test curl fallback when requests fails."""
        # Mock requests failure
        import requests

        mock_session.return_value.get.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )

        # Mock successful curl fallback
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='{"results": [{"collectionName": "Test", "feedUrl": "http://feed"}]}',
        )

        fetcher = PodcastFetcher()
        results = fetcher.search_podcasts("Test Show")

        assert len(results) == 1
        mock_subprocess.assert_called_once()

    @patch("podx.core.fetch.PodcastFetcher.search_podcasts")
    def test_find_feed_url_success(self, mock_search):
        """Test finding feed URL."""
        mock_search.return_value = [{"feedUrl": "http://test.feed.url"}]

        fetcher = PodcastFetcher()
        feed_url = fetcher.find_feed_url("Test Show")

        assert feed_url == "http://test.feed.url"

    @patch("podx.core.fetch.PodcastFetcher.search_podcasts")
    def test_find_feed_url_no_feed(self, mock_search):
        """Test error when no feed URL in results."""
        mock_search.return_value = [{"collectionName": "Test"}]  # No feedUrl

        fetcher = PodcastFetcher()

        with pytest.raises(ValidationError, match="no feedUrl"):
            fetcher.find_feed_url("Test Show")

    def test_choose_episode_by_title(self):
        """Test episode selection by title."""
        entries = [
            {"title": "Episode 1: Introduction"},
            {"title": "Episode 2: Advanced Topics"},
            {"title": "Episode 3: Conclusion"},
        ]

        fetcher = PodcastFetcher()
        episode = fetcher.choose_episode(entries, title_contains="Advanced")

        assert episode["title"] == "Episode 2: Advanced Topics"

    def test_choose_episode_by_date(self):
        """Test episode selection by date (nearest match)."""
        entries = [
            {"title": "Ep 1", "published": "2025-01-01T00:00:00Z"},
            {"title": "Ep 2", "published": "2025-01-10T00:00:00Z"},
            {"title": "Ep 3", "published": "2025-01-20T00:00:00Z"},
        ]

        fetcher = PodcastFetcher()
        episode = fetcher.choose_episode(entries, date_str="2025-01-12")

        assert episode["title"] == "Ep 2"  # Nearest to Jan 12

    def test_choose_episode_default_latest(self):
        """Test default behavior: return most recent episode."""
        entries = [
            {"title": "Latest Episode"},
            {"title": "Older Episode"},
        ]

        fetcher = PodcastFetcher()
        episode = fetcher.choose_episode(entries)

        assert episode["title"] == "Latest Episode"

    def test_choose_episode_empty_list(self):
        """Test choosing from empty list returns None."""
        fetcher = PodcastFetcher()
        episode = fetcher.choose_episode([])

        assert episode is None

    @patch("podx.core.fetch.requests.get")
    def test_download_audio_success(self, mock_get, tmp_path):
        """Test successful audio download."""
        entry = {
            "title": "Test Episode",
            "links": [
                {"rel": "enclosure", "type": "audio/mpeg", "href": "http://audio.url"}
            ],
        }

        # Mock streaming response
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.iter_content.return_value = [b"audio data chunk"]
        mock_get.return_value = mock_response

        fetcher = PodcastFetcher()
        audio_path = fetcher.download_audio(entry, tmp_path)

        assert audio_path.exists()
        assert audio_path.name.endswith(".mp3")

    def test_download_audio_no_enclosure(self, tmp_path):
        """Test error when no audio enclosure found."""
        entry = {"title": "Test Episode", "links": []}

        fetcher = PodcastFetcher()

        with pytest.raises(ValidationError, match="No audio enclosure"):
            fetcher.download_audio(entry, tmp_path)

    @patch("podx.core.fetch.requests.get")
    def test_download_audio_retry_logic(self, mock_get, tmp_path):
        """Test download retries on failure."""
        entry = {
            "title": "Test Episode",
            "links": [
                {"rel": "enclosure", "type": "audio/mpeg", "href": "http://audio.url"}
            ],
        }

        # First attempt fails, second succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.__enter__.side_effect = Exception("Network error")

        mock_response_success = MagicMock()
        mock_response_success.__enter__.return_value = mock_response_success
        mock_response_success.iter_content.return_value = [b"audio data"]

        mock_get.side_effect = [mock_response_fail, mock_response_success]

        fetcher = PodcastFetcher()
        audio_path = fetcher.download_audio(entry, tmp_path)

        assert audio_path.exists()
        assert mock_get.call_count == 2  # Retried once

    @patch("podx.core.fetch.feedparser.parse")
    def test_parse_feed_success(self, mock_parse):
        """Test successful feed parsing."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [{"title": "Episode 1"}]
        mock_parse.return_value = mock_feed

        fetcher = PodcastFetcher()
        feed = fetcher.parse_feed("http://feed.url")

        assert len(feed.entries) == 1

    @patch("podx.core.fetch.requests.Session")
    @patch("podx.core.fetch.feedparser.parse")
    def test_parse_feed_fallback_with_user_agent(self, mock_parse, mock_session):
        """Test feed parsing with user agent fallback."""
        # First parse fails
        mock_feed_fail = Mock()
        mock_feed_fail.bozo = True
        mock_feed_fail.entries = []

        # Second parse succeeds
        mock_feed_success = Mock()
        mock_feed_success.bozo = False
        mock_feed_success.entries = [{"title": "Episode 1"}]

        mock_parse.side_effect = [mock_feed_fail, mock_feed_success]

        # Mock session response
        mock_response = Mock()
        mock_response.content = b"<rss>...</rss>"
        mock_session.return_value.get.return_value = mock_response

        fetcher = PodcastFetcher()
        feed = fetcher.parse_feed("http://feed.url")

        assert len(feed.entries) == 1

    @patch("podx.core.fetch.requests.Session")
    @patch("podx.core.fetch.feedparser.parse")
    def test_parse_feed_no_entries(self, mock_parse, mock_session):
        """Test error when feed has no entries."""
        # First parse: no entries, triggers fallback
        mock_feed_first = Mock()
        mock_feed_first.bozo = True
        mock_feed_first.entries = []

        # Second parse: still no entries
        mock_feed_second = Mock()
        mock_feed_second.bozo = False
        mock_feed_second.entries = []

        mock_parse.side_effect = [mock_feed_first, mock_feed_second]

        # Mock session response for fallback
        mock_response = Mock()
        mock_response.content = b"<rss></rss>"
        mock_session.return_value.get.return_value = mock_response

        fetcher = PodcastFetcher()

        with pytest.raises(ValidationError, match="No episodes found in feed"):
            fetcher.parse_feed("http://feed.url")

    @patch("podx.core.fetch.PodcastFetcher.download_audio")
    @patch("podx.core.fetch.PodcastFetcher.choose_episode")
    @patch("podx.core.fetch.PodcastFetcher.parse_feed")
    @patch("podx.core.fetch.PodcastFetcher.find_feed_url")
    def test_fetch_episode_by_show_name(
        self, mock_find_feed, mock_parse, mock_choose, mock_download, tmp_path
    ):
        """Test fetching episode by show name with explicit output directory."""
        # Mock feed URL discovery
        mock_find_feed.return_value = "http://feed.url"

        # Mock feed parsing
        mock_feed = Mock()
        mock_feed.feed = {"title": "Test Podcast"}
        mock_feed.entries = [{"title": "Episode 1", "published": "2025-01-01"}]
        mock_parse.return_value = mock_feed

        # Mock episode selection
        mock_choose.return_value = {
            "title": "Episode 1",
            "published": "2025-01-01",
        }

        # Mock audio download
        audio_path = tmp_path / "episode.mp3"
        audio_path.write_text("fake audio")
        mock_download.return_value = audio_path

        fetcher = PodcastFetcher()
        # Provide explicit output_dir to avoid generate_workdir call
        result = fetcher.fetch_episode(show_name="Test Show", output_dir=tmp_path)

        # When searching by show_name, it uses the search term
        assert result["meta"]["show"] == "Test Show"
        assert result["meta"]["episode_title"] == "Episode 1"
        assert "audio_path" in result
        assert "meta_path" in result

    @patch("podx.core.fetch.PodcastFetcher.download_audio")
    @patch("podx.core.fetch.PodcastFetcher.choose_episode")
    @patch("podx.core.fetch.PodcastFetcher.parse_feed")
    def test_fetch_episode_by_rss_url(
        self, mock_parse, mock_choose, mock_download, tmp_path
    ):
        """Test fetching episode by direct RSS URL."""
        # Mock feed parsing
        mock_feed = Mock()
        mock_feed.feed = {"title": "Direct Feed Podcast"}
        mock_feed.entries = [{"title": "Ep 1"}]
        mock_parse.return_value = mock_feed

        # Mock episode selection
        mock_choose.return_value = {"title": "Ep 1", "published": "2025-01-01"}

        # Mock audio download
        audio_path = tmp_path / "episode.mp3"
        audio_path.write_text("fake audio")
        mock_download.return_value = audio_path

        fetcher = PodcastFetcher()
        result = fetcher.fetch_episode(rss_url="http://feed.url", output_dir=tmp_path)

        assert result["meta"]["show"] == "Direct Feed Podcast"
        assert result["meta"]["feed"] == "http://feed.url"

    def test_fetch_episode_no_show_or_rss(self):
        """Test error when neither show nor RSS provided."""
        fetcher = PodcastFetcher()

        with pytest.raises(
            ValidationError, match="show_name or rss_url must be provided"
        ):
            fetcher.fetch_episode()

    def test_fetch_episode_both_show_and_rss(self):
        """Test error when both show and RSS provided."""
        fetcher = PodcastFetcher()

        with pytest.raises(
            ValidationError, match="either show_name or rss_url, not both"
        ):
            fetcher.fetch_episode(show_name="Test", rss_url="http://feed.url")

    @patch("podx.core.fetch.PodcastFetcher.download_audio")
    @patch("podx.core.fetch.PodcastFetcher.choose_episode")
    @patch("podx.core.fetch.PodcastFetcher.parse_feed")
    def test_fetch_episode_no_matching_episode(
        self, mock_parse, mock_choose, mock_download
    ):
        """Test error when no episode matches criteria."""
        mock_feed = Mock()
        mock_feed.feed = {"title": "Test Podcast"}
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        mock_choose.return_value = None  # No match

        fetcher = PodcastFetcher()

        with pytest.raises(ValidationError, match="No episode found"):
            fetcher.fetch_episode(rss_url="http://feed.url")

    @patch("podx.core.fetch.PodcastFetcher.download_audio")
    @patch("podx.core.fetch.PodcastFetcher.choose_episode")
    @patch("podx.core.fetch.PodcastFetcher.parse_feed")
    def test_fetch_episode_saves_metadata(
        self, mock_parse, mock_choose, mock_download, tmp_path
    ):
        """Test that episode metadata is saved to JSON file."""
        mock_feed = Mock()
        mock_feed.feed = {
            "title": "Test Podcast",
            "image": {"href": "http://image.url"},
        }
        mock_parse.return_value = mock_feed

        mock_choose.return_value = {"title": "Ep 1", "published": "2025-01-01"}

        audio_path = tmp_path / "episode.mp3"
        audio_path.write_text("fake audio")
        mock_download.return_value = audio_path

        fetcher = PodcastFetcher()
        result = fetcher.fetch_episode(rss_url="http://feed.url", output_dir=tmp_path)

        # Verify metadata file was created
        meta_path = Path(result["meta_path"])
        assert meta_path.exists()

        # Verify metadata contains image URL
        assert result["meta"]["image_url"] == "http://image.url"


class TestConvenienceFunctions:
    """Test convenience functions for direct use."""

    @patch("podx.core.fetch.PodcastFetcher.search_podcasts")
    def test_search_podcasts_convenience(self, mock_method):
        """Test search_podcasts convenience function."""
        mock_method.return_value = [{"feedUrl": "http://feed.url"}]

        results = search_podcasts("Test Show")

        assert len(results) == 1
        mock_method.assert_called_once_with("Test Show")

    @patch("podx.core.fetch.PodcastFetcher.find_feed_url")
    def test_find_feed_url_convenience(self, mock_method):
        """Test find_feed_url convenience function."""
        mock_method.return_value = "http://feed.url"

        url = find_feed_url("Test Show")

        assert url == "http://feed.url"
        mock_method.assert_called_once_with("Test Show")

    @patch("podx.core.fetch.PodcastFetcher.fetch_episode")
    def test_fetch_episode_convenience(self, mock_method):
        """Test fetch_episode convenience function."""
        mock_method.return_value = {"meta": {"show": "Test", "episode_title": "Ep 1"}}

        result = fetch_episode(show_name="Test Show")

        assert result["meta"]["show"] == "Test"
        mock_method.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_choose_episode_title_case_insensitive(self):
        """Test title matching is case insensitive."""
        entries = [{"title": "Episode About Python Programming"}]

        fetcher = PodcastFetcher()
        episode = fetcher.choose_episode(entries, title_contains="python")

        assert episode is not None

    def test_choose_episode_handles_missing_dates(self):
        """Test episode selection handles missing date fields."""
        entries = [
            {"title": "Ep 1"},  # No published or updated
            {"title": "Ep 2", "published": "2025-01-10"},
        ]

        fetcher = PodcastFetcher()
        episode = fetcher.choose_episode(entries, date_str="2025-01-10")

        assert episode["title"] == "Ep 2"

    @patch("podx.core.fetch.requests.get")
    def test_download_audio_creates_output_dir(self, mock_get, tmp_path):
        """Test that download creates output directory if missing."""
        entry = {
            "title": "Test Episode",
            "links": [
                {"rel": "enclosure", "type": "audio/mpeg", "href": "http://audio.url"}
            ],
        }

        output_dir = tmp_path / "nested" / "dir"
        assert not output_dir.exists()

        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.iter_content.return_value = [b"audio data"]
        mock_get.return_value = mock_response

        fetcher = PodcastFetcher()
        audio_path = fetcher.download_audio(entry, output_dir)

        assert output_dir.exists()
        assert audio_path.parent == output_dir

    def test_download_audio_sanitizes_filename(self, tmp_path):
        """Test that audio filename is sanitized."""
        entry = {
            "title": "Episode: Special / Characters \\ Test",
            "link": "http://audio.url/file.mp3",
        }

        # Mock just to avoid actual download
        with patch("podx.core.fetch.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.__enter__.return_value = mock_response
            mock_response.iter_content.return_value = [b"data"]
            mock_get.return_value = mock_response

            fetcher = PodcastFetcher()
            audio_path = fetcher.download_audio(entry, tmp_path)

            # Filename should not contain special characters
            assert "/" not in audio_path.name
            assert "\\" not in audio_path.name
            assert ":" not in audio_path.name
