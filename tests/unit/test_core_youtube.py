"""Unit tests for core.youtube module.

Tests pure business logic without UI dependencies.
Uses mocking to avoid actual yt-dlp downloads.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from podx.core.youtube import (
    YouTubeEngine,
    YouTubeError,
    download_youtube_audio,
    extract_video_id,
    fetch_youtube_episode,
    format_upload_date,
    get_youtube_metadata,
    is_youtube_url,
)


@pytest.fixture
def mock_yt_dlp():
    """Fixture to mock yt-dlp module."""
    mock_module = MagicMock()
    sys.modules["yt_dlp"] = mock_module
    yield mock_module
    # Cleanup
    if "yt_dlp" in sys.modules:
        del sys.modules["yt_dlp"]


class TestExtractVideoId:
    """Test extract_video_id utility function."""

    def test_extract_from_watch_url(self):
        """Test extracting video ID from standard watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_short_url(self):
        """Test extracting video ID from youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_embed_url(self):
        """Test extracting video ID from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_watch_url_with_params(self):
        """Test extracting video ID from URL with multiple query parameters."""
        url = "https://www.youtube.com/watch?t=123&v=dQw4w9WgXcQ&list=xyz"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_mobile_url(self):
        """Test extracting video ID from mobile URL."""
        url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_invalid_url_raises_error(self):
        """Test that invalid URL raises YouTubeError."""
        url = "https://not-youtube.com/video"
        with pytest.raises(YouTubeError, match="Could not extract video ID"):
            extract_video_id(url)

    def test_extract_malformed_url_raises_error(self):
        """Test that malformed YouTube URL raises error."""
        url = "https://youtube.com/invalid"
        with pytest.raises(YouTubeError, match="Could not extract video ID"):
            extract_video_id(url)


class TestIsYoutubeUrl:
    """Test is_youtube_url utility function."""

    def test_youtube_com_url(self):
        """Test recognizing youtube.com URL."""
        assert is_youtube_url("https://www.youtube.com/watch?v=abc") is True

    def test_youtu_be_url(self):
        """Test recognizing youtu.be URL."""
        assert is_youtube_url("https://youtu.be/abc") is True

    def test_mobile_youtube_url(self):
        """Test recognizing mobile YouTube URL."""
        assert is_youtube_url("https://m.youtube.com/watch?v=abc") is True

    def test_non_youtube_url(self):
        """Test rejecting non-YouTube URL."""
        assert is_youtube_url("https://vimeo.com/video/123") is False

    def test_invalid_url(self):
        """Test handling of invalid URL."""
        assert is_youtube_url("not a url") is False

    def test_empty_url(self):
        """Test handling of empty URL."""
        assert is_youtube_url("") is False


class TestFormatUploadDate:
    """Test format_upload_date utility function."""

    def test_format_valid_date(self):
        """Test formatting valid upload date."""
        upload_date = "20231225"
        formatted = format_upload_date(upload_date)
        assert formatted == "Mon, 25 Dec 2023 00:00:00 GMT"

    def test_format_another_valid_date(self):
        """Test formatting another valid date."""
        upload_date = "20200101"
        formatted = format_upload_date(upload_date)
        assert formatted == "Wed, 01 Jan 2020 00:00:00 GMT"

    def test_format_invalid_date_returns_none(self):
        """Test that invalid date returns None."""
        upload_date = "invalid"
        formatted = format_upload_date(upload_date)
        assert formatted is None

    def test_format_none_returns_none(self):
        """Test that None returns None."""
        formatted = format_upload_date(None)
        assert formatted is None

    def test_format_empty_string_returns_none(self):
        """Test that empty string returns None."""
        formatted = format_upload_date("")
        assert formatted is None

    def test_format_wrong_length_returns_none(self):
        """Test that wrong length date returns None."""
        formatted = format_upload_date("2023")
        assert formatted is None


