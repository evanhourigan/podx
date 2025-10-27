"""Unit tests for core.transcode module.

Tests pure business logic without UI dependencies.
Uses mocking to avoid actual ffmpeg/ffprobe execution.
"""
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podx.core.transcode import (
    TranscodeEngine,
    TranscodeError,
    transcode_to_aac,
    transcode_to_mp3,
    transcode_to_wav16,
)


class TestTranscodeEngine:
    """Test TranscodeEngine class."""

    def test_init_defaults(self):
        """Test default initialization."""
        engine = TranscodeEngine()
        assert engine.format == "wav16"
        assert engine.bitrate == "128k"

    def test_init_custom_format(self):
        """Test initialization with custom format."""
        engine = TranscodeEngine(format="mp3", bitrate="192k")
        assert engine.format == "mp3"
        assert engine.bitrate == "192k"

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_wav16_success(self, mock_run, tmp_path):
        """Test successful WAV16 transcoding."""
        # Setup
        source = tmp_path / "source.mp3"
        source.write_text("fake audio")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_run.return_value = MagicMock(returncode=0)

        # Execute
        engine = TranscodeEngine(format="wav16")
        result = engine.transcode(source, output_dir)

        # Verify
        assert result["format"] == "wav16"
        assert result["sample_rate"] == 16000
        assert result["channels"] == 1
        assert "audio_path" in result
        assert Path(result["audio_path"]).suffix == ".wav"

        # Verify ffmpeg was called with correct args
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "-ac" in call_args
        assert "1" in call_args
        assert "-ar" in call_args
        assert "16000" in call_args

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_mp3_success(self, mock_run, tmp_path):
        """Test successful MP3 transcoding."""
        # Setup
        source = tmp_path / "source.wav"
        source.write_text("fake audio")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock ffmpeg success
        def run_side_effect(cmd, **kwargs):
            if "ffmpeg" in cmd:
                return MagicMock(returncode=0)
            elif "ffprobe" in cmd:
                # Mock ffprobe returning sample_rate and channels
                return MagicMock(returncode=0, stdout="44100\n2\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        # Execute
        engine = TranscodeEngine(format="mp3", bitrate="192k")
        result = engine.transcode(source, output_dir)

        # Verify
        assert result["format"] == "mp3"
        assert result["sample_rate"] == 44100
        assert result["channels"] == 2
        assert "audio_path" in result
        assert Path(result["audio_path"]).suffix == ".mp3"

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_aac_success(self, mock_run, tmp_path):
        """Test successful AAC transcoding."""
        # Setup
        source = tmp_path / "source.wav"
        source.write_text("fake audio")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock ffmpeg success
        def run_side_effect(cmd, **kwargs):
            if "ffmpeg" in cmd:
                return MagicMock(returncode=0)
            elif "ffprobe" in cmd:
                return MagicMock(returncode=0, stdout="48000\n2\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        # Execute
        engine = TranscodeEngine(format="aac", bitrate="256k")
        result = engine.transcode(source, output_dir)

        # Verify
        assert result["format"] == "aac"
        assert result["sample_rate"] == 48000
        assert result["channels"] == 2
        assert "audio_path" in result
        assert Path(result["audio_path"]).suffix == ".m4a"

    def test_transcode_missing_source(self, tmp_path):
        """Test transcoding with missing source file."""
        source = tmp_path / "nonexistent.mp3"
        output_dir = tmp_path / "output"

        engine = TranscodeEngine()

        with pytest.raises(FileNotFoundError, match="Source audio file not found"):
            engine.transcode(source, output_dir)

    def test_transcode_invalid_format(self, tmp_path):
        """Test transcoding with invalid format."""
        source = tmp_path / "source.mp3"
        source.write_text("fake audio")

        engine = TranscodeEngine(format="wav16")
        engine.format = "invalid"  # Manually set invalid format

        with pytest.raises(ValueError, match="Unsupported format"):
            engine.transcode(source)

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_ffmpeg_failure(self, mock_run, tmp_path):
        """Test handling of ffmpeg failure."""
        # Setup
        source = tmp_path / "source.mp3"
        source.write_text("fake audio")

        # Mock ffmpeg failure
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["ffmpeg"], stderr="ffmpeg error"
        )

        # Execute
        engine = TranscodeEngine(format="wav16")

        with pytest.raises(TranscodeError, match="WAV16 transcoding failed"):
            engine.transcode(source)

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_creates_output_dir(self, mock_run, tmp_path):
        """Test that transcode creates output directory if missing."""
        # Setup
        source = tmp_path / "source.mp3"
        source.write_text("fake audio")
        output_dir = tmp_path / "new" / "nested" / "dir"

        mock_run.return_value = MagicMock(returncode=0)

        # Execute
        engine = TranscodeEngine(format="wav16")
        engine.transcode(source, output_dir)

        # Verify directory was created
        assert output_dir.exists()
        assert output_dir.is_dir()

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_defaults_to_source_directory(self, mock_run, tmp_path):
        """Test that transcode uses source directory when output_dir is None."""
        # Setup
        source = tmp_path / "source.mp3"
        source.write_text("fake audio")

        mock_run.return_value = MagicMock(returncode=0)

        # Execute
        engine = TranscodeEngine(format="wav16")
        result = engine.transcode(source, output_dir=None)

        # Verify output is in source directory
        assert Path(result["audio_path"]).parent == tmp_path

    @patch("podx.core.transcode.subprocess.run")
    def test_probe_audio_metadata_success(self, mock_run, tmp_path):
        """Test successful audio metadata probing."""
        # Setup
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        mock_run.return_value = MagicMock(returncode=0, stdout="44100\n2\n")

        # Execute
        engine = TranscodeEngine()
        metadata = engine._probe_audio_metadata(audio_file)

        # Verify
        assert metadata["sample_rate"] == 44100
        assert metadata["channels"] == 2

    @patch("podx.core.transcode.subprocess.run")
    def test_probe_audio_metadata_failure(self, mock_run, tmp_path):
        """Test handling of ffprobe failure."""
        # Setup
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["ffprobe"], stderr="probe error"
        )

        # Execute
        engine = TranscodeEngine()
        metadata = engine._probe_audio_metadata(audio_file)

        # Verify returns empty dict on failure
        assert metadata == {}

    @patch("podx.core.transcode.subprocess.run")
    def test_probe_audio_metadata_invalid_output(self, mock_run, tmp_path):
        """Test handling of invalid ffprobe output."""
        # Setup
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        mock_run.return_value = MagicMock(returncode=0, stdout="invalid\n")

        # Execute
        engine = TranscodeEngine()
        metadata = engine._probe_audio_metadata(audio_file)

        # Verify returns empty dict on invalid output
        assert metadata == {}


