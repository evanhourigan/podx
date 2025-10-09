import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

import click

from .cli_shared import print_json, read_stdin_json
from .config import get_config
from .errors import AudioError, ValidationError
from .logging import get_logger
from .schemas import AudioMeta, Transcript
from .validation import validate_output

logger = get_logger(__name__)

# Interactive browser imports (optional)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Available ASR models in order of sophistication (local/faster-whisper canonical names)
# Note: local models also support ".en" variants like "small.en", "medium.en".
ASR_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]

# Model alias maps per provider. Keep minimal and conservative; expand over time.
OPENAI_MODEL_ALIASES: Dict[str, str] = {
    # Friendly -> API model id
    "large-v3": "whisper-large-v3",
    "large-v3-turbo": "whisper-large-v3-turbo",
}

HF_MODEL_ALIASES: Dict[str, str] = {
    # Friendly -> HF repo id
    "distil-large-v3": "distil-whisper/distil-large-v3",
    # Allow mapping to official whisper repos as well
    "large-v3": "openai/whisper-large-v3",
}

LOCAL_MODEL_ALIASES: Dict[str, str] = {
    # Accept common variations and normalize to faster-whisper names
    "small.en": "small.en",
    "medium.en": "medium.en",
    "large": "large",
    "large-v2": "large-v2",
    "large-v3": "large-v3",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
    "medium": "medium",
}