class TestYouTubeEngineGetMetadata:
    """Test YouTubeEngine.get_metadata() method."""

    def test_get_metadata_success(self, mock_yt_dlp):
        """Test successful metadata extraction."""
        # Mock yt-dlp response
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "uploader": "Test Channel",
            "uploader_id": "UC123",
            "description": "Test description",
            "upload_date": "20231225",
            "duration": 240,
            "view_count": 1000000,
            "thumbnail": "https://example.com/thumb.jpg",
            "webpage_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        engine = YouTubeEngine()
        metadata = engine.get_metadata("https://youtube.com/watch?v=dQw4w9WgXcQ")

        assert metadata["video_id"] == "dQw4w9WgXcQ"
        assert metadata["title"] == "Test Video"
        assert metadata["channel"] == "Test Channel"
        assert metadata["channel_id"] == "UC123"
        assert metadata["description"] == "Test description"
        assert metadata["upload_date"] == "20231225"
        assert metadata["duration"] == 240
        assert metadata["view_count"] == 1000000
        assert metadata["thumbnail"] == "https://example.com/thumb.jpg"
        assert metadata["webpage_url"] == "https://youtube.com/watch?v=dQw4w9WgXcQ"

    def test_get_metadata_with_channel_fallback(self, mock_yt_dlp):
        """Test metadata extraction with channel field fallback."""
        # Mock yt-dlp response with channel instead of uploader
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "channel": "Alternative Channel Name",
            "channel_id": "UC456",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        engine = YouTubeEngine()
        metadata = engine.get_metadata("https://youtube.com/watch?v=abc123")

        assert metadata["channel"] == "Alternative Channel Name"
        assert metadata["channel_id"] == "UC456"

    def test_get_metadata_missing_yt_dlp(self):
        """Test that missing yt-dlp raises appropriate error."""
        # Mock __import__ to raise ImportError for yt_dlp
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "yt_dlp":
                raise ImportError("No module named 'yt_dlp'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            engine = YouTubeEngine()

            with pytest.raises(YouTubeError, match="yt-dlp library not installed"):
                engine.get_metadata("https://youtube.com/watch?v=abc")

    def test_get_metadata_extraction_failure(self, mock_yt_dlp):
        """Test handling of yt-dlp extraction failure."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = Exception("Network error")
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        engine = YouTubeEngine()

        with pytest.raises(YouTubeError, match="Failed to extract YouTube metadata"):
            engine.get_metadata("https://youtube.com/watch?v=abc")


class TestYouTubeEngineDownloadAudio:
    """Test YouTubeEngine.download_audio() method."""

    def test_download_audio_success(self, mock_yt_dlp, tmp_path):
        """Test successful audio download."""
        # Mock metadata
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "uploader": "Test Channel",
            "description": "Test description",
            "upload_date": "20231225",
            "duration": 240,
            "thumbnail": "https://example.com/thumb.jpg",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create a fake downloaded audio file
        audio_file = tmp_path / "Test_Video.mp3"
        audio_file.write_text("fake audio content")

        engine = YouTubeEngine()
        result = engine.download_audio(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", tmp_path
        )

        assert result["show"] == "Test Channel"
        assert result["episode_title"] == "Test Video"
        assert result["video_id"] == "dQw4w9WgXcQ"
        assert result["video_url"] == "https://youtube.com/watch?v=dQw4w9WgXcQ"
        assert result["duration_seconds"] == 240
        assert result["description"] == "Test description"
        assert result["image_url"] == "https://example.com/thumb.jpg"
        assert result["episode_published"] == "Mon, 25 Dec 2023 00:00:00 GMT"
        assert "audio_path" in result

    def test_download_audio_custom_filename(self, mock_yt_dlp, tmp_path):
        """Test download with custom filename."""
        mock_info = {
            "id": "abc123",
            "title": "Original Title",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create a fake downloaded audio file with custom name
        audio_file = tmp_path / "custom_name.mp3"
        audio_file.write_text("fake audio")

        engine = YouTubeEngine()
        result = engine.download_audio(
            "https://youtube.com/watch?v=abc123",
            tmp_path,
            filename="custom_name.%(ext)s",
        )

        assert "audio_path" in result

    def test_download_audio_sanitizes_title(self, mock_yt_dlp, tmp_path):
        """Test that special characters in title are sanitized."""
        mock_info = {
            "id": "abc123",
            "title": "Test: Video (2023) [HD]",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create a fake downloaded file with sanitized name
        audio_file = tmp_path / "Test_Video_2023_HD.mp3"
        audio_file.write_text("fake audio")

        engine = YouTubeEngine()
        result = engine.download_audio("https://youtube.com/watch?v=abc123", tmp_path)

        assert "audio_path" in result

    def test_download_audio_creates_output_dir(self, mock_yt_dlp, tmp_path):
        """Test that download creates output directory if missing."""
        output_dir = tmp_path / "nested" / "output"

        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create file after directory is created
        def create_audio_file(*args):
            audio_file = output_dir / "Test_Video.mp3"
            audio_file.write_text("fake audio")

        mock_ydl_instance.download.side_effect = create_audio_file

        engine = YouTubeEngine()
        result = engine.download_audio("https://youtube.com/watch?v=abc123", output_dir)

        assert output_dir.exists()
        assert "audio_path" in result

    def test_download_audio_no_file_found_raises_error(self, mock_yt_dlp, tmp_path):
        """Test that missing audio file raises error."""
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Don't create any audio file

        engine = YouTubeEngine()

        with pytest.raises(YouTubeError, match="Downloaded audio file not found"):
            engine.download_audio("https://youtube.com/watch?v=abc123", tmp_path)

    def test_download_audio_calls_progress_callback(self, mock_yt_dlp, tmp_path):
        """Test that download calls progress callback."""
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create audio file
        audio_file = tmp_path / "Test_Video.mp3"
        audio_file.write_text("fake audio")

        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        engine = YouTubeEngine(progress_callback=progress_callback)
        engine.download_audio("https://youtube.com/watch?v=abc123", tmp_path)

        assert len(progress_messages) >= 2
        assert any("metadata" in msg.lower() for msg in progress_messages)
        assert any("download" in msg.lower() for msg in progress_messages)

    def test_download_audio_missing_yt_dlp(self, tmp_path):
        """Test that missing yt-dlp raises appropriate error."""
        # Mock __import__ to raise ImportError for yt_dlp
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "yt_dlp":
                raise ImportError("No module named 'yt_dlp'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            engine = YouTubeEngine()

            with pytest.raises(YouTubeError, match="yt-dlp library not installed"):
                engine.download_audio("https://youtube.com/watch?v=abc", tmp_path)


class TestYouTubeEngineFetchEpisode:
    """Test YouTubeEngine.fetch_episode() method."""

    def test_fetch_episode_success(self, mock_yt_dlp, tmp_path):
        """Test successful episode fetch."""
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "uploader": "Test Channel",
            "description": "Test description",
            "upload_date": "20231225",
            "duration": 240,
            "thumbnail": "https://example.com/thumb.jpg",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create fake audio file
        audio_file = tmp_path / "Test_Video.mp3"
        audio_file.write_text("fake audio")

        engine = YouTubeEngine()
        result = engine.fetch_episode(
            "https://youtube.com/watch?v=dQw4w9WgXcQ", tmp_path
        )

        # Verify episode metadata
        assert result["show"] == "Test Channel"
        assert result["episode_title"] == "Test Video"
        assert result["video_id"] == "dQw4w9WgXcQ"

        # Verify episode-meta.json was created
        meta_file = tmp_path / "episode-meta.json"
        assert meta_file.exists()

        # Verify content of metadata file
        with open(meta_file, "r") as f:
            saved_meta = json.load(f)

        assert saved_meta["show"] == "Test Channel"
        assert saved_meta["episode_title"] == "Test Video"
        assert saved_meta["video_id"] == "dQw4w9WgXcQ"

    def test_fetch_episode_invalid_url_raises_error(self, tmp_path):
        """Test that invalid YouTube URL raises error."""
        engine = YouTubeEngine()

        with pytest.raises(YouTubeError, match="Not a valid YouTube URL"):
            engine.fetch_episode("https://vimeo.com/video/123", tmp_path)

    def test_fetch_episode_download_failure(self, mock_yt_dlp, tmp_path):
        """Test handling of download failure during fetch."""
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.side_effect = Exception("Download failed")
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        engine = YouTubeEngine()

        with pytest.raises(YouTubeError, match="Failed to download YouTube audio"):
            engine.fetch_episode("https://youtube.com/watch?v=abc123", tmp_path)


class TestConvenienceFunctions:
    """Test convenience functions for direct use."""

    def test_get_youtube_metadata(self, mock_yt_dlp):
        """Test get_youtube_metadata convenience function."""
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        metadata = get_youtube_metadata("https://youtube.com/watch?v=dQw4w9WgXcQ")

        assert metadata["video_id"] == "dQw4w9WgXcQ"
        assert metadata["title"] == "Test Video"

    def test_download_youtube_audio(self, mock_yt_dlp, tmp_path):
        """Test download_youtube_audio convenience function."""
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create fake audio file
        audio_file = tmp_path / "Test_Video.mp3"
        audio_file.write_text("fake audio")

        result = download_youtube_audio("https://youtube.com/watch?v=abc123", tmp_path)

        assert result["video_id"] == "abc123"
        assert result["show"] == "Test Channel"

    def test_download_youtube_audio_with_progress_callback(self, mock_yt_dlp, tmp_path):
        """Test download_youtube_audio with progress callback."""
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create fake audio file
        audio_file = tmp_path / "Test_Video.mp3"
        audio_file.write_text("fake audio")

        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        download_youtube_audio(
            "https://youtube.com/watch?v=abc123",
            tmp_path,
            progress_callback=progress_callback,
        )

        assert len(progress_messages) >= 2

    def test_fetch_youtube_episode(self, mock_yt_dlp, tmp_path):
        """Test fetch_youtube_episode convenience function."""
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create fake audio file
        audio_file = tmp_path / "Test_Video.mp3"
        audio_file.write_text("fake audio")

        result = fetch_youtube_episode("https://youtube.com/watch?v=abc123", tmp_path)

        assert result["video_id"] == "abc123"
        assert (tmp_path / "episode-meta.json").exists()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_download_finds_alternative_audio_format(self, mock_yt_dlp, tmp_path):
        """Test that download finds audio file with alternative extension."""
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create audio file with .m4a extension instead of .mp3
        audio_file = tmp_path / "Test_Video.m4a"
        audio_file.write_text("fake audio")

        engine = YouTubeEngine()
        result = engine.download_audio("https://youtube.com/watch?v=abc123", tmp_path)

        assert "audio_path" in result
        assert result["audio_path"].endswith(".m4a")

    def test_extract_video_id_with_various_formats(self):
        """Test video ID extraction with various URL formats."""
        urls = [
            ("https://www.youtube.com/watch?v=abc12345678", "abc12345678"),
            ("https://youtu.be/xyz98765432", "xyz98765432"),
            ("https://youtube.com/watch?v=test_video1", "test_video1"),
            ("https://m.youtube.com/watch?v=mobile12345", "mobile12345"),
        ]

        for url, expected_id in urls:
            video_id = extract_video_id(url)
            assert video_id == expected_id

    def test_download_with_missing_optional_metadata(self, mock_yt_dlp, tmp_path):
        """Test download handles missing optional metadata fields."""
        # Minimal metadata with only required fields
        mock_info = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
            # Missing: description, upload_date, duration, thumbnail, etc.
        }

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.download.return_value = None
        mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance

        # Create fake audio file
        audio_file = tmp_path / "Test_Video.mp3"
        audio_file.write_text("fake audio")

        engine = YouTubeEngine()
        result = engine.download_audio("https://youtube.com/watch?v=abc123", tmp_path)

        # Should still work with None values for missing fields
        assert result["video_id"] == "abc123"
        assert result["show"] == "Test Channel"
        assert result["episode_published"] is None  # No upload_date
        assert result.get("duration_seconds") is None
        assert result.get("description") is None

    def test_format_upload_date_edge_cases(self):
        """Test upload date formatting with edge cases."""
        # Leap year date
        assert format_upload_date("20240229") == "Thu, 29 Feb 2024 00:00:00 GMT"

        # First day of year
        assert format_upload_date("20230101") == "Sun, 01 Jan 2023 00:00:00 GMT"

        # Last day of year
        assert format_upload_date("20231231") == "Sun, 31 Dec 2023 00:00:00 GMT"

        # Invalid date (February 30th doesn't exist)
        assert format_upload_date("20230230") is None