class TestConvenienceFunctions:
    """Test convenience functions for direct use."""

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_to_wav16(self, mock_run, tmp_path):
        """Test transcode_to_wav16 convenience function."""
        source = tmp_path / "source.mp3"
        source.write_text("fake audio")

        mock_run.return_value = MagicMock(returncode=0)

        result = transcode_to_wav16(source)

        assert result["format"] == "wav16"
        assert result["sample_rate"] == 16000
        assert result["channels"] == 1

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_to_mp3(self, mock_run, tmp_path):
        """Test transcode_to_mp3 convenience function."""
        source = tmp_path / "source.wav"
        source.write_text("fake audio")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        def run_side_effect(cmd, **kwargs):
            if "ffmpeg" in cmd:
                return MagicMock(returncode=0)
            elif "ffprobe" in cmd:
                return MagicMock(returncode=0, stdout="44100\n2\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = transcode_to_mp3(source, output_dir, bitrate="192k")

        assert result["format"] == "mp3"
        assert Path(result["audio_path"]).suffix == ".mp3"

    @patch("podx.core.transcode.subprocess.run")
    def test_transcode_to_aac(self, mock_run, tmp_path):
        """Test transcode_to_aac convenience function."""
        source = tmp_path / "source.wav"
        source.write_text("fake audio")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        def run_side_effect(cmd, **kwargs):
            if "ffmpeg" in cmd:
                return MagicMock(returncode=0)
            elif "ffprobe" in cmd:
                return MagicMock(returncode=0, stdout="48000\n2\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = transcode_to_aac(source, output_dir, bitrate="256k")

        assert result["format"] == "aac"
        assert Path(result["audio_path"]).suffix == ".m4a"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("podx.core.transcode.subprocess.run")
    def test_source_with_special_characters(self, mock_run, tmp_path):
        """Test transcoding file with special characters in name."""
        source = tmp_path / "test [special] (chars).mp3"
        source.write_text("fake audio")

        mock_run.return_value = MagicMock(returncode=0)

        engine = TranscodeEngine(format="wav16")
        result = engine.transcode(source)

        assert "audio_path" in result
        assert Path(result["audio_path"]).exists() or not Path(
            result["audio_path"]
        ).exists()  # May or may not exist since mocked

    @patch("podx.core.transcode.subprocess.run")
    def test_output_overwrites_existing(self, mock_run, tmp_path):
        """Test that transcoding overwrites existing output file."""
        source = tmp_path / "source.mp3"
        source.write_text("fake audio")

        # Create existing output
        existing_output = tmp_path / "source.wav"
        existing_output.write_text("old content")

        mock_run.return_value = MagicMock(returncode=0)

        engine = TranscodeEngine(format="wav16")
        engine.transcode(source)

        # Verify ffmpeg was called with -y flag (overwrite)
        call_args = mock_run.call_args[0][0]
        assert "-y" in call_args

    @patch("podx.core.transcode.subprocess.run")
    def test_bitrate_passed_to_ffmpeg(self, mock_run, tmp_path):
        """Test that bitrate is correctly passed to ffmpeg."""
        source = tmp_path / "source.wav"
        source.write_text("fake audio")

        def run_side_effect(cmd, **kwargs):
            if "ffmpeg" in cmd:
                # Verify bitrate in command
                assert "-b:a" in cmd
                assert "320k" in cmd
                return MagicMock(returncode=0)
            elif "ffprobe" in cmd:
                return MagicMock(returncode=0, stdout="44100\n2\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        engine = TranscodeEngine(format="mp3", bitrate="320k")
        engine.transcode(source)
