"""Unit tests for AsyncStepExecutor class."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podx.errors import ValidationError
from podx.services import AsyncStepExecutor


@pytest.mark.asyncio
async def test_fetch_with_show():
    """Test async fetch with show name."""
    executor = AsyncStepExecutor(verbose=False)

    mock_result = {
        "show": "Test Podcast",
        "episode_title": "Episode 1",
        "episode_published": "2024-10-01",
    }

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.fetch(show="Test Podcast", date="2024-10-01")

        assert result == mock_result
        mock_run.assert_called_once()

        # Verify command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]  # First positional arg is the command list
        assert "podx-fetch" in cmd
        assert "--show" in cmd
        assert "Test Podcast" in cmd
        assert "--date" in cmd
        assert "2024-10-01" in cmd


@pytest.mark.asyncio
async def test_fetch_with_rss_url():
    """Test async fetch with RSS URL."""
    executor = AsyncStepExecutor(verbose=False)

    mock_result = {"show": "RSS Podcast", "episode_title": "Latest"}

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.fetch(rss_url="https://example.com/feed.xml")

        assert result == mock_result

        # Verify command included RSS URL
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--rss-url" in cmd
        assert "https://example.com/feed.xml" in cmd


@pytest.mark.asyncio
async def test_fetch_no_source_raises_error():
    """Test that fetch without show or rss_url raises ValidationError."""
    executor = AsyncStepExecutor(verbose=False)

    with pytest.raises(ValidationError) as exc_info:
        await executor.fetch()  # No show or rss_url

    assert "Either show or rss_url must be provided" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcode():
    """Test async transcode."""
    executor = AsyncStepExecutor(verbose=False)

    meta = {"audio_path": "/tmp/audio.mp3"}
    mock_result = {"audio_path": "/tmp/audio.wav", "format": "wav16"}

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.transcode(
            meta=meta, fmt="wav16", outdir=Path("/tmp/output")
        )

        assert result == mock_result

        # Verify command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "podx-transcode" in cmd
        assert "--to" in cmd
        assert "wav16" in cmd
        assert "--outdir" in cmd


@pytest.mark.asyncio
async def test_transcribe():
    """Test async transcribe."""
    executor = AsyncStepExecutor(verbose=False)

    audio = {"audio_path": "/tmp/audio.wav"}
    mock_result = {
        "text": "Hello world",
        "segments": [],
        "audio_path": "/tmp/audio.wav",
    }

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.transcribe(
            audio=audio,
            model="large-v3-turbo",
            compute="int8",
            asr_provider="local",
            preset="balanced",
        )

        assert result == mock_result

        # Verify command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "podx-transcribe" in cmd
        assert "--model" in cmd
        assert "large-v3-turbo" in cmd
        assert "--compute" in cmd
        assert "int8" in cmd
        assert "--asr-provider" in cmd
        assert "local" in cmd
        assert "--preset" in cmd
        assert "balanced" in cmd


@pytest.mark.asyncio
async def test_align():
    """Test async align."""
    executor = AsyncStepExecutor(verbose=False)

    transcript = {"text": "Hello world", "segments": []}
    mock_result = {"text": "Hello world", "segments": [], "aligned": True}

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.align(transcript)

        assert result == mock_result

        # Verify command
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "podx-align" in cmd


@pytest.mark.asyncio
async def test_diarize():
    """Test async diarize."""
    executor = AsyncStepExecutor(verbose=False)

    transcript = {"text": "Hello world", "segments": []}
    mock_result = {"text": "Hello world", "segments": [], "speakers": ["SPEAKER_00"]}

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.diarize(transcript)

        assert result == mock_result

        # Verify command
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "podx-diarize" in cmd


@pytest.mark.asyncio
async def test_preprocess():
    """Test async preprocess."""
    executor = AsyncStepExecutor(verbose=False)

    transcript = {"text": "Hello world", "segments": []}
    mock_result = {"text": "Hello world!", "segments": [], "preprocessed": True}

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.preprocess(transcript, restore=True)

        assert result == mock_result

        # Verify command included --restore flag
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "podx-preprocess" in cmd
        assert "--restore" in cmd


@pytest.mark.asyncio
async def test_deepcast():
    """Test async deepcast."""
    executor = AsyncStepExecutor(verbose=False)

    transcript = {"text": "Hello world", "segments": []}
    mock_result = {"brief": "Test brief", "quotes": []}

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        result = await executor.deepcast(
            transcript=transcript,
            model="gpt-4o",
            temperature=0.7,
            analysis_type="detailed",
        )

        assert result == mock_result

        # Verify command structure
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "podx-deepcast" in cmd
        assert "--model" in cmd
        assert "gpt-4o" in cmd
        assert "--temperature" in cmd
        assert "0.7" in cmd
        assert "--analysis-type" in cmd
        assert "detailed" in cmd


@pytest.mark.asyncio
async def test_run_concurrent():
    """Test running multiple operations concurrently."""
    executor = AsyncStepExecutor(verbose=False)

    mock_results = [
        {"show": "Podcast 1", "episode_title": "Episode 1"},
        {"show": "Podcast 2", "episode_title": "Episode 2"},
        {"show": "Podcast 3", "episode_title": "Episode 3"},
    ]

    with patch.object(executor, "_run", new_callable=AsyncMock) as mock_run:
        # Configure mock to return different results for each call
        mock_run.side_effect = mock_results

        # Run 3 fetch operations concurrently
        results = await executor.run_concurrent(
            executor.fetch(show="Podcast 1"),
            executor.fetch(show="Podcast 2"),
            executor.fetch(show="Podcast 3"),
        )

        assert len(results) == 3
        assert results == mock_results
        assert mock_run.call_count == 3


@pytest.mark.asyncio
async def test_run_subprocess_success():
    """Test _run method with successful subprocess execution."""
    executor = AsyncStepExecutor(verbose=False)

    # Mock successful subprocess
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(
        return_value=(
            json.dumps({"result": "success"}).encode(),
            b"",  # stderr
        )
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor._run(["echo", "test"], label="test")

        assert result == {"result": "success"}
        mock_process.communicate.assert_called_once()


@pytest.mark.asyncio
async def test_run_subprocess_failure():
    """Test _run method with failed subprocess execution."""
    executor = AsyncStepExecutor(verbose=False)

    # Mock failed subprocess
    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(
        return_value=(
            b"",  # stdout
            b"Command failed: test error",  # stderr
        )
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(ValidationError) as exc_info:
            await executor._run(["false"], label="test")

        assert "Command failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_subprocess_invalid_json():
    """Test _run method with invalid JSON output."""
    executor = AsyncStepExecutor(verbose=False)

    # Mock subprocess with invalid JSON
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(
        return_value=(
            b"This is not JSON",  # stdout
            b"",  # stderr
        )
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(ValidationError) as exc_info:
            await executor._run(["echo", "test"], label="test")

        assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_with_stdin_payload():
    """Test _run method with stdin payload."""
    executor = AsyncStepExecutor(verbose=False)

    stdin_payload = {"input": "test data"}

    # Mock successful subprocess
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(
        return_value=(
            json.dumps({"result": "processed"}).encode(),
            b"",
        )
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        result = await executor._run(["cat"], stdin_payload=stdin_payload, label="test")

        assert result == {"result": "processed"}

        # Verify stdin was passed
        call_args = mock_process.communicate.call_args
        stdin_data = call_args[1]["input"]  # keyword arg
        assert json.loads(stdin_data) == stdin_payload


@pytest.mark.asyncio
async def test_verbose_mode():
    """Test verbose mode shows output preview."""
    executor = AsyncStepExecutor(verbose=True)

    # Mock successful subprocess
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(
        return_value=(
            json.dumps({"result": "test" * 100}).encode(),  # Long output
            b"",
        )
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with patch("podx.services.async_step_executor.logger") as mock_logger:
            await executor._run(["echo", "test"], label="test")

            # Verify logger was called for verbose output
            assert mock_logger.info.called or mock_logger.debug.called
