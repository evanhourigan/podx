"""Audio playback utilities for speaker verification."""

import platform
import subprocess
import tempfile
from pathlib import Path
from typing import List

from podx.logging import get_logger

logger = get_logger(__name__)

CLIP_PADDING_SECONDS = 2.0


class AudioPlaybackError(Exception):
    """Raised when audio playback fails."""

    pass


def extract_audio_clip(
    audio_path: Path,
    start_seconds: float,
    end_seconds: float,
) -> Path:
    """Extract a short audio clip using FFmpeg.

    Args:
        audio_path: Path to the source audio file
        start_seconds: Start time in seconds
        end_seconds: End time in seconds

    Returns:
        Path to the temporary clip file

    Raises:
        AudioPlaybackError: If FFmpeg extraction fails
    """
    start_seconds = max(0, start_seconds)
    duration = end_seconds - start_seconds

    fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="podx_clip_")
    output_path = Path(temp_path)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(audio_path),
                "-ss",
                str(start_seconds),
                "-t",
                str(duration),
                "-ar",
                "44100",
                "-ac",
                "2",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        output_path.unlink(missing_ok=True)
        raise AudioPlaybackError(f"FFmpeg error: {e.stderr.decode()}")
    except FileNotFoundError:
        output_path.unlink(missing_ok=True)
        raise AudioPlaybackError("FFmpeg not found. Please install FFmpeg.")

    return output_path


def play_audio_file(audio_path: Path) -> None:
    """Open audio with system default player (async).

    Args:
        audio_path: Path to the audio file to play

    Raises:
        AudioPlaybackError: If the platform is not supported
    """
    system = platform.system()

    if system == "Darwin":
        subprocess.Popen(
            ["open", str(audio_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    elif system == "Linux":
        subprocess.Popen(
            ["xdg-open", str(audio_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    elif system == "Windows":
        subprocess.Popen(
            ["start", "", str(audio_path)],
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        raise AudioPlaybackError(f"Unsupported platform: {system}")


def cleanup_temp_clips(clip_paths: List[Path]) -> None:
    """Remove temporary audio clips.

    Args:
        clip_paths: List of paths to temporary clip files
    """
    for path in clip_paths:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass  # Best effort cleanup
