"""Unit tests for AsyncPipelineService class."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from podx.services import AsyncPipelineService, AsyncStepExecutor, PipelineConfig


@pytest.mark.asyncio
async def test_basic_pipeline_execution():
    """Test basic async pipeline execution."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_meta = {
        "show": "Test Podcast",
        "episode_title": "Episode 1",
        "episode_published": "2024-10-01",
    }
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello world", "segments": []}

    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch("podx.services.async_pipeline_service.Path.mkdir"):
                    with patch("podx.services.async_pipeline_service.Path.write_text"):
                        mock_fetch.return_value = mock_meta
                        mock_transcode.return_value = mock_audio
                        mock_transcribe.return_value = mock_transcript

                        result = await service.execute()

                        # Verify pipeline completed
                        assert result.duration >= 0
                        assert "fetch" in result.steps_completed
                        assert "transcode" in result.steps_completed
                        assert "transcribe" in result.steps_completed

                        # Verify executor methods were called
                        mock_fetch.assert_called_once()
                        mock_transcode.assert_called_once()
                        mock_transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_align_and_diarize():
    """Test that align and diarize run concurrently when both enabled."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        align=True,
        diarize=True,
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}
    mock_aligned = {"text": "Hello", "segments": [], "aligned": True}
    mock_diarized = {"text": "Hello", "segments": [], "speakers": ["SPEAKER_00"]}

    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch.object(service.executor, "align", new_callable=AsyncMock) as mock_align:
                    with patch.object(service.executor, "diarize", new_callable=AsyncMock) as mock_diarize:
                        with patch("podx.services.async_pipeline_service.Path.mkdir"):
                            with patch("podx.services.async_pipeline_service.Path.write_text"):
                                with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                                    mock_fetch.return_value = mock_meta
                                    mock_transcode.return_value = mock_audio
                                    mock_transcribe.return_value = mock_transcript
                                    mock_align.return_value = mock_aligned
                                    mock_diarize.return_value = mock_diarized

                                    # Use asyncio.gather to verify concurrent execution
                                    with patch("asyncio.gather", wraps=asyncio.gather) as mock_gather:
                                        result = await service.execute()

                                        # Verify both align and diarize completed
                                        assert "align" in result.steps_completed
                                        assert "diarize" in result.steps_completed

                                        # Verify asyncio.gather was called (concurrent execution)
                                        mock_gather.assert_called()


@pytest.mark.asyncio
async def test_pipeline_with_deepcast():
    """Test pipeline with deepcast analysis."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        deepcast=True,
        deepcast_model="gpt-4o",
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}
    mock_deepcast = {"brief": "Test brief", "quotes": []}

    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch.object(service.executor, "deepcast", new_callable=AsyncMock) as mock_deepcast_call:
                    with patch("podx.services.async_pipeline_service.Path.mkdir"):
                        with patch("podx.services.async_pipeline_service.Path.write_text"):
                            with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                                mock_fetch.return_value = mock_meta
                                mock_transcode.return_value = mock_audio
                                mock_transcribe.return_value = mock_transcript
                                mock_deepcast_call.return_value = mock_deepcast

                                result = await service.execute()

                                # Verify deepcast completed
                                assert "deepcast" in result.steps_completed
                                mock_deepcast_call.assert_called_once()

                                # Verify deepcast was called with correct model
                                call_args = mock_deepcast_call.call_args
                                assert call_args[1]["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_progress_callback():
    """Test progress callback is called during execution."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}

    progress_updates = []

    async def on_progress(step: str, status: str):
        """Capture progress updates."""
        progress_updates.append((step, status))

    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch("podx.services.async_pipeline_service.Path.mkdir"):
                    with patch("podx.services.async_pipeline_service.Path.write_text"):
                        with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                            mock_fetch.return_value = mock_meta
                            mock_transcode.return_value = mock_audio
                            mock_transcribe.return_value = mock_transcript

                            await service.execute(progress_callback=on_progress)

                            # Verify progress updates were captured
                            assert len(progress_updates) > 0

                            # Verify expected steps in progress updates
                            steps = [step for step, _ in progress_updates]
                            assert "fetch" in steps
                            assert "transcode" in steps
                            assert "transcribe" in steps


@pytest.mark.asyncio
async def test_batch_processing():
    """Test batch processing with concurrency control."""
    configs = [
        PipelineConfig(show="Podcast 1", date="2024-10-01"),
        PipelineConfig(show="Podcast 2", date="2024-10-01"),
        PipelineConfig(show="Podcast 3", date="2024-10-01"),
    ]

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}

    with patch.object(AsyncStepExecutor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(AsyncStepExecutor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(AsyncStepExecutor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch("podx.services.async_pipeline_service.Path.mkdir"):
                    with patch("podx.services.async_pipeline_service.Path.write_text"):
                        with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                            mock_fetch.return_value = mock_meta
                            mock_transcode.return_value = mock_audio
                            mock_transcribe.return_value = mock_transcript

                            results = await AsyncPipelineService.process_batch(
                                configs, max_concurrent=2
                            )

                            # Verify all 3 episodes were processed
                            assert len(results) == 3

                            # Verify all results are PipelineResult instances
                            for result in results:
                                assert result.duration >= 0
                                assert len(result.steps_completed) > 0


@pytest.mark.asyncio
async def test_batch_processing_with_progress():
    """Test batch processing with progress callback."""
    configs = [
        PipelineConfig(show="Podcast 1", date="2024-10-01"),
        PipelineConfig(show="Podcast 2", date="2024-10-01"),
    ]

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}

    progress_updates = []

    def batch_progress(idx: int, step: str, status: str):
        """Capture batch progress."""
        progress_updates.append((idx, step, status))

    with patch.object(AsyncStepExecutor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(AsyncStepExecutor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(AsyncStepExecutor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch("podx.services.async_pipeline_service.Path.mkdir"):
                    with patch("podx.services.async_pipeline_service.Path.write_text"):
                        with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                            mock_fetch.return_value = mock_meta
                            mock_transcode.return_value = mock_audio
                            mock_transcribe.return_value = mock_transcript

                            await AsyncPipelineService.process_batch(
                                configs, max_concurrent=2, progress_callback=batch_progress
                            )

                            # Verify progress updates for both episodes
                            assert len(progress_updates) > 0

                            # Verify updates include episode indices
                            indices = {idx for idx, _, _ in progress_updates}
                            assert 0 in indices
                            assert 1 in indices


@pytest.mark.asyncio
async def test_graceful_cancellation():
    """Test graceful cancellation support."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        verbose=False,
    )

    service = AsyncPipelineService(config)

    # Create a slow async operation that we can cancel
    async def slow_fetch(*args, **kwargs):
        await asyncio.sleep(10)  # Long operation
        return {"show": "Test", "episode_published": "2024-10-01"}

    with patch.object(service.executor, "fetch", side_effect=slow_fetch):
        # Create task
        task = asyncio.create_task(service.execute())

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()

        # Verify it raises CancelledError
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_youtube_url_mode():
    """Test YouTube URL processing mode."""
    config = PipelineConfig(
        youtube_url="https://www.youtube.com/watch?v=test123",
        model="large-v3-turbo",
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}

    with patch("podx.youtube.is_youtube_url", return_value=True):
        with patch("podx.youtube.get_youtube_metadata") as mock_get_yt:
            with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
                with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                    with patch("podx.services.async_pipeline_service.Path.mkdir"):
                        with patch("podx.services.async_pipeline_service.Path.write_text"):
                            with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                                mock_get_yt.return_value = {
                                    "channel": "Test Channel",
                                    "title": "Test Video",
                                    "upload_date": "2024-10-01",
                                }
                                mock_transcode.return_value = mock_audio
                                mock_transcribe.return_value = mock_transcript

                                result = await service.execute()

                                # Verify YouTube metadata was used
                                assert "fetch" in result.steps_completed
                                mock_get_yt.assert_called_once()


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in pipeline execution."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        verbose=False,
    )

    service = AsyncPipelineService(config)

    # Mock fetch to raise an error
    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = Exception("Test error")

        with pytest.raises(Exception) as exc_info:
            await service.execute()

        assert "Test error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_preprocess_step():
    """Test preprocessing step."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        preprocess=True,
        restore=True,
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}
    mock_preprocessed = {"text": "Hello!", "segments": [], "preprocessed": True}

    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch.object(service.executor, "preprocess", new_callable=AsyncMock) as mock_preprocess:
                    with patch("podx.services.async_pipeline_service.Path.mkdir"):
                        with patch("podx.services.async_pipeline_service.Path.write_text"):
                            with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                                mock_fetch.return_value = mock_meta
                                mock_transcode.return_value = mock_audio
                                mock_transcribe.return_value = mock_transcript
                                mock_preprocess.return_value = mock_preprocessed

                                result = await service.execute()

                                # Verify preprocess completed
                                assert "preprocess" in result.steps_completed
                                mock_preprocess.assert_called_once()

                                # Verify restore flag was passed
                                call_args = mock_preprocess.call_args
                                assert call_args[1]["restore"] is True


@pytest.mark.asyncio
async def test_reuse_existing_transcript():
    """Test reusing existing transcoded audio."""
    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}

    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch("podx.services.async_pipeline_service.Path.mkdir"):
                    with patch("podx.services.async_pipeline_service.Path.write_text"):
                        # Mock existing audio file
                        with patch("podx.services.async_pipeline_service.Path.exists", return_value=True):
                            with patch("podx.services.async_pipeline_service.Path.read_text") as mock_read:
                                mock_fetch.return_value = mock_meta
                                mock_read.return_value = json.dumps(mock_audio)
                                mock_transcribe.return_value = mock_transcript

                                await service.execute()

                                # Verify transcode was NOT called (reused existing)
                                mock_transcode.assert_not_called()

                                # Verify transcribe WAS called with reused audio
                                mock_transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_custom_workdir():
    """Test using custom working directory."""
    custom_wd = Path("/tmp/custom/workdir")

    config = PipelineConfig(
        show="Test Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        workdir=custom_wd,
        verbose=False,
    )

    service = AsyncPipelineService(config)

    mock_meta = {"show": "Test", "episode_published": "2024-10-01"}
    mock_audio = {"audio_path": "/tmp/audio.wav"}
    mock_transcript = {"text": "Hello", "segments": []}

    with patch.object(service.executor, "fetch", new_callable=AsyncMock) as mock_fetch:
        with patch.object(service.executor, "transcode", new_callable=AsyncMock) as mock_transcode:
            with patch.object(service.executor, "transcribe", new_callable=AsyncMock) as mock_transcribe:
                with patch("podx.services.async_pipeline_service.Path.mkdir"):
                    with patch("podx.services.async_pipeline_service.Path.write_text"):
                        with patch("podx.services.async_pipeline_service.Path.exists", return_value=False):
                            mock_fetch.return_value = mock_meta
                            mock_transcode.return_value = mock_audio
                            mock_transcribe.return_value = mock_transcript

                            result = await service.execute()

                            # Verify custom workdir was used
                            assert result.workdir == custom_wd
