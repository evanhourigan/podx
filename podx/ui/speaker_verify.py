"""Interactive speaker verification for chunked diarization.

Walks through each chunk and lets the user verify/correct speaker labels.
Helps fix speaker label swaps that can occur at chunk boundaries.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel

console = Console()

# Display constants
MAX_SAMPLES_PER_SPEAKER = 3
MAX_DISPLAY_LENGTH = 150
MIN_UTTERANCE_LENGTH = 20
LOW_CONFIDENCE_THRESHOLD = 0.75
DEFAULT_CLIP_DURATION = 15.0  # Default clip duration if no end time


def _format_timecode(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS timecode."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_time_range(start_sec: float, end_sec: float) -> str:
    """Format a time range for display."""
    return f"{_format_timecode(start_sec)} - {_format_timecode(end_sec)}"


def _get_speaker_samples(
    segments: List[Dict[str, Any]],
    speaker_id: str,
    max_samples: int = MAX_SAMPLES_PER_SPEAKER,
) -> List[Tuple[float, float, str]]:
    """Get sample utterances for a speaker.

    Args:
        segments: List of transcript segments
        speaker_id: Speaker ID to get samples for
        max_samples: Maximum number of samples to return

    Returns:
        List of (start_time, end_time, text) tuples
    """
    samples = []
    for seg in segments:
        if seg.get("speaker") == speaker_id:
            text = seg.get("text", "").strip()
            if len(text) >= MIN_UTTERANCE_LENGTH:
                start = seg.get("start", 0)
                end = seg.get("end", start + DEFAULT_CLIP_DURATION)
                # Truncate for display
                display_text = (
                    text if len(text) <= MAX_DISPLAY_LENGTH else text[:MAX_DISPLAY_LENGTH] + "..."
                )
                samples.append((start, end, display_text))
                if len(samples) >= max_samples:
                    break
    return samples


def _display_speaker_samples(
    speaker_id: str,
    samples: List[Tuple[float, float, str]],
    speaker_name: Optional[str] = None,
) -> None:
    """Display sample utterances for a speaker (unnumbered).

    Args:
        speaker_id: The speaker ID (e.g., SPEAKER_00)
        samples: List of (start_time, end_time, text) tuples
        speaker_name: Optional display name for the speaker
    """
    display_name = speaker_name if speaker_name else speaker_id
    console.print(f"[bold cyan]{display_name}[/bold cyan]:")
    for start, end, text in samples:
        timecode = _format_timecode(start)
        console.print(f'  [cyan]{timecode}[/cyan] [dim]"{text}"[/dim]')


def _display_speaker_samples_numbered(
    speaker_id: str,
    samples: List[Tuple[float, float, str]],
    start_index: int,
    speaker_name: Optional[str] = None,
) -> int:
    """Display numbered sample utterances for a speaker.

    Args:
        speaker_id: The speaker ID (e.g., SPEAKER_00)
        samples: List of (start_time, end_time, text) tuples
        start_index: Starting index for numbering (0-based)
        speaker_name: Optional display name for the speaker

    Returns:
        Next index after displayed samples
    """
    display_name = speaker_name if speaker_name else speaker_id
    console.print(f"[bold cyan]{display_name}[/bold cyan]:")

    for i, (start, end, text) in enumerate(samples):
        num = start_index + i + 1
        timecode = _format_timecode(start)
        console.print(f'  [yellow]\\[{num}][/yellow] [cyan]{timecode}[/cyan] [dim]"{text}"[/dim]')

    return start_index + len(samples)


def _prompt_play_audio(
    all_samples: List[Tuple[str, float, float, str]],
    audio_path: Path,
    temp_clips: List[Path],
) -> None:
    """Prompt to play audio samples.

    Args:
        all_samples: List of (speaker_id, start, end, text) tuples
        audio_path: Path to the source audio file
        temp_clips: List to track temporary clip files for cleanup
    """
    from podx.core.audio_player import (
        CLIP_PADDING_SECONDS,
        AudioPlaybackError,
        extract_audio_clip,
        play_audio_file,
    )

    while True:
        try:
            console.print(
                "\n[dim]Press \[p] to play a sample, \[Enter] to continue:[/dim] ", end=""
            )
            response = input().strip().lower()

            if not response:
                break

            if response == "p":
                console.print(f"[dim]Which sample? (1-{len(all_samples)}):[/dim] ", end="")
                choice = input().strip()
                if not choice:
                    continue

                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_samples):
                        speaker_id, start, end, text = all_samples[idx]
                        clip_start = max(0, start - CLIP_PADDING_SECONDS)
                        clip_end = end + CLIP_PADDING_SECONDS

                        console.print("[dim]Extracting clip...[/dim]")
                        clip_path = extract_audio_clip(audio_path, clip_start, clip_end)
                        temp_clips.append(clip_path)

                        console.print("[dim]Playing audio...[/dim]")
                        play_audio_file(clip_path)
                    else:
                        console.print(f"[red]Enter 1-{len(all_samples)}[/red]")
                except ValueError:
                    console.print("[red]Enter a number[/red]")
                except AudioPlaybackError as e:
                    console.print(f"[yellow]Audio error:[/yellow] {e}")
        except (KeyboardInterrupt, EOFError):
            break


def _prompt_speaker_name(speaker_id: str) -> str:
    """Prompt user for speaker name.

    Args:
        speaker_id: The speaker ID to identify

    Returns:
        Speaker name entered by user, or original ID if empty
    """
    try:
        console.print(f"\nWho is {speaker_id}? ", end="")
        name = input().strip()
        return name if name else speaker_id
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise


def _prompt_confirm(message: str, default: bool = True) -> bool:
    """Prompt user for confirmation.

    Args:
        message: The confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if confirmed, False otherwise
    """
    default_str = "Y/n" if default else "y/N"
    try:
        console.print(f"\n{message} [{default_str}] ", end="")
        response = input().strip().lower()
        if not response:
            return default
        return response in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise


def _prompt_speaker_correction(
    chunk_segments: List[Dict[str, Any]],
    speaker_names: Dict[str, str],
) -> Optional[Tuple[str, str]]:
    """Prompt user to correct speaker assignment.

    Args:
        chunk_segments: Segments from the current chunk
        speaker_names: Current speaker name mapping

    Returns:
        Tuple of (speaker_a, speaker_b) to swap, or None if cancelled
    """
    # Get unique speakers in this chunk
    speakers_in_chunk = set()
    for seg in chunk_segments:
        speaker = seg.get("speaker")
        if speaker:
            speakers_in_chunk.add(speaker)

    speakers_list = sorted(speakers_in_chunk)
    if len(speakers_list) < 2:
        console.print("[yellow]Only one speaker in this chunk, cannot swap.[/yellow]")
        return None

    # Show options
    console.print("\nWhich speakers should be swapped?")
    for i, spk in enumerate(speakers_list, 1):
        name = speaker_names.get(spk, spk)
        console.print(f"  {i}. {name} ({spk})")

    try:
        console.print("\nEnter two numbers to swap (e.g., '1 2'), or 'c' to cancel: ", end="")
        response = input().strip().lower()

        if response == "c":
            return None

        parts = response.split()
        if len(parts) != 2:
            console.print("[red]Please enter exactly two numbers.[/red]")
            return None

        idx1, idx2 = int(parts[0]) - 1, int(parts[1]) - 1
        if not (0 <= idx1 < len(speakers_list) and 0 <= idx2 < len(speakers_list)):
            console.print("[red]Invalid selection.[/red]")
            return None

        return (speakers_list[idx1], speakers_list[idx2])
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise
    except ValueError:
        console.print("[red]Please enter valid numbers.[/red]")
        return None


def apply_speaker_swap(
    segments: List[Dict[str, Any]],
    chunk_start: float,
    chunk_end: float,
    speaker_a: str,
    speaker_b: str,
) -> None:
    """Swap speaker labels within a chunk's time range.

    Args:
        segments: Full list of transcript segments (modified in place)
        chunk_start: Start time of the chunk
        chunk_end: End time of the chunk
        speaker_a: First speaker to swap
        speaker_b: Second speaker to swap
    """
    for seg in segments:
        seg_start = seg.get("start", 0)
        # Check if segment falls within chunk time range
        if chunk_start <= seg_start < chunk_end:
            if seg.get("speaker") == speaker_a:
                seg["speaker"] = speaker_b
            elif seg.get("speaker") == speaker_b:
                seg["speaker"] = speaker_a

            # Also swap in words if present
            if "words" in seg:
                for word in seg["words"]:
                    if word.get("speaker") == speaker_a:
                        word["speaker"] = speaker_b
                    elif word.get("speaker") == speaker_b:
                        word["speaker"] = speaker_a


def _get_segments_for_chunk(
    segments: List[Dict[str, Any]],
    chunk_start: float,
    chunk_end: float,
) -> List[Dict[str, Any]]:
    """Get segments that fall within a chunk's time range.

    Args:
        segments: Full list of transcript segments
        chunk_start: Start time of the chunk
        chunk_end: End time of the chunk

    Returns:
        List of segments within the time range
    """
    chunk_segments = []
    for seg in segments:
        seg_start = seg.get("start", 0)
        if chunk_start <= seg_start < chunk_end:
            chunk_segments.append(seg)
    return chunk_segments


def verify_chunks(
    chunk_info: List[Dict[str, Any]],
    transcript_segments: List[Dict[str, Any]],
    audio_path: Optional[Path] = None,
) -> Dict[str, str]:
    """Interactive chunk-by-chunk speaker verification.

    Walks through each chunk and lets the user verify/correct speaker labels.

    Args:
        chunk_info: List of chunk metadata from diarization, each containing:
            - index: Chunk index
            - start_time: Start time in seconds
            - end_time: End time in seconds
            - confidence: Match confidence (0-1) for non-first chunks
            - speakers: List of speaker IDs in this chunk
        transcript_segments: List of transcript segments with speaker labels
        audio_path: Optional path to audio file for playback during verification

    Returns:
        Final speaker name mapping (e.g., {"SPEAKER_00": "Lenny Rachitsky"})
    """
    from podx.core.audio_player import cleanup_temp_clips

    speaker_names: Dict[str, str] = {}
    temp_clips: List[Path] = []
    playback_available = audio_path is not None and audio_path.exists()

    try:
        console.print()
        playback_hint = (
            "\n[dim]Press \[p] to play audio samples during verification.[/dim]"
            if playback_available
            else ""
        )
        console.print(
            Panel(
                "[bold]Speaker Verification[/bold]\n"
                "Review speaker assignments for each chunk.\n"
                "[dim]This helps fix speaker label swaps that can occur at chunk boundaries.[/dim]"
                + playback_hint,
                border_style="cyan",
            )
        )

        for chunk in chunk_info:
            chunk_idx = chunk["index"]
            start_time = chunk["start_time"]
            end_time = chunk["end_time"]
            confidence = chunk.get("confidence", 1.0)
            speakers = chunk.get("speakers", [])

            # Get segments for this chunk
            chunk_segments = _get_segments_for_chunk(transcript_segments, start_time, end_time)

            if not chunk_segments:
                continue

            # Display chunk header
            console.print()
            console.print(
                f"[bold]━━━ Chunk {chunk_idx + 1} "
                f"({_format_time_range(start_time, end_time)}) ━━━[/bold]"
            )

            if chunk_idx == 0:
                # First chunk: establish ground truth names
                console.print(f"Found {len(speakers)} speakers. Samples:\n")

                # Collect all samples for playback
                all_samples: List[Tuple[str, float, float, str]] = []
                sample_index = 0

                for speaker_id in sorted(speakers):
                    samples = _get_speaker_samples(chunk_segments, speaker_id)
                    if samples:
                        if playback_available:
                            sample_index = _display_speaker_samples_numbered(
                                speaker_id, samples, sample_index
                            )
                            for start, end, text in samples:
                                all_samples.append((speaker_id, start, end, text))
                        else:
                            _display_speaker_samples(speaker_id, samples)
                        console.print()

                # Offer audio playback if available
                if playback_available and all_samples and audio_path:
                    _prompt_play_audio(all_samples, audio_path, temp_clips)

                # Prompt for names
                for speaker_id in sorted(speakers):
                    name = _prompt_speaker_name(speaker_id)
                    speaker_names[speaker_id] = name
                    console.print(f"  [green]✓[/green] {speaker_id} → {name}")

            else:
                # Subsequent chunks: verify matching
                if confidence < LOW_CONFIDENCE_THRESHOLD:
                    console.print(f"[yellow]⚠ LOW CONFIDENCE ({confidence:.0%})[/yellow]")
                else:
                    console.print(f"Matched to previous chunks (confidence: {confidence:.0%})")

                # Show samples for verification
                console.print()

                # Collect all samples for playback
                all_samples = []
                sample_index = 0

                for speaker_id in sorted(speakers):
                    samples = _get_speaker_samples(chunk_segments, speaker_id)
                    if samples:
                        display_name = speaker_names.get(speaker_id, speaker_id)
                        if playback_available:
                            sample_index = _display_speaker_samples_numbered(
                                speaker_id, samples, sample_index, display_name
                            )
                            for start, end, text in samples:
                                all_samples.append((speaker_id, start, end, text))
                        else:
                            _display_speaker_samples(speaker_id, samples, display_name)

                # Offer audio playback if available
                if playback_available and all_samples and audio_path:
                    _prompt_play_audio(all_samples, audio_path, temp_clips)

                # Ask for confirmation
                if not _prompt_confirm("Correct?"):
                    # User says incorrect - prompt for correction
                    swap = _prompt_speaker_correction(chunk_segments, speaker_names)
                    if swap:
                        speaker_a, speaker_b = swap
                        console.print(
                            f"\n[cyan]↻[/cyan] Swapping {speaker_names.get(speaker_a, speaker_a)} "
                            f"and {speaker_names.get(speaker_b, speaker_b)} for this chunk..."
                        )
                        apply_speaker_swap(
                            transcript_segments, start_time, end_time, speaker_a, speaker_b
                        )
                        console.print("[green]✓[/green] Speakers swapped")

        console.print()
        return speaker_names

    finally:
        # Clean up temporary audio clips
        cleanup_temp_clips(temp_clips)


def apply_speaker_names_to_transcript(
    segments: List[Dict[str, Any]],
    speaker_names: Dict[str, str],
) -> None:
    """Apply speaker names to all segments.

    Args:
        segments: List of transcript segments (modified in place)
        speaker_names: Mapping of speaker IDs to names
    """
    for seg in segments:
        old_speaker = seg.get("speaker", "")
        if old_speaker and old_speaker in speaker_names:
            seg["speaker"] = speaker_names[old_speaker]

        # Also update words if present
        if "words" in seg:
            for word in seg["words"]:
                old_word_speaker = word.get("speaker", "")
                if old_word_speaker and old_word_speaker in speaker_names:
                    word["speaker"] = speaker_names[old_word_speaker]
