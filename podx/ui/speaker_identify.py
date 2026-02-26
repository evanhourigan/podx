"""Interactive speaker identification.

Prompts user to identify speakers based on sample utterances.
Port from talkwise/core/speaker_identify.py.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel

console = Console()

# Commands that won't be interpreted as speaker names
MORE_COMMANDS = {"?", "more", "m"}
PLAY_COMMANDS = {"play", "p"}
DEFAULT_SAMPLES = 7
EXTRA_SAMPLES = 7  # Additional samples when user requests more
MIN_UTTERANCE_LENGTH = 30  # Minimum chars for meaningful sample
MAX_DISPLAY_LENGTH = 200  # Max chars to display per utterance


def get_speaker_samples(
    segments: List[Dict[str, Any]],
    max_samples: int = DEFAULT_SAMPLES,
    min_length: int = MIN_UTTERANCE_LENGTH,
) -> Dict[str, List[Tuple[str, int]]]:
    """Extract sample utterances for each speaker, preferring longer ones.

    Args:
        segments: List of transcript segments
        max_samples: Maximum samples per speaker
        min_length: Minimum character length for utterances

    Returns:
        Dict mapping speaker ID to list of (utterance, segment_index) tuples
    """
    # Collect all candidate utterances per speaker with their lengths
    candidates: Dict[str, List[Tuple[str, int, int]]] = {}  # speaker -> [(text, length, idx)]

    for idx, seg in enumerate(segments):
        speaker = seg.get("speaker", "")
        if not speaker:
            continue
        text = seg.get("text", "").strip()
        if len(text) >= min_length:
            if speaker not in candidates:
                candidates[speaker] = []
            candidates[speaker].append((text, len(text), idx))

    # Sort by length (descending) and take top samples
    samples: Dict[str, List[Tuple[str, int]]] = {}
    for speaker, utterances in candidates.items():
        # Sort by length descending to prefer longer utterances
        sorted_utterances = sorted(utterances, key=lambda x: -x[1])
        # Take top max_samples, keep (text, original_index) for ordering
        top = sorted_utterances[:max_samples]
        # Re-sort by original index so they appear in conversation order
        top_by_order = sorted(top, key=lambda x: x[2])
        samples[speaker] = [(text, idx) for text, _, idx in top_by_order]

    return samples


def get_all_speaker_utterances(
    segments: List[Dict[str, Any]],
    speaker: str,
    min_length: int = MIN_UTTERANCE_LENGTH,
) -> List[Tuple[str, int]]:
    """Get ALL utterances for a speaker (for 'more' requests).

    Args:
        segments: List of transcript segments
        speaker: Speaker ID to get utterances for
        min_length: Minimum character length

    Returns:
        List of (utterance, segment_index) tuples in conversation order
    """
    utterances = []
    for idx, seg in enumerate(segments):
        if seg.get("speaker") == speaker:
            text = seg.get("text", "").strip()
            if len(text) >= min_length:
                utterances.append((text, idx))
    return utterances


def _format_timecode(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS timecode."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _display_utterances(
    utterances: List[Tuple[str, int]],
    segments: List[Dict[str, Any]],
    start_num: int = 1,
) -> None:
    """Display a list of utterances with numbering and timecodes.

    Args:
        utterances: List of (text, segment_index) tuples
        segments: Full segments list to look up timecodes
        start_num: Starting number for display
    """
    for i, (text, seg_idx) in enumerate(utterances, start_num):
        # Get timecode from segment
        start_time = segments[seg_idx].get("start", 0)
        timecode = _format_timecode(start_time)

        # Truncate for display but show more than before
        display_text = (
            text if len(text) <= MAX_DISPLAY_LENGTH else text[:MAX_DISPLAY_LENGTH] + "..."
        )
        console.print(f'  {i}. [cyan]{timecode}[/cyan] [dim]"{display_text}"[/dim]')


def _play_speaker_sample(
    sample_utterance: Tuple[str, int],
    segments: List[Dict[str, Any]],
    audio_path: Path,
    temp_clips: List[Path],
) -> None:
    """Extract and play an audio clip for a sample utterance.

    Args:
        sample_utterance: (text, segment_index) tuple
        segments: Full segments list to look up timestamps
        audio_path: Path to the source audio file
        temp_clips: List to track temporary clip files for cleanup
    """
    from podx.core.audio_player import (
        CLIP_PADDING_SECONDS,
        AudioPlaybackError,
        extract_audio_clip,
        play_audio_file,
    )

    text, seg_idx = sample_utterance
    seg = segments[seg_idx]
    start = seg.get("start", 0)
    end = seg.get("end", start + 15.0)

    clip_start = max(0, start - CLIP_PADDING_SECONDS)
    clip_end = end + CLIP_PADDING_SECONDS

    try:
        console.print("[dim]Extracting clip...[/dim]")
        clip_path = extract_audio_clip(audio_path, clip_start, clip_end)
        temp_clips.append(clip_path)
        console.print("[dim]Playing audio...[/dim]")
        play_audio_file(clip_path)
    except AudioPlaybackError as e:
        console.print(f"[yellow]Audio error:[/yellow] {e}")


def identify_speakers_interactive(
    segments: List[Dict[str, Any]],
    audio_path: Optional[Path] = None,
) -> Dict[str, str]:
    """Interactively prompt user to identify speakers.

    Shows sample utterances for each speaker and asks for names.
    User can type '?' or 'more' to see additional utterances,
    or 'play'/'p' to hear audio clips of displayed samples.

    Args:
        segments: List of transcript segments
        audio_path: Optional path to source audio file for playback

    Returns:
        Mapping of SPEAKER_XX -> actual name
    """
    from podx.core.audio_player import cleanup_temp_clips

    samples = get_speaker_samples(segments)

    # Skip if no speakers to identify
    if not samples:
        return {}

    speaker_names: Dict[str, str] = {}
    temp_clips: List[Path] = []
    playback_available = audio_path is not None and audio_path.exists()

    try:
        console.print()
        play_hint = ", 'play' to hear audio" if playback_available else ""
        console.print(
            Panel(
                "[bold]Speaker Identification[/bold]\n"
                "Identify each speaker based on sample utterances.\n"
                f"[dim]Press Enter to keep original ID, '?' for more samples{play_hint}.[/dim]",
                border_style="cyan",
            )
        )
        console.print()

        for speaker_id in sorted(samples.keys()):
            initial_utterances = samples[speaker_id]

            # Skip speakers with no displayable utterances
            if not initial_utterances:
                console.print(f"[dim]Skipping {speaker_id} (no utterances to display)[/dim]")
                speaker_names[speaker_id] = speaker_id  # Keep original ID
                continue

            shown_count = len(initial_utterances)
            # Track all displayed utterances for this speaker (for play requests)
            displayed_utterances: List[Tuple[str, int]] = list(initial_utterances)

            console.print(f"[bold cyan]{speaker_id}[/bold cyan] said:")
            _display_utterances(initial_utterances, segments)

            # Track all utterances for this speaker (for "more" requests)
            all_utterances: List[Tuple[str, int]] = []
            all_loaded = False

            while True:
                try:
                    play_suffix = "/play" if playback_available else ""
                    console.print(
                        f"\nWho is {speaker_id}? [dim](?{play_suffix} for help)[/dim] ", end=""
                    )
                    name = input().strip()
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Cancelled[/dim]")
                    # Return what we have so far, keeping remaining as original
                    for remaining_speaker in samples.keys():
                        if remaining_speaker not in speaker_names:
                            speaker_names[remaining_speaker] = remaining_speaker
                    return speaker_names

                # Check if user wants more utterances
                if name.lower() in MORE_COMMANDS:
                    # Lazy load all utterances on first "more" request
                    if not all_loaded:
                        all_utterances = get_all_speaker_utterances(segments, speaker_id)
                        all_loaded = True

                    # Show next batch
                    remaining = all_utterances[shown_count:]
                    if remaining:
                        next_batch = remaining[:EXTRA_SAMPLES]
                        console.print(f"\n[dim]Additional utterances for {speaker_id}:[/dim]")
                        _display_utterances(next_batch, segments, start_num=shown_count + 1)
                        displayed_utterances.extend(next_batch)
                        shown_count += len(next_batch)

                        if shown_count >= len(all_utterances):
                            console.print("[dim](No more utterances available)[/dim]")
                    else:
                        console.print("[dim](No more utterances available)[/dim]")
                    continue

                # Check if user wants to play audio
                if name.lower() in PLAY_COMMANDS:
                    if not playback_available:
                        console.print("[dim]No audio file available for playback.[/dim]")
                        continue

                    console.print(
                        f"[dim]Which sample? (1-{len(displayed_utterances)}):[/dim] ", end=""
                    )
                    try:
                        choice = input().strip()
                    except (KeyboardInterrupt, EOFError):
                        continue

                    if not choice:
                        continue

                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(displayed_utterances):
                            _play_speaker_sample(
                                displayed_utterances[idx],
                                segments,
                                audio_path,
                                temp_clips,
                            )
                        else:
                            console.print(f"[red]Enter 1-{len(displayed_utterances)}[/red]")
                    except ValueError:
                        console.print("[red]Enter a number[/red]")
                    continue

                # Accept the name (or keep speaker ID if empty)
                speaker_names[speaker_id] = name if name else speaker_id
                console.print()
                break

        return speaker_names

    finally:
        cleanup_temp_clips(temp_clips)


def apply_speaker_names(
    segments: List[Dict[str, Any]], speaker_map: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Replace speaker IDs with actual names in segments.

    Args:
        segments: List of transcript segments
        speaker_map: Mapping of speaker IDs to names

    Returns:
        Updated segments list with names applied
    """
    for seg in segments:
        old_speaker = seg.get("speaker", "")
        if old_speaker and old_speaker in speaker_map:
            seg["speaker"] = speaker_map[old_speaker]
    return segments


def has_generic_speaker_ids(segments: List[Dict[str, Any]]) -> bool:
    """Check if transcript has generic SPEAKER_XX style IDs.

    Returns True if any segment has a speaker ID matching SPEAKER_XX pattern.
    """
    import re

    pattern = re.compile(r"^SPEAKER_\d+$")
    for seg in segments:
        speaker = seg.get("speaker", "")
        if speaker and pattern.match(speaker):
            return True
    return False