def parse_model_and_provider(
    model_arg: str,
    provider_arg: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Parse model/provider from user input.

    Returns (provider, normalized_model_id).

    Rules:
    - Explicit provider via provider_arg takes precedence.
    - Prefix syntax "openai:large-v3-turbo" or "hf:distil-large-v3" selects provider.
    - Otherwise default to local provider.
    - Alias maps normalize to backend-specific ids.
    """
    if not model_arg:
        return ("local", "small")

    # Detect prefix in model string
    detected_provider = None
    if ":" in model_arg:
        prefix, remainder = model_arg.split(":", 1)
        if prefix in {"local", "openai", "hf"}:
            detected_provider = prefix
            model_key = remainder
        else:
            model_key = model_arg
    else:
        model_key = model_arg

    provider = provider_arg or detected_provider or "local"

    if provider == "openai":
        normalized = OPENAI_MODEL_ALIASES.get(model_key, model_key)
        return ("openai", normalized)
    if provider == "hf":
        normalized = HF_MODEL_ALIASES.get(model_key, model_key)
        return ("hf", normalized)

    # local
    normalized = LOCAL_MODEL_ALIASES.get(model_key, model_key)
    return ("local", normalized)


class LiveTimer:
    """Display a live timer that updates every second in the console."""

    def __init__(self, message: str = "Running"):
        self.message = message
        self.start_time = None
        self.stop_flag = threading.Event()
        self.thread = None

    def _format_time(self, seconds: int) -> str:
        """Format seconds as M:SS."""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"

    def _run(self):
        """Run the timer loop."""
        while not self.stop_flag.is_set():
            elapsed = int(time.time() - self.start_time)
            # Use \r to overwrite the line
            print(f"\r{self.message} ({self._format_time(elapsed)})", end="", flush=True)
            time.sleep(1)

    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        elapsed = time.time() - self.start_time
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=2)
        # Clear the line
        print("\r" + " " * 80 + "\r", end="", flush=True)
        return elapsed


def get_most_sophisticated_model(models: List[str]) -> str:
    """Return the most sophisticated model from a list."""
    for model in reversed(ASR_MODELS):
        if model in models:
            return model
    return models[0] if models else "base"


def scan_transcribable_episodes(base_dir: Path = Path.cwd()) -> List[Dict[str, Any]]:
    """Scan for audio-meta.json files (transcoded episodes ready for transcription)."""
    episodes = []

    # Recursively search for audio-meta.json files
    for meta_file in base_dir.rglob("audio-meta.json"):
        try:
            meta_data = json.loads(meta_file.read_text(encoding="utf-8"))

            # Check if audio file exists
            if "audio_path" not in meta_data:
                continue

            audio_path = Path(meta_data["audio_path"])
            if not audio_path.exists():
                # Try relative to meta file directory
                audio_path = meta_file.parent / audio_path.name
                if not audio_path.exists():
                    continue

            # Check for existing transcripts by reading JSON (provider-aware)
            transcripts = {}

            # Discover any transcript-*.json and read asr_model from content
            for transcript_path in meta_file.parent.glob("transcript-*.json"):
                try:
                    data = json.loads(transcript_path.read_text(encoding="utf-8"))
                    asr_model = data.get("asr_model") or data.get("model") or "unknown"
                    transcripts[asr_model] = transcript_path
                except Exception:
                    continue

            # Check for legacy transcript.json (unknown model)
            legacy_transcript = meta_file.parent / "transcript.json"
            if legacy_transcript.exists():
                # Try to determine model from content
                try:
                    transcript_data = json.loads(
                        legacy_transcript.read_text(encoding="utf-8")
                    )
                    model = transcript_data.get("asr_model", "unknown")
                    transcripts[model] = legacy_transcript
                except Exception:
                    transcripts["unknown"] = legacy_transcript

            episodes.append(
                {
                    "meta_file": meta_file,
                    "meta_data": meta_data,
                    "audio_path": audio_path,
                    "transcripts": transcripts,
                    "directory": meta_file.parent,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to parse {meta_file}: {e}")
            continue

    # Sort by directory path for consistent ordering
    episodes.sort(key=lambda x: str(x["directory"]))

    return episodes


def _truncate_text(text: str, max_length: int = 60) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


class TranscribeBrowser:
    """Interactive episode browser for transcription."""

    def __init__(self, episodes: List[Dict[str, Any]], episodes_per_page: int = 10):
        self.episodes = episodes
        self.episodes_per_page = episodes_per_page
        self.console = Console() if RICH_AVAILABLE else None
        self.current_page = 0
        self.total_pages = (
            (len(episodes) + episodes_per_page - 1) // episodes_per_page
            if episodes
            else 1
        )

    def display_page(self) -> None:
        """Display current page of episodes."""
        if not self.console:
            return

        start_idx = self.current_page * self.episodes_per_page
        end_idx = min(start_idx + self.episodes_per_page, len(self.episodes))
        page_episodes = self.episodes[start_idx:end_idx]

        # Create title
        title = f"🎙️ Episodes Available for Transcription (Page {self.current_page + 1}/{self.total_pages})"

        # Create table
        table = Table(show_header=True, header_style="bold magenta", title=title)
        table.add_column("#", style="cyan", width=3, justify="right")
        table.add_column("Status", style="yellow", width=25)
        table.add_column("Show", style="green", width=18)
        table.add_column("Date", style="blue", width=12)
        table.add_column("Title", style="white", width=45)

        # Add episodes to table
        for i, episode in enumerate(page_episodes):
            episode_num = start_idx + i + 1

            # Load episode metadata from episode-meta.json if it exists
            episode_meta_file = episode["directory"] / "episode-meta.json"
            if episode_meta_file.exists():
                try:
                    episode_meta = json.loads(
                        episode_meta_file.read_text(encoding="utf-8")
                    )
                except Exception:
                    episode_meta = {}
            else:
                episode_meta = {}

            # Status indicator
            if episode["transcripts"]:
                models_list = ", ".join(episode["transcripts"].keys())
                status = f"✓ {models_list}"
            else:
                status = "○ New"

            # Extract info from metadata
            show = _truncate_text(episode_meta.get("show", "Unknown"), 18)

            # Extract date
            date_str = episode_meta.get("episode_published", "")
            if date_str:
                try:
                    from dateutil import parser as dtparse

                    parsed = dtparse.parse(date_str)
                    date = parsed.strftime("%Y-%m-%d")
                except Exception:
                    date = date_str[:10] if len(date_str) >= 10 else date_str
            else:
                # Try to extract from directory name
                parts = str(episode["directory"]).split("/")
                date = parts[-1] if parts else "Unknown"

            title = _truncate_text(episode_meta.get("episode_title", "Unknown"), 45)

            table.add_row(str(episode_num), status, show, date, title)

        self.console.print(table)

        # Show navigation options
        options = []
        options.append(
            f"[cyan]1-{len(self.episodes)}[/cyan]: Select episode to transcribe"
        )

        if self.current_page < self.total_pages - 1:
            options.append("[yellow]N[/yellow]: Next page")

        if self.current_page > 0:
            options.append("[yellow]P[/yellow]: Previous page")

        options.append("[red]Q[/red]: Quit")

        options_text = " • ".join(options)

        panel = Panel(
            options_text, title="Options", border_style="blue", padding=(0, 1)
        )

        self.console.print(panel)

    def get_user_input(self) -> Optional[Dict[str, Any]]:
        """Get user input and return selected episode or None."""
        while True:
            try:
                user_input = input("\n👉 Your choice: ").strip().upper()

                if not user_input:
                    continue

                # Quit
                if user_input in ["Q", "QUIT", "EXIT"]:
                    if self.console:
                        self.console.print("👋 Goodbye!")
                    return None

                # Next page
                if user_input == "N" and self.current_page < self.total_pages - 1:
                    self.current_page += 1
                    return {}  # Empty dict signals page change

                # Previous page
                if user_input == "P" and self.current_page > 0:
                    self.current_page -= 1
                    return {}  # Empty dict signals page change

                # Episode selection
                try:
                    episode_num = int(user_input)
                    if 1 <= episode_num <= len(self.episodes):
                        selected_episode = self.episodes[episode_num - 1]
                        return selected_episode
                    else:
                        if self.console:
                            self.console.print(
                                f"❌ Invalid episode number. Please choose 1-{len(self.episodes)}"
                            )
                except ValueError:
                    pass

                # Invalid input
                if self.console:
                    self.console.print("❌ Invalid input. Please try again.")

            except (KeyboardInterrupt, EOFError):
                if self.console:
                    self.console.print("\n👋 Goodbye!")
                return None

    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop."""
        while True:
            if self.console:
                self.console.clear()
            self.display_page()

            result = self.get_user_input()

            # None means quit
            if result is None:
                return None

            # Empty dict means page change, continue loop
            if not result:
                continue

            # Non-empty dict means episode selected
            return result
def sanitize_for_filename(name: str) -> str:
    """Sanitize a model/provider name for safe filename usage."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)



def select_asr_model(
    episode: Dict[str, Any], console: Optional[Console]
) -> Optional[str]:
    """Prompt user to select ASR model with helpful context."""
    if not console:
        return None

    transcribed_models = list(episode["transcripts"].keys())

    # Determine recommended local model (most sophisticated not yet transcribed)
    recommended = None
    for model in reversed(ASR_MODELS):
        if model not in transcribed_models:
            recommended = model
            break

    if not recommended:
        recommended = get_most_sophisticated_model(ASR_MODELS)

    console.print("\n[bold cyan]Select ASR model:[/bold cyan]\n")

    # Create table showing models
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Number", style="cyan", justify="right", width=3)
    table.add_column("Model", style="white", width=12)
    table.add_column("Status", style="yellow", width=20)

    # Display local models plus common variants and provider examples
    display_models: List[str] = []
    display_models.extend(ASR_MODELS)
    for extra in ["small.en", "medium.en", "openai:large-v3-turbo", "hf:distil-large-v3"]:
        if extra not in display_models:
            display_models.append(extra)

    for idx, model in enumerate(display_models, 1):
        if model in transcribed_models:
            status = "✓ Already transcribed"
        elif model == recommended:
            status = "← Recommended"
        else:
            status = ""
        table.add_row(str(idx), model, status)

    console.print(table)

    if transcribed_models:
        console.print(
            f"\n[dim]Already transcribed with: {', '.join(transcribed_models)}[/dim]"
        )

    # Get user selection
    while True:
        try:
            choice = input(f"\n👉 Select model (1-{len(display_models)}) or Q to cancel: ").strip().upper()

            if choice in ["Q", "QUIT", "CANCEL"]:
                return None

            model_idx = int(choice)
            if 1 <= model_idx <= len(display_models):
                selected_model = display_models[model_idx - 1]

                # Check if same model already exists - ask for confirmation
                if selected_model in transcribed_models:
                    console.print(
                        f"\n[yellow]⚠ Episode already transcribed with model '{selected_model}'[/yellow]"
                    )
                    confirm = (
                        input("Re-transcribe with same model? (yes/no): ")
                        .strip()
                        .lower()
                    )
                    if confirm not in ["yes", "y"]:
                        console.print(
                            "[dim]Selection cancelled. Choose a different model.[/dim]"
                        )
                        continue

                return selected_model
            else:
                console.print(
                        f"[red]❌ Invalid choice. Please select 1-{len(display_models)}[/red]"
                )

        except ValueError:
            console.print("[red]❌ Invalid input. Please enter a number.[/red]")
        except (KeyboardInterrupt, EOFError):
            return None


@click.command()
@click.option(
    "--model",
    default=lambda: get_config().default_asr_model,
    help=(
        "ASR model (e.g., tiny, base, small, medium, large, large-v2, large-v3, "
        "small.en, medium.en, or prefixed: openai:large-v3-turbo, hf:distil-large-v3)"
    ),
)
@click.option(
    "--asr-provider",
    type=click.Choice(["auto", "local", "openai", "hf"]),
    default="auto",
    help="ASR provider (auto-detect by model prefix/alias if 'auto')",
)
@click.option(
    "--preset",
    type=click.Choice(["balanced", "precision", "recall"]),
    default=None,
    help="High-level decoding preset (defaults to balanced behavior)",
)
@click.option(
    "--expert",
    is_flag=True,
    help="Show and enable expert decoder flags (for advanced users)",
)
@click.option(
    "--vad-filter/--no-vad",
    default=None,
    help="Enable/disable VAD filtering (overrides preset)",
)
@click.option(
    "--condition-on-previous-text/--no-condition-on-previous-text",
    default=None,
    help="Condition decoding on previous text (overrides preset; local only)",
)
@click.option(
    "--decode-option",
    multiple=True,
    help="Advanced k=v options to pass to decoder (local provider only)",
)
@click.option(
    "--compute",
    default=lambda: get_config().default_compute,
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read AudioMeta JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save Transcript JSON to file (also prints to stdout)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive browser to select episodes for transcription",
)
@click.option(
    "--scan-dir",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Directory to scan for episodes (default: current directory)",
)
@validate_output(Transcript)
def main(
    model,
    compute,
    input,
    output,
    interactive,
    scan_dir,
    asr_provider,
    preset,
    expert,
    vad_filter,
    condition_on_previous_text,
    decode_option,
):
    """
    Read AudioMeta JSON on stdin -> run faster-whisper -> print Transcript JSON to stdout.

    With --interactive, browse episodes and select one to transcribe.
    """
    # Handle interactive mode
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit(
                "Interactive mode requires rich library. Install with: pip install rich"
            )

        console = Console()

        # Scan for episodes
        logger.info(f"Scanning for episodes in: {scan_dir}")
        episodes = scan_transcribable_episodes(Path(scan_dir))

        if not episodes:
            logger.error(f"No transcoded episodes found in {scan_dir}")
            raise SystemExit("No episodes with audio-meta.json found")

        logger.info(f"Found {len(episodes)} episodes")

        # Browse and select episode
        browser = TranscribeBrowser(episodes, episodes_per_page=10)
        selected = browser.browse()

        if not selected:
            logger.info("User cancelled episode selection")
            sys.exit(0)

        # Select ASR model
        selected_model = select_asr_model(selected, console)

        if not selected_model:
            logger.info("User cancelled model selection")
            sys.exit(0)

        # Override model parameter with user selection
        model = selected_model

        # Use selected episode's audio path
        audio = selected["audio_path"]
        episode_dir = selected["directory"]

        # Force output to transcript-{safe_model}.json in episode directory
        safe_model = sanitize_for_filename(model)
        output = episode_dir / f"transcript-{safe_model}.json"

        # Load audio metadata
        try:
            meta = AudioMeta.parse_obj(selected["meta_data"])
        except Exception as e:
            raise ValidationError(f"Invalid AudioMeta input: {e}") from e

    else:
        # Non-interactive mode
        logger.info("Starting transcription", model=model, compute=compute)

        # Read input
        if input:
            raw_data = json.loads(input.read_text())
            logger.debug("Reading input from file", file=str(input))
        else:
            raw_data = read_stdin_json()
            logger.debug("Reading input from stdin")

        if not raw_data or "audio_path" not in raw_data:
            raise ValidationError(
                "input must contain AudioMeta JSON with 'audio_path' field"
            )

        # Validate input data
        try:
            meta = AudioMeta.parse_obj(raw_data)
            audio = Path(meta.audio_path)
            logger.debug("Input validation passed", audio_path=str(audio))
        except Exception as e:
            raise ValidationError(f"Invalid AudioMeta input: {e}") from e

    # Determine provider and normalized model id
    provider_choice = None if asr_provider == "auto" else asr_provider
    provider, normalized_model = parse_model_and_provider(model, provider_choice)

    logger.info("Selected ASR backend", provider=provider, model=normalized_model)

    # Dispatch to provider-specific transcription path
    segments = None
    detected_language = "en"
    full_text_lines: List[str] = []

    if provider == "local":
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise AudioError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )

        logger.info("Initializing local Whisper model", model=normalized_model, compute=compute)
        try:
            asr = WhisperModel(normalized_model, device="cpu", compute_type=compute)
        except Exception as e:
            raise AudioError(f"Failed to initialize Whisper model: {e}") from e

        logger.info("Starting transcription", audio_file=str(audio))
        
        # Start live timer in interactive mode
        timer = None
        if interactive and RICH_AVAILABLE:
            console = Console()
            timer = LiveTimer("Transcribing")
            timer.start()
        
        # Determine decode parameters (preset -> defaults -> explicit overrides)
        # Defaults emulate current behavior
        use_vad = True if vad_filter is None else bool(vad_filter)
        use_condition = None if condition_on_previous_text is None else bool(condition_on_previous_text)
        if preset:
            if preset == "balanced":
                use_vad = True if vad_filter is None else use_vad
                use_condition = True if condition_on_previous_text is None else use_condition
            elif preset == "precision":
                use_vad = True if vad_filter is None else use_vad
                use_condition = True if condition_on_previous_text is None else use_condition
            elif preset == "recall":
                use_vad = False if vad_filter is None else use_vad
                use_condition = False if condition_on_previous_text is None else use_condition

        # Parse additional decode options
        extra_kwargs: Dict[str, Any] = {}
        for opt in decode_option or ():
            if "=" in opt:
                k, v = opt.split("=", 1)
                extra_kwargs[k.strip()] = v.strip()

        try:
            transcribe_kwargs: Dict[str, Any] = {
                "vad_filter": use_vad,
                "vad_parameters": {"min_silence_duration_ms": 500},
            }
            if use_condition is not None:
                transcribe_kwargs["condition_on_previous_text"] = use_condition
            # Add expert options if provided
            if expert and extra_kwargs:
                transcribe_kwargs.update(extra_kwargs)

            seg_iter, info = asr.transcribe(str(audio), **transcribe_kwargs)
        except Exception as e:
            if timer:
                timer.stop()
            raise AudioError(f"Transcription failed: {e}") from e

        segs = []
        text_lines = []
        for s in seg_iter:
            segs.append({"start": s.start, "end": s.end, "text": s.text})
            text_lines.append(s.text)

        detected_language = getattr(info, "language", "en")
        total_segments = len(segs)

        # Stop timer and show completion message in interactive mode
        if timer:
            elapsed = timer.stop()
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            console.print(f"[green]✓ Transcribe completed in {minutes}:{seconds:02d}[/green]")

        logger.info(
            "Transcription completed",
            segments_count=total_segments,
            language=detected_language,
            total_duration=segs[-1]["end"] if segs else 0,
        )

        segments = segs
        full_text_lines = text_lines

    elif provider == "openai":
        # OpenAI Whisper via API
        logger.info("Using OpenAI transcription API", model=normalized_model)
        try:
            # Prefer new SDK if available
            try:
                from openai import OpenAI  # type: ignore
                client = OpenAI()
                use_new_sdk = True
            except Exception:
                import openai  # type: ignore
                use_new_sdk = False

            audio_path = str(audio)
            if use_new_sdk:
                with open(audio_path, "rb") as f:
                    # Attempt verbose JSON for segments
                    resp = client.audio.transcriptions.create(
                        model=normalized_model,
                        file=f,
                        response_format="verbose_json",
                    )
                # SDK returns pydantic-like objects; try to access fields
                text = getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else None)
                segs_raw = getattr(resp, "segments", None) or (resp.get("segments") if isinstance(resp, dict) else None)
            else:
                # Legacy SDK
                with open(audio_path, "rb") as f:
                    resp = openai.Audio.transcriptions.create(
                        model=normalized_model,
                        file=f,
                        response_format="verbose_json",
                    )
                text = resp.get("text")
                segs_raw = resp.get("segments")

            segs: List[Dict[str, Any]] = []
            if segs_raw:
                for s in segs_raw:
                    start = s.get("start")
                    end = s.get("end")
                    txt = s.get("text", "")
                    if start is None or end is None:
                        # Some APIs use "timestamp" as [start, end]
                        ts = s.get("timestamp")
                        if isinstance(ts, (list, tuple)) and len(ts) == 2:
                            start, end = ts[0], ts[1]
                    if start is None:
                        start = 0.0
                    if end is None:
                        end = 0.0
                    segs.append({"start": float(start), "end": float(end), "text": txt})
            else:
                # Fallback: single segment with full text
                txt = text or ""
                segs = [{"start": 0.0, "end": 0.0, "text": txt}]

            segments = segs
            full_text_lines = [s["text"] for s in segs]
            detected_language = "en"
        except Exception as e:
            raise AudioError(f"OpenAI transcription failed: {e}") from e

    elif provider == "hf":
        # Hugging Face transformers pipeline
        logger.info("Using Hugging Face ASR pipeline", model=normalized_model)
        try:
            from transformers import pipeline  # type: ignore
        except Exception as e:
            raise AudioError(
                "transformers not installed. Install with: pip install transformers torchaudio"
            ) from e

        try:
            asr = pipeline(
                "automatic-speech-recognition",
                model=normalized_model,
                return_timestamps="chunk",
            )
            result = asr(str(audio), chunk_length_s=30, stride_length_s=5)
            segs: List[Dict[str, Any]] = []
            chunks = result.get("chunks") if isinstance(result, dict) else None
            if chunks:
                for c in chunks:
                    ts = c.get("timestamp") or c.get("timestamps")
                    if isinstance(ts, (list, tuple)) and len(ts) == 2:
                        start, end = ts
                    else:
                        start, end = 0.0, 0.0
                    segs.append({"start": float(start), "end": float(end), "text": c.get("text", "")})
                segments = segs
                full_text_lines = [c.get("text", "") for c in chunks]
            else:
                # Fallback: one segment
                text_val = result.get("text") if isinstance(result, dict) else ""
                segments = [{"start": 0.0, "end": 0.0, "text": text_val}]
                full_text_lines = [text_val]
            detected_language = "en"
        except Exception as e:
            raise AudioError(f"Hugging Face transcription failed: {e}") from e
    else:
        raise AudioError(f"Unknown ASR provider: {provider}")
    
    out = {
        "audio_path": str(audio.resolve()),  # Always use absolute path
        "language": detected_language,
        "asr_model": model,
        "asr_provider": provider,
        "preset": preset,
        "decoder_options": {"vad_filter": use_vad} if provider == "local" else None,
        "segments": segments,
        "text": "\n".join(full_text_lines).strip(),
    }

    # Handle output based on interactive mode
    if interactive:
        # In interactive mode, save to file (already set to transcript-{model}.json)
        output.write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Transcript saved to: {output}")
    else:
        # Non-interactive mode: use model-specific filename if model specified and no explicit output
        if model and not output:
            # Try to determine episode directory from audio path
            audio_dir = audio.parent
            safe_model = sanitize_for_filename(model)
            output = audio_dir / f"transcript-{safe_model}.json"
            output.write_text(
                json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.debug("Transcript saved to file", file=str(output))
        elif output:
            # Explicit output file specified
            output.write_text(json.dumps(out, indent=2))
            logger.debug("Transcript saved to file", file=str(output))

        # Always print to stdout in non-interactive mode
        print_json(out)

    # Return for validation decorator
    return out


if __name__ == "__main__":
    main()
