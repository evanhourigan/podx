"""Tests for AsyncPodxClient API."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from podx.api import AsyncPodxClient, ClientConfig, DiarizeResponse, TranscribeResponse


class TestAsyncPodxClientInit:
    """Test AsyncPodxClient initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        client = AsyncPodxClient()

        assert client.config is not None
        assert isinstance(client.config, ClientConfig)
        assert client.config.default_model == "base"

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = ClientConfig(default_model="medium", verbose=True)
        client = AsyncPodxClient(config=config)

        assert client.config == config
        assert client.config.default_model == "medium"


class TestAsyncTranscribe:
    """Test async transcribe method."""

    @pytest.mark.asyncio
    async def test_transcribe_success_with_callback(self, tmp_path):
        """Test successful async transcription with progress callback."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        # Create transcript file that will be "created"
        transcript_path = tmp_path / "transcript-output.json"
        transcript_data = {
            "segments": [
                {"text": "Hello", "start": 0.0, "end": 1.0},
                {"text": "World", "start": 1.0, "end": 2.0},
            ],
            "duration": 2.0,
        }
        transcript_path.write_text(json.dumps(transcript_data))

        # Mock subprocess that outputs JSON progress
        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "Loading model", "percent": 10}\n',
                b'{"message": "Transcribing", "percent": 50}\n',
                b'{"message": "Done", "percent": 100}\n',
                b'{"transcript_path": "'
                + str(transcript_path).encode()
                + b'", "duration_seconds": 2}\n',
                b"",  # EOF
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        # Track progress updates
        progress_updates = []

        async def on_progress(update: dict):
            progress_updates.append(update)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            result = await client.transcribe(
                audio_path=str(tmp_path / "audio.mp3"),
                model="base",
                output_dir=str(tmp_path),
                progress_callback=on_progress,
            )

        # Verify result
        assert result.success is True
        assert result.transcript_path == str(transcript_path)
        assert result.duration_seconds == 2

        # Verify progress callbacks were called
        assert len(progress_updates) >= 2
        assert any("Loading model" in str(update) for update in progress_updates)

    @pytest.mark.asyncio
    async def test_transcribe_without_callback(self, tmp_path):
        """Test async transcription without progress callback."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": [], "duration": 0}')

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"transcript_path": "' + str(transcript_path).encode() + b'", "duration_seconds": 0}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            result = await client.transcribe(
                audio_path=str(tmp_path / "audio.mp3"), output_dir=str(tmp_path)
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_transcribe_handles_errors(self, tmp_path):
        """Test async transcription handles errors gracefully."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(side_effect=[b""])
        mock_process.wait = AsyncMock(return_value=1)  # Non-zero exit code
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            result = await client.transcribe(
                audio_path=str(tmp_path / "audio.mp3"), output_dir=str(tmp_path)
            )

        assert result.success is False
        assert result.error is not None


class TestAsyncTranscribeStream:
    """Test async transcribe_stream method."""

    @pytest.mark.asyncio
    async def test_transcribe_stream_yields_progress_and_result(self, tmp_path):
        """Test transcribe_stream yields progress updates and final result."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_path = tmp_path / "transcript.json"
        transcript_data = {"segments": [{"text": "Test", "start": 0.0, "end": 1.0}], "duration": 1.0}
        transcript_path.write_text(json.dumps(transcript_data))

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "Processing", "percent": 50}\n',
                b'{"transcript_path": "' + str(transcript_path).encode() + b'", "duration_seconds": 1}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        progress_count = 0
        final_result = None

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            async for update in client.transcribe_stream(
                audio_path=str(tmp_path / "audio.mp3"), output_dir=str(tmp_path)
            ):
                if isinstance(update, dict):
                    progress_count += 1
                else:
                    final_result = update

        assert progress_count >= 1
        assert final_result is not None
        assert isinstance(final_result, TranscribeResponse)
        assert final_result.success is True


class TestAsyncDiarize:
    """Test async diarize method."""

    @pytest.mark.asyncio
    async def test_diarize_success_with_callback(self, tmp_path):
        """Test successful async diarization with progress callback."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        # Create input transcript
        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": [{"text": "Hello", "start": 0.0, "end": 1.0}]}')

        # Create diarized output
        diarized_path = tmp_path / "transcript-diarized.json"
        diarized_data = {
            "segments": [
                {"text": "Hello", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}
            ],
        }
        diarized_path.write_text(json.dumps(diarized_data))

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "Loading diarization model", "percent": 10}\n',
                b'{"message": "Identifying speakers", "percent": 50}\n',
                b'{"transcript_path": "' + str(diarized_path).encode() + b'", "speakers_found": 1}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        progress_updates = []

        async def on_progress(update: dict):
            progress_updates.append(update)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            result = await client.diarize(
                transcript_path=str(transcript_path),
                audio_path=str(tmp_path / "audio.mp3"),
                progress_callback=on_progress,
            )

        assert result.success is True
        assert result.speakers_found == 1
        assert len(progress_updates) >= 1

    @pytest.mark.asyncio
    async def test_diarize_handles_errors(self, tmp_path):
        """Test async diarization handles errors gracefully."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": []}')

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(side_effect=[b""])
        mock_process.wait = AsyncMock(return_value=1)
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            result = await client.diarize(
                transcript_path=str(transcript_path), audio_path=str(tmp_path / "audio.mp3")
            )

        assert result.success is False
        assert result.error is not None


