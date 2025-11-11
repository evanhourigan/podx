"""Core transcoding engine - pure business logic.

No UI dependencies, no CLI concerns. Just audio transcoding.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from ..logging import get_logger

logger = get_logger(__name__)

# Type aliases
AudioFormat = Literal["wav16", "mp3", "aac"]


class TranscodeError(Exception):
    """Raised when transcoding fails."""

    pass


class TranscodeEngine:
    """Pure transcoding logic with no UI dependencies.

    Can be used by CLI, TUI studio, web API, or any other interface.
    """

    def __init__(self, format: AudioFormat = "wav16", bitrate: str = "128k"):
        """Initialize transcoding engine.

        Args:
            format: Output format (wav16, mp3, or aac)
            bitrate: Bitrate for compressed formats
        """
        self.format = format
        self.bitrate = bitrate

    def transcode(
        self,
        source_path: Path,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Transcode audio file to target format.

        Args:
            source_path: Path to source audio file
            output_dir: Output directory (defaults to source directory)

        Returns:
            AudioMeta dictionary with audio_path, format, sample_rate, channels

        Raises:
            TranscodeError: If transcoding fails
            FileNotFoundError: If source file doesn't exist
        """
        # Validate source
        if not source_path.exists():
            raise FileNotFoundError(f"Source audio file not found: {source_path}")

        # Determine output directory
        if output_dir is None:
            output_dir = source_path.parent

        output_dir.mkdir(parents=True, exist_ok=True)

        # Transcode based on format
        if self.format == "wav16":
            return self._transcode_wav16(source_path, output_dir)
        elif self.format == "mp3":
            return self._transcode_mp3(source_path, output_dir)
        elif self.format == "aac":
            return self._transcode_aac(source_path, output_dir)
        else:
            raise ValueError(f"Unsupported format: {self.format}")

    def _transcode_wav16(self, source: Path, output_dir: Path) -> Dict[str, Any]:
        """Transcode to 16kHz mono WAV."""
        output = (output_dir / source.stem).with_suffix(".wav")

        try:
            self._run_ffmpeg(
                [
                    "-y",
                    "-i",
                    str(source),
                    "-ac",
                    "1",  # Mono
                    "-ar",
                    "16000",  # 16kHz
                    "-vn",  # No video
                    str(output),
                ]
            )
        except subprocess.CalledProcessError as e:
            raise TranscodeError(f"WAV16 transcoding failed: {e.stderr}")

        return {
            "audio_path": str(output.resolve()),
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav16",
        }

    def _transcode_mp3(self, source: Path, output_dir: Path) -> Dict[str, Any]:
        """Transcode to MP3."""
        output = (output_dir / source.stem).with_suffix(".mp3")

        try:
            self._run_ffmpeg(
                [
                    "-y",
                    "-i",
                    str(source),
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    self.bitrate,
                    str(output),
                ]
            )
        except subprocess.CalledProcessError as e:
            raise TranscodeError(f"MP3 transcoding failed: {e.stderr}")

        # Probe actual metadata
        probed = self._probe_audio_metadata(output)

        return {
            "audio_path": str(output.resolve()),
            "format": "mp3",
            **probed,
        }

    def _transcode_aac(self, source: Path, output_dir: Path) -> Dict[str, Any]:
        """Transcode to AAC."""
        output = (output_dir / source.stem).with_suffix(".m4a")

        try:
            self._run_ffmpeg(
                [
                    "-y",
                    "-i",
                    str(source),
                    "-c:a",
                    "aac",
                    "-b:a",
                    self.bitrate,
                    str(output),
                ]
            )
        except subprocess.CalledProcessError as e:
            raise TranscodeError(f"AAC transcoding failed: {e.stderr}")

        # Probe actual metadata
        probed = self._probe_audio_metadata(output)

        return {
            "audio_path": str(output.resolve()),
            "format": "aac",
            **probed,
        }

    def _run_ffmpeg(self, args: list[str]) -> None:
        """Run ffmpeg command with error handling.

        Args:
            args: ffmpeg arguments

        Raises:
            subprocess.CalledProcessError: If ffmpeg fails
        """
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error"] + args,
            capture_output=True,
            text=True,
            check=True,  # Raise on non-zero exit
        )

    def _probe_audio_metadata(self, path: Path) -> Dict[str, Any]:
        """Probe audio file for sample rate and channels.

        Args:
            path: Path to audio file

        Returns:
            Dictionary with sample_rate and channels (if available)
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=sample_rate,channels",
                    "-of",
                    "default=nw=1:nk=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            values = [v for v in result.stdout.strip().splitlines() if v]
            if len(values) >= 2:
                return {
                    "sample_rate": int(values[0]),
                    "channels": int(values[1]),
                }
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.debug(f"Failed to probe audio metadata: {e}")

        return {}


# Convenience functions for direct use
def transcode_to_wav16(
    source: Path, output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Transcode audio to 16kHz mono WAV.

    Args:
        source: Source audio file
        output_dir: Output directory (defaults to source directory)

    Returns:
        AudioMeta dictionary
    """
    engine = TranscodeEngine(format="wav16")
    return engine.transcode(source, output_dir)


def transcode_to_mp3(
    source: Path, output_dir: Optional[Path] = None, bitrate: str = "128k"
) -> Dict[str, Any]:
    """Transcode audio to MP3.

    Args:
        source: Source audio file
        output_dir: Output directory (defaults to source directory)
        bitrate: MP3 bitrate

    Returns:
        AudioMeta dictionary
    """
    engine = TranscodeEngine(format="mp3", bitrate=bitrate)
    return engine.transcode(source, output_dir)


def transcode_to_aac(
    source: Path, output_dir: Optional[Path] = None, bitrate: str = "128k"
) -> Dict[str, Any]:
    """Transcode audio to AAC.

    Args:
        source: Source audio file
        output_dir: Output directory (defaults to source directory)
        bitrate: AAC bitrate

    Returns:
        AudioMeta dictionary
    """
    engine = TranscodeEngine(format="aac", bitrate=bitrate)
    return engine.transcode(source, output_dir)
