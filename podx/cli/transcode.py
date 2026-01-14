"""CLI wrapper for transcode command.

Extract and convert audio from video/audio files for transcription.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.core.transcode import TranscodeEngine, TranscodeError
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger

logger = get_logger(__name__)
console = Console()


@click.command(context_settings={"max_content_width": 120})
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    help="Output directory (defaults to source file's directory)",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["wav", "mp3", "aac"]),
    default="wav",
    help="Output format (default: wav - optimal for transcription)",
)
@click.option(
    "--bitrate",
    default="128k",
    help="Bitrate for mp3/aac formats (default: 128k)",
)
def main(
    source: Path,
    output: Optional[Path],
    output_format: str,
    bitrate: str,
) -> None:
    """Extract and transcode audio from video/audio files.

    Converts any video or audio file to a format suitable for transcription.
    The default WAV output (16kHz mono) is optimal for Whisper ASR.

    \b
    Examples:
      podx transcode video.mp4                    # Extract to video.wav in same dir
      podx transcode video.mp4 -o ./episode/      # Extract to ./episode/video.wav
      podx transcode audio.m4a -f mp3             # Convert to MP3
      podx transcode recording.mov -o ./ep/ -f wav  # Video to WAV

    \b
    Supported input formats:
      Video: mp4, mkv, mov, avi, webm, etc.
      Audio: mp3, m4a, aac, ogg, flac, wav, etc.

    \b
    Output formats:
      wav   16kHz mono WAV - optimal for Whisper (default)
      mp3   MP3 with configurable bitrate
      aac   AAC/M4A with configurable bitrate
    """
    # Map CLI format names to engine format names
    format_map = {"wav": "wav16", "mp3": "mp3", "aac": "aac"}
    engine_format = format_map[output_format]

    console.print(f"[cyan]Transcoding:[/cyan] {source.name}")
    console.print(f"[dim]Format: {output_format.upper()}[/dim]")

    try:
        engine = TranscodeEngine(format=engine_format, bitrate=bitrate)
        result = engine.transcode(source, output)

        output_path = Path(result["audio_path"])
        console.print(f"\n[green]✓ Created:[/green] {output_path}")

        # Show audio info
        if "sample_rate" in result:
            console.print(f"  Sample rate: {result['sample_rate']} Hz")
        if "channels" in result:
            channels = "mono" if result["channels"] == 1 else f"{result['channels']} channels"
            console.print(f"  Channels: {channels}")

        # Show next step hint
        console.print(f"\n[dim]Next: podx transcribe {output_path.parent}/[/dim]")

        sys.exit(ExitCode.SUCCESS)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(ExitCode.USER_ERROR)
    except TranscodeError as e:
        console.print(f"[red]Transcode Error:[/red] {e}")
        console.print("[dim]Make sure ffmpeg is installed: brew install ffmpeg[/dim]")
        sys.exit(ExitCode.PROCESSING_ERROR)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error during transcode")
        sys.exit(ExitCode.SYSTEM_ERROR)


if __name__ == "__main__":
    main()
