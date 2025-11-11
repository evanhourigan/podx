"""Tests for the AsyncPodxClient API."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from podx.api import AsyncPodxClient, ClientConfig
from podx.api.models import DiarizeResponse, TranscribeResponse
from podx.errors import ValidationError


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
    async def test_transcribe_success(self, tmp_path):
        """Test successful async transcription."""
        client = AsyncPodxClient()

        # Create audio file
        audio_path = tmp_path / "test.mp3"
        audio_path.write_text("fake audio")

        # Create output transcript
        output_path = tmp_path / "transcript-base.json"
        transcript_data = {
            "segments": [{"text": "Hello", "start": 0, "end": 1}],
            "duration": 1.0,
        }
        output_path.write_text(json.dumps(transcript_data))

        # Mock subprocess
        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            # Mock process output
            final_output = json.dumps({
                "success": True,
                "transcript": transcript_data,
            })
            mock_process.stdout.readline = AsyncMock(
                side_effect=[
                    final_output.encode() + b"\n",
                    b"",  # End of stream
                ]
            )
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            result = await client.transcribe(
                audio_path=audio_path,
                model="base",
                output_dir=tmp_path,
            )

            assert result.success is True
            assert result.model_used == "base"
            assert result.segments_count == 1

    @pytest.mark.asyncio
    async def test_transcribe_with_progress_callback(self, tmp_path):
        """Test transcription with progress callback."""
        client = AsyncPodxClient()

        audio_path = tmp_path / "test.mp3"
        audio_path.write_text("fake audio")

        output_path = tmp_path / "transcript-base.json"
        output_path.write_text(json.dumps({"segments": [], "duration": 0}))

        # Track progress updates
        progress_updates = []

        async def progress_callback(update: dict):
            progress_updates.append(update)

        # Mock subprocess
        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            # Simulate progress updates
            progress1 = json.dumps({"type": "progress", "message": "Loading model..."})
            progress2 = json.dumps({"type": "progress", "message": "Transcribing...", "percent": 50})
            final = json.dumps({"success": True, "transcript": {"segments": [], "duration": 0}})

            mock_process.stdout.readline = AsyncMock(
                side_effect=[
                    progress1.encode() + b"\n",
                    progress2.encode() + b"\n",
                    final.encode() + b"\n",
                    b"",
                ]
            )
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            result = await client.transcribe(
                audio_path=audio_path,
                model="base",
                output_dir=tmp_path,
                progress_callback=progress_callback,
            )

            assert result.success is True
            assert len(progress_updates) == 2
            assert progress_updates[0]["message"] == "Loading model..."
            assert progress_updates[1]["percent"] == 50

    @pytest.mark.asyncio
    async def test_transcribe_validation_error(self):
        """Test transcription fails validation for missing file."""
        client = AsyncPodxClient()

        with pytest.raises(ValidationError, match="Audio file not found"):
            await client.transcribe(
                audio_path="/nonexistent/audio.mp3",
                model="base",
            )

    @pytest.mark.asyncio
    async def test_transcribe_handles_command_error(self, tmp_path):
        """Test transcription handles subprocess errors."""
        client = AsyncPodxClient()

        audio_path = tmp_path / "test.mp3"
        audio_path.write_text("fake audio")

        # Mock subprocess failure
        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            mock_process.stdout.readline = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 1  # Non-zero exit code
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"Command failed")

            result = await client.transcribe(
                audio_path=audio_path,
                model="base",
            )

            assert result.success is False
            assert result.error is not None


class TestAsyncTranscribeStream:
    """Test async transcribe_stream generator method."""

    @pytest.mark.asyncio
    async def test_transcribe_stream_yields_progress_and_result(self, tmp_path):
        """Test streaming transcription yields progress then result."""
        client = AsyncPodxClient()

        audio_path = tmp_path / "test.mp3"
        audio_path.write_text("fake audio")

        output_path = tmp_path / "transcript-base.json"
        transcript_data = {"segments": [{"text": "Test"}], "duration": 1}
        output_path.write_text(json.dumps(transcript_data))

        # Mock subprocess
        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            progress1 = json.dumps({"type": "progress", "message": "Starting..."})
            final = json.dumps({"success": True, "transcript": transcript_data})

            mock_process.stdout.readline = AsyncMock(
                side_effect=[
                    progress1.encode() + b"\n",
                    final.encode() + b"\n",
                    b"",
                ]
            )
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            updates = []
            final_result = None

            async for update in client.transcribe_stream(
                audio_path=audio_path,
                model="base",
                output_dir=tmp_path,
            ):
                if isinstance(update, dict):
                    updates.append(update)
                else:
                    final_result = update

            # Should have progress updates
            assert len(updates) > 0
            # Should have final TranscribeResponse
            assert isinstance(final_result, TranscribeResponse)
            assert final_result.success is True


class TestAsyncDiarize:
    """Test async diarize method."""

    @pytest.mark.asyncio
    async def test_diarize_success(self, tmp_path):
        """Test successful async diarization."""
        client = AsyncPodxClient()

        # Create transcript file
        transcript_path = tmp_path / "transcript.json"
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_data = {
            "audio_path": str(audio_path),
            "segments": [{"text": "Hello"}],
        }
        transcript_path.write_text(json.dumps(transcript_data))

        # Create output
        output_path = tmp_path / "transcript-diarized.json"
        diarized_data = {
            "segments": [
                {"text": "Hello", "speaker": "SPEAKER_00"},
                {"text": "World", "speaker": "SPEAKER_01"},
            ]
        }
        output_path.write_text(json.dumps(diarized_data))

        # Mock subprocess
        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            final = json.dumps({"success": True, "transcript": diarized_data})
            mock_process.stdout.readline = AsyncMock(
                side_effect=[final.encode() + b"\n", b""]
            )
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            result = await client.diarize(
                transcript_path=transcript_path,
                num_speakers=2,
            )

            assert result.success is True
            assert result.speakers_found == 2

    @pytest.mark.asyncio
    async def test_diarize_with_progress_callback(self, tmp_path):
        """Test diarization with progress callback."""
        client = AsyncPodxClient()

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

        progress_updates = []

        async def progress_callback(update: dict):
            progress_updates.append(update)

        # Mock subprocess
        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            progress1 = json.dumps({"type": "progress", "message": "Embedding audio..."})
            final = json.dumps({"success": True, "transcript": {"segments": []}})

            mock_process.stdout.readline = AsyncMock(
                side_effect=[
                    progress1.encode() + b"\n",
                    final.encode() + b"\n",
                    b"",
                ]
            )
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            result = await client.diarize(
                transcript_path=transcript_path,
                progress_callback=progress_callback,
            )

            assert result.success is True
            assert len(progress_updates) == 1
            assert progress_updates[0]["message"] == "Embedding audio..."

    @pytest.mark.asyncio
    async def test_diarize_validation_error(self):
        """Test diarize fails validation for missing transcript."""
        client = AsyncPodxClient()

        with pytest.raises(ValidationError, match="Transcript not found"):
            await client.diarize(transcript_path="/nonexistent/transcript.json")


class TestAsyncDiarizeStream:
    """Test async diarize_stream generator method."""

    @pytest.mark.asyncio
    async def test_diarize_stream_yields_progress_and_result(self, tmp_path):
        """Test streaming diarization yields progress then result."""
        client = AsyncPodxClient()

        transcript_path = tmp_path / "transcript.json"
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_text("fake audio")

        transcript_data = {
            "audio_path": str(audio_path),
            "segments": [],
        }
        transcript_path.write_text(json.dumps(transcript_data))

        output_path = tmp_path / "transcript-diarized.json"
        diarized_data = {"segments": [{"speaker": "SPEAKER_00"}]}
        output_path.write_text(json.dumps(diarized_data))

        # Mock subprocess
        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            progress1 = json.dumps({"type": "progress", "message": "Processing..."})
            final = json.dumps({"success": True, "transcript": diarized_data})

            mock_process.stdout.readline = AsyncMock(
                side_effect=[
                    progress1.encode() + b"\n",
                    final.encode() + b"\n",
                    b"",
                ]
            )
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            updates = []
            final_result = None

            async for update in client.diarize_stream(
                transcript_path=transcript_path,
            ):
                if isinstance(update, dict):
                    updates.append(update)
                else:
                    final_result = update

            assert len(updates) > 0
            assert isinstance(final_result, DiarizeResponse)
            assert final_result.success is True
            assert final_result.speakers_found == 1


class TestAsyncRunCommandWithProgress:
    """Test _run_command_with_progress helper method."""

    @pytest.mark.asyncio
    async def test_run_command_basic(self):
        """Test basic command execution."""
        client = AsyncPodxClient()

        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            output = "command output"
            mock_process.stdout.readline = AsyncMock(
                side_effect=[output.encode() + b"\n", b""]
            )
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            result = await client._run_command_with_progress(
                cmd=["echo", "test"]
            )

            assert result == output

    @pytest.mark.asyncio
    async def test_run_command_with_stdin(self):
        """Test command execution with stdin data."""
        client = AsyncPodxClient()

        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            mock_process.stdout.readline = AsyncMock(side_effect=[b"", b""])
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            mock_process.stdin = MagicMock()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")

            await client._run_command_with_progress(
                cmd=["cat"],
                stdin_data="test input"
            )

            # Verify stdin was written
            mock_process.stdin.write.assert_called_once()
            mock_process.stdin.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_command_handles_failure(self):
        """Test command execution handles failures."""
        client = AsyncPodxClient()

        with patch("podx.api.client.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_exec.return_value = mock_process

            mock_process.stdout.readline = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 1  # Failed
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"Error occurred")

            with pytest.raises(Exception):  # subprocess.CalledProcessError
                await client._run_command_with_progress(cmd=["false"])