class TestAsyncDiarizeStream:
    """Test async diarize_stream method."""

    @pytest.mark.asyncio
    async def test_diarize_stream_yields_progress_and_result(self, tmp_path):
        """Test diarize_stream yields progress updates and final result."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": [{"text": "Test", "start": 0.0, "end": 1.0}]}')

        diarized_path = tmp_path / "transcript-diarized.json"
        diarized_path.write_text('{"segments": [{"text": "Test", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]}')

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "Processing", "percent": 50}\n',
                b'{"transcript_path": "' + str(diarized_path).encode() + b'", "speakers_found": 1}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        progress_count = 0
        final_result = None

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            async for update in client.diarize_stream(
                transcript_path=str(transcript_path), audio_path=str(tmp_path / "audio.mp3")
            ):
                if isinstance(update, dict):
                    progress_count += 1
                else:
                    final_result = update

        assert progress_count >= 1
        assert final_result is not None
        assert isinstance(final_result, DiarizeResponse)
        assert final_result.success is True


class TestRunCommandWithProgress:
    """Test _run_command_with_progress helper method."""

    @pytest.mark.asyncio
    async def test_run_command_parses_json_progress(self):
        """Test that command output is parsed as JSON progress."""
        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "step 1", "percent": 25}\n',
                b'{"message": "step 2", "percent": 50}\n',
                b'{"final": "result"}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        progress_updates = []

        async def callback(update: dict):
            progress_updates.append(update)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            result = await client._run_command_with_progress(
                ["echo", "test"], progress_callback=callback
            )

        assert result == {"final": "result"}
        assert len(progress_updates) == 2

    @pytest.mark.asyncio
    async def test_run_command_handles_non_json_lines(self):
        """Test that non-JSON lines are handled gracefully."""
        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b"Some non-JSON output\n",
                b'{"message": "valid json", "percent": 50}\n',
                b'{"final": "result"}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            result = await client._run_command_with_progress(["echo", "test"])

        assert result == {"final": "result"}

    @pytest.mark.asyncio
    async def test_run_command_calls_callback(self):
        """Test that progress callback is called for each progress update."""
        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "update 1"}\n',
                b'{"message": "update 2"}\n',
                b'{"message": "update 3"}\n',
                b'{"final": true}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        callback_calls = []

        async def callback(update: dict):
            callback_calls.append(update)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            await client._run_command_with_progress(["test"], progress_callback=callback)

        # Should have called callback for updates 1, 2, 3 (but not final)
        assert len(callback_calls) == 3


class TestProgressCallbacks:
    """Test progress callback functionality."""

    @pytest.mark.asyncio
    async def test_callback_receives_progress_updates(self, tmp_path):
        """Test that callback receives all progress updates."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": []}')

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "Starting", "percent": 0}\n',
                b'{"message": "Halfway", "percent": 50}\n',
                b'{"message": "Almost done", "percent": 90}\n',
                b'{"transcript_path": "' + str(transcript_path).encode() + b'", "duration_seconds": 0}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        received_messages = []

        async def track_messages(update: dict):
            if "message" in update:
                received_messages.append(update["message"])

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            await client.transcribe(
                audio_path=str(tmp_path / "audio.mp3"),
                output_dir=str(tmp_path),
                progress_callback=track_messages,
            )

        assert "Starting" in received_messages
        assert "Halfway" in received_messages
        assert "Almost done" in received_messages

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, tmp_path):
        """Test that errors in callback don't crash the operation."""
        # Create audio file
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_path = tmp_path / "transcript.json"
        transcript_path.write_text('{"segments": []}')

        mock_process = MagicMock()
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                b'{"message": "test"}\n',
                b'{"transcript_path": "' + str(transcript_path).encode() + b'", "duration_seconds": 0}\n',
                b"",
            ]
        )
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.returncode = 0

        async def failing_callback(update: dict):
            raise ValueError("Callback error")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            client = AsyncPodxClient()
            # Should not raise even though callback raises
            result = await client.transcribe(
                audio_path=str(tmp_path / "audio.mp3"),
                output_dir=str(tmp_path),
                progress_callback=failing_callback,
            )

        # Operation should still succeed
        assert result.success is True
