"""Unit tests for _execute_fetch() helper function."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podx.orchestrate import _execute_fetch


def test_interactive_mode_passthrough():
    """Test that interactive mode uses pre-loaded metadata and workdir."""
    config = {"show": "Test Podcast"}

    # Pre-loaded from interactive selection
    interactive_meta = {"show": "Interactive Show", "episode_title": "Episode 1"}
    interactive_wd = Path("/tmp/test/interactive")

    progress = MagicMock()

    # Should return the pre-loaded values without calling fetch
    meta, wd = _execute_fetch(
        config=config,
        interactive_mode_meta=interactive_meta,
        interactive_mode_wd=interactive_wd,
        progress=progress,
        verbose=False,
    )

    assert meta == interactive_meta
    assert wd == interactive_wd
    # Should not have called any progress methods (no fetch needed)
    progress.start_step.assert_not_called()


@patch("podx.utils.generate_workdir")
@patch("podx.utils.apply_podcast_config")
@patch("podx.youtube.is_youtube_url")
@patch("podx.youtube.get_youtube_metadata")
def test_youtube_url_fetching(
    mock_get_youtube, mock_is_youtube, mock_apply_config, mock_generate_workdir
):
    """Test fetching from YouTube URL."""
    config = {
        "youtube_url": "https://youtube.com/watch?v=test123",
        "show": None,
        "rss_url": None,
        "date": None,
        "title_contains": None,
        "workdir": None,
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
        "deepcast_model": "gpt-4",
        "deepcast_temp": 0.7,
    }

    # Mock YouTube URL validation
    mock_is_youtube.return_value = True

    # Mock YouTube metadata
    mock_get_youtube.return_value = {
        "channel": "Test Channel",
        "title": "Test Video",
        "upload_date": "2025-01-15",
    }

    # Mock podcast config (no overrides)
    mock_apply_config.return_value = {
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
    }

    # Mock workdir generation
    mock_generate_workdir.return_value = Path("/tmp/test/Test Channel/2025-01-15")

    progress = MagicMock()

    meta, wd = _execute_fetch(
        config=config,
        interactive_mode_meta=None,
        interactive_mode_wd=None,
        progress=progress,
        verbose=False,
    )

    # Verify metadata structure
    assert meta["show"] == "Test Channel"
    assert meta["episode_title"] == "Test Video"
    assert meta["episode_published"] == "2025-01-15"

    # Verify workdir
    assert wd == Path("/tmp/test/Test Channel/2025-01-15")

    # Verify progress tracking
    progress.start_step.assert_called_once()
    progress.complete_step.assert_called_once()


@patch("podx.utils.generate_workdir")
@patch("podx.utils.apply_podcast_config")
@patch("podx.orchestrate._run")
def test_rss_podcast_fetching(mock_run, mock_apply_config, mock_generate_workdir):
    """Test fetching from RSS/podcast via podx-fetch."""
    config = {
        "show": "My Podcast",
        "rss_url": None,
        "youtube_url": None,
        "date": "2025-01-15",
        "title_contains": "episode",
        "workdir": None,
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
        "deepcast_model": "gpt-4",
        "deepcast_temp": 0.7,
    }

    # Mock fetch result
    mock_run.return_value = {
        "show": "My Podcast",
        "episode_title": "Episode 42",
        "episode_published": "2025-01-15",
        "audio_path": "/tmp/audio.mp3",
    }

    # Mock podcast config (no overrides)
    mock_apply_config.return_value = {
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
    }

    # Mock workdir generation
    mock_generate_workdir.return_value = Path("/tmp/test/My Podcast/2025-01-15")

    progress = MagicMock()

    meta, wd = _execute_fetch(
        config=config,
        interactive_mode_meta=None,
        interactive_mode_wd=None,
        progress=progress,
        verbose=False,
    )

    # Verify metadata
    assert meta["show"] == "My Podcast"
    assert meta["episode_title"] == "Episode 42"

    # Verify fetch command included date and title_contains
    call_args = mock_run.call_args
    cmd = call_args[0][0]  # First positional arg is the command list
    assert "--show" in cmd
    assert "My Podcast" in cmd
    assert "--date" in cmd
    assert "2025-01-15" in cmd
    assert "--title-contains" in cmd
    assert "episode" in cmd

    # Verify workdir
    assert wd == Path("/tmp/test/My Podcast/2025-01-15")


@patch("podx.utils.generate_workdir")
@patch("podx.utils.apply_podcast_config")
@patch("podx.orchestrate._run")
def test_rss_url_fetching(mock_run, mock_apply_config, mock_generate_workdir):
    """Test fetching from direct RSS URL."""
    config = {
        "show": None,
        "rss_url": "https://example.com/feed.xml",
        "youtube_url": None,
        "date": None,
        "title_contains": None,
        "workdir": None,
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
        "deepcast_model": "gpt-4",
        "deepcast_temp": 0.7,
    }

    # Mock fetch result
    mock_run.return_value = {
        "show": "RSS Podcast",
        "episode_title": "Latest Episode",
        "episode_published": "2025-01-15",
    }

    # Mock podcast config
    mock_apply_config.return_value = {
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
    }

    # Mock workdir generation
    mock_generate_workdir.return_value = Path("/tmp/test/RSS Podcast/2025-01-15")

    progress = MagicMock()

    meta, wd = _execute_fetch(
        config=config,
        interactive_mode_meta=None,
        interactive_mode_wd=None,
        progress=progress,
        verbose=False,
    )

    # Verify fetch command used RSS URL
    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "--rss-url" in cmd
    assert "https://example.com/feed.xml" in cmd


@patch("podx.utils.apply_podcast_config")
@patch("podx.orchestrate._run")
def test_podcast_config_application(mock_run, mock_apply_config):
    """Test that podcast-specific config is applied and updates config dict."""
    config = {
        "show": "My Podcast",
        "rss_url": None,
        "youtube_url": None,
        "date": None,
        "title_contains": None,
        "workdir": Path("/tmp/override"),  # Explicit workdir
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
        "deepcast_model": "gpt-4",
        "deepcast_temp": 0.7,
    }

    # Mock fetch result
    mock_run.return_value = {
        "show": "My Podcast",
        "episode_title": "Episode 1",
        "episode_published": "2025-01-15",
    }

    # Mock podcast config with overrides
    mock_apply_config.return_value = {
        "align": True,  # Override
        "diarize": True,  # Override
        "deepcast": True,  # Override
        "extract_markdown": True,  # Override
        "notion": False,
        "deepcast_model": "gpt-4o",  # Override
        "deepcast_temp": 0.5,  # Override
        "analysis_type": "detailed",  # New field
    }

    progress = MagicMock()

    meta, wd = _execute_fetch(
        config=config,
        interactive_mode_meta=None,
        interactive_mode_wd=None,
        progress=progress,
        verbose=False,
    )

    # Verify config was updated with podcast-specific overrides
    assert config["align"] is True
    assert config["diarize"] is True
    assert config["deepcast"] is True
    assert config["extract_markdown"] is True
    assert config["deepcast_model"] == "gpt-4o"
    assert config["deepcast_temp"] == 0.5
    assert config["yaml_analysis_type"] == "detailed"

    # Verify explicit workdir was used
    assert wd == Path("/tmp/override")


def test_missing_source_raises_error():
    """Test that missing source (show/RSS/YouTube) raises ValidationError."""
    from podx.errors import ValidationError

    config = {
        "show": None,
        "rss_url": None,
        "youtube_url": None,  # All sources missing
        "date": None,
        "title_contains": None,
        "workdir": None,
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
        "deepcast_model": "gpt-4",
        "deepcast_temp": 0.7,
    }

    progress = MagicMock()

    with pytest.raises(ValidationError) as exc_info:
        _execute_fetch(
            config=config,
            interactive_mode_meta=None,
            interactive_mode_wd=None,
            progress=progress,
            verbose=False,
        )

    assert "Either --show, --rss-url, or --youtube-url must be provided" in str(exc_info.value)


@patch("podx.youtube.is_youtube_url")
def test_invalid_youtube_url_raises_error(mock_is_youtube):
    """Test that invalid YouTube URL raises ValidationError."""
    from podx.errors import ValidationError

    config = {
        "youtube_url": "https://notayoutubeurl.com/video",
        "show": None,
        "rss_url": None,
        "date": None,
        "title_contains": None,
        "workdir": None,
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
        "deepcast_model": "gpt-4",
        "deepcast_temp": 0.7,
    }

    # Mock YouTube URL validation to return False
    mock_is_youtube.return_value = False

    progress = MagicMock()

    with pytest.raises(ValidationError) as exc_info:
        _execute_fetch(
            config=config,
            interactive_mode_meta=None,
            interactive_mode_wd=None,
            progress=progress,
            verbose=False,
        )

    assert "Invalid YouTube URL" in str(exc_info.value)


@patch("podx.utils.generate_workdir")
@patch("podx.utils.apply_podcast_config")
@patch("podx.orchestrate._run")
def test_workdir_generation_from_metadata(
    mock_run, mock_apply_config, mock_generate_workdir
):
    """Test that workdir is generated from show name and episode date."""
    config = {
        "show": "Amazing Podcast",
        "rss_url": None,
        "youtube_url": None,
        "date": None,
        "title_contains": None,
        "workdir": None,  # No explicit workdir
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
        "deepcast_model": "gpt-4",
        "deepcast_temp": 0.7,
    }

    # Mock fetch result
    mock_run.return_value = {
        "show": "Amazing Podcast",
        "episode_title": "Great Episode",
        "episode_published": "2025-01-20",
    }

    # Mock podcast config
    mock_apply_config.return_value = {
        "align": False,
        "diarize": False,
        "deepcast": False,
        "extract_markdown": False,
        "notion": False,
    }

    # Mock workdir generation
    expected_wd = Path("/podcasts/Amazing Podcast/2025-01-20")
    mock_generate_workdir.return_value = expected_wd

    progress = MagicMock()

    meta, wd = _execute_fetch(
        config=config,
        interactive_mode_meta=None,
        interactive_mode_wd=None,
        progress=progress,
        verbose=False,
    )

    # Verify generate_workdir was called with show and date
    mock_generate_workdir.assert_called_once_with("Amazing Podcast", "2025-01-20")

    # Verify returned workdir
    assert wd == expected_wd
