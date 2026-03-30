"""Main run command - interactive wizard for full pipeline.

Enhanced flow: fetch → cloud prompt → transcribe → diarize → cleanup →
listen-through → template → oracle → moments → questions → analyze → export → notion
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from rich.console import Console

from podx.domain.exit_codes import ExitCode

console = Console()


# ---------------------------------------------------------------------------
# Pipeline step functions (fetch, transcribe, diarize, cleanup, export)
# ---------------------------------------------------------------------------


def _run_fetch_step() -> Optional[Path]:
    """Run fetch step interactively. Returns episode directory or None."""
    from podx.cli.fetch import PodcastFetcher, _run_interactive

    console.print("\n[bold cyan]── Fetch ──────────────────────────────────────────[/bold cyan]")

    fetcher = PodcastFetcher()
    result = _run_interactive(fetcher)

    if result is None:
        return None

    return Path(result["directory"])


def _run_transcribe_step(episode_dir: Path, model: Optional[str] = None) -> bool:
    """Run transcribe step. Returns True on success."""
    from podx.cli.transcribe import _find_audio_file
    from podx.config import get_config
    from podx.core.transcribe import TranscriptionEngine, TranscriptionError
    from podx.ui import LiveTimer, LiveTimerProgressReporter

    console.print("\n[bold cyan]── Transcribe ─────────────────────────────────────[/bold cyan]")

    transcript_path = episode_dir / "transcript.json"
    if transcript_path.exists():
        console.print("[dim]Transcript already exists, skipping...[/dim]")
        return True

    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        console.print("[red]Error:[/red] No audio file found")
        return False

    if model is None:
        model = get_config().default_asr_model
    console.print(f"[dim]Transcribing with {model}...[/dim]")

    timer = LiveTimer("Transcribing")
    progress = LiveTimerProgressReporter(timer)
    timer.start()

    try:
        engine = TranscriptionEngine(model=model, progress=progress)
        result = engine.transcribe(audio_file)
    except TranscriptionError as e:
        timer.stop()
        console.print(f"[red]Error:[/red] {e}")
        return False

    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    result["audio_path"] = str(audio_file)
    result["diarized"] = False
    result["cleaned"] = False
    result["restored"] = False
    transcript_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[green]✓ Transcription complete ({minutes}:{seconds:02d})[/green]")
    return True


def _run_diarize_step(episode_dir: Path, use_cloud: bool = False) -> bool:
    """Run diarize step. Returns True on success."""
    import logging
    from contextlib import redirect_stderr, redirect_stdout

    from podx.cli.diarize import _find_audio_file
    from podx.cloud import CloudConfig
    from podx.cloud.exceptions import CloudError
    from podx.core.diarization import DiarizationProviderError, get_diarization_provider
    from podx.core.diarize import DiarizationEngine, DiarizationError
    from podx.ui import LiveTimer

    console.print("\n[bold cyan]── Diarize ────────────────────────────────────────[/bold cyan]")

    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print("[red]Error:[/red] No transcript found")
        return False

    transcript = json.loads(transcript_path.read_text())

    if transcript.get("diarized"):
        console.print("[dim]Already diarized, skipping...[/dim]")
        return True

    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        console.print("[red]Error:[/red] No audio file found")
        return False

    language = transcript.get("language", "en")

    # Audio preprocessing: create denoised audio for diarization
    diarize_audio = audio_file
    diarize_audio_path = None
    try:
        from podx.core.transcode import create_diarize_audio

        diarize_audio_path = episode_dir / "audio_diarize.wav"
        create_diarize_audio(audio_file, diarize_audio_path)
        diarize_audio = diarize_audio_path
    except Exception:
        diarize_audio_path = None

    # Check if cloud diarization is configured
    cloud_diarize_available = False
    if use_cloud:
        try:
            cloud_config = CloudConfig.from_podx_config()
            cloud_diarize_available = cloud_config.is_diarization_configured
        except Exception:
            pass
        if not cloud_diarize_available:
            console.print("[dim]Cloud diarization not configured, using local...[/dim]")

    if use_cloud and cloud_diarize_available:
        console.print("[dim]Diarizing on cloud GPU...[/dim]")
        timer = LiveTimer("Diarizing")
        timer.start()

        def cloud_progress(msg: str) -> None:
            if "..." in msg:
                activity = msg.split("...")[0].strip() + "..."
                timer.update_message(activity)
                timer.update_substatus(msg)
            else:
                timer.update_message(msg)
                timer.update_substatus(None)

        try:
            provider = get_diarization_provider(
                "runpod", language=language, progress_callback=cloud_progress
            )
            result = provider.diarize(diarize_audio, transcript["segments"])
            segments = result.segments
            speakers_count = result.speakers_count
        except (DiarizationProviderError, CloudError) as e:
            timer.stop()
            if diarize_audio_path and diarize_audio_path.exists():
                diarize_audio_path.unlink()
            console.print(f"[red]Error:[/red] {e}")
            return False
        elapsed = timer.stop()
    else:
        console.print("[dim]Adding speaker labels...[/dim]")
        timer = LiveTimer("Diarizing")
        timer.start()

        noisy_loggers = [
            "speechbrain.utils.parameter_transfer",
            "speechbrain.utils.checkpoints",
            "pyannote.audio",
        ]
        saved_levels = {}
        for name in noisy_loggers:
            lg = logging.getLogger(name)
            saved_levels[name] = lg.level
            lg.setLevel(logging.WARNING)

        try:
            with (
                redirect_stdout(open(os.devnull, "w")),
                redirect_stderr(open(os.devnull, "w")),
            ):
                engine = DiarizationEngine(
                    language=language, hf_token=os.getenv("HUGGINGFACE_TOKEN")
                )
                result = engine.diarize(diarize_audio, transcript["segments"])
                segments = result["segments"]
                speakers = set(s.get("speaker") for s in segments if s.get("speaker"))
                speakers_count = len(speakers)
        except DiarizationError as e:
            timer.stop()
            for name, level in saved_levels.items():
                logging.getLogger(name).setLevel(level)
            if diarize_audio_path and diarize_audio_path.exists():
                diarize_audio_path.unlink()
            console.print(f"[red]Error:[/red] {e}")
            return False

        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)
        elapsed = timer.stop()

    if diarize_audio_path and diarize_audio_path.exists():
        diarize_audio_path.unlink()

    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    transcript["segments"] = segments
    transcript["diarized"] = True
    transcript_path.write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    console.print(f"[green]✓ Diarization complete ({minutes}:{seconds:02d})[/green]")
    console.print(f"  Speakers found: {speakers_count}")
    return True


def _run_cleanup_step(episode_dir: Path) -> bool:
    """Run cleanup step. Returns True on success."""
    from podx.core.preprocess import PreprocessError, TranscriptPreprocessor
    from podx.core.speakers import load_speaker_map, save_speaker_map
    from podx.ui import (
        LiveTimer,
        apply_speaker_names,
        has_generic_speaker_ids,
        identify_speakers_interactive,
        resolve_audio_path,
    )

    console.print("\n[bold cyan]── Cleanup ────────────────────────────────────────[/bold cyan]")

    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print("[red]Error:[/red] No transcript found")
        return False

    transcript = json.loads(transcript_path.read_text())

    if transcript.get("cleaned"):
        console.print("[dim]Already cleaned, skipping...[/dim]")
        return True

    # Speaker identification
    if transcript.get("diarized") and has_generic_speaker_ids(transcript["segments"]):
        # Check for saved speaker map first
        existing_map = load_speaker_map(episode_dir)
        if existing_map:
            transcript["segments"] = apply_speaker_names(transcript["segments"], existing_map)
            console.print(
                f"[green]✓ Applied saved speaker map ({len(existing_map)} speakers)[/green]"
            )
        else:
            try:
                choice = (
                    input("Identify speakers? (recommended for diarized transcripts) [Y/n]: ")
                    .strip()
                    .lower()
                )
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Cancelled[/dim]")
                raise SystemExit(0)

            if choice not in ("n", "no"):
                audio_path = resolve_audio_path(episode_dir, transcript.get("audio_path"))
                try:
                    speaker_map = identify_speakers_interactive(
                        transcript["segments"], audio_path=audio_path
                    )
                    if speaker_map:
                        transcript["segments"] = apply_speaker_names(
                            transcript["segments"], speaker_map
                        )
                        save_speaker_map(episode_dir, speaker_map)
                        transcript_path.write_text(
                            json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8"
                        )
                        console.print(f"[green]✓ Identified {len(speaker_map)} speaker(s)[/green]")
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[dim]Speaker identification cancelled[/dim]")

    # Run text cleanup
    do_restore = bool(os.getenv("OPENAI_API_KEY"))
    if do_restore:
        console.print("[dim]Cleaning up with LLM restore...[/dim]")
    else:
        console.print("[dim]Cleaning up (no API key, skipping restore)...[/dim]")

    timer = LiveTimer("Cleaning up")
    timer.start()

    try:
        preprocessor = TranscriptPreprocessor(
            merge=True,
            normalize=True,
            restore=do_restore,
            max_gap=1.0,
            max_len=800,
            restore_model="gpt-4o-mini",
        )
        result = preprocessor.preprocess(transcript)
    except PreprocessError as e:
        timer.stop()
        console.print(f"[red]Error:[/red] {e}")
        return False

    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    for key in [
        "audio_path",
        "language",
        "asr_model",
        "asr_provider",
        "decoder_options",
        "diarized",
    ]:
        if key in transcript:
            result[key] = transcript[key]
    result["cleaned"] = True
    result["restored"] = do_restore

    transcript_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    original_count = len(transcript["segments"])
    merged_count = len(result["segments"])
    console.print(f"[green]✓ Cleanup complete ({minutes}:{seconds:02d})[/green]")
    console.print(f"  Segments: {original_count} → {merged_count}")
    return True


def _run_export_step(episode_dir: Path) -> bool:
    """Run export step. Returns True on success."""
    console.print("\n[bold cyan]── Export ─────────────────────────────────────────[/bold cyan]")

    transcript_path = episode_dir / "transcript.json"
    if transcript_path.exists():
        transcript = json.loads(transcript_path.read_text())
        segments = transcript.get("segments", [])
        lines = ["# Transcript\n"]
        for seg in segments:
            speaker = seg.get("speaker", "")
            text = seg.get("text", "")
            if speaker:
                lines.append(f"**{speaker}:** {text}\n")
            else:
                lines.append(f"{text}\n")
        md_path = episode_dir / "transcript.md"
        md_path.write_text("\n".join(lines), encoding="utf-8")
        console.print("  Exported: transcript.md")

    # Export all analysis files to markdown
    for analysis_path in sorted(episode_dir.glob("analysis*.json")):
        if analysis_path.suffix != ".json":
            continue
        try:
            analysis = json.loads(analysis_path.read_text())
            md = analysis.get("markdown", "")
            if md:
                md_name = analysis_path.stem + ".md"
                md_path = episode_dir / md_name
                md_path.write_text(md, encoding="utf-8")
                console.print(f"  Exported: {md_name}")
        except Exception:
            pass

    return True


# ---------------------------------------------------------------------------
# Interactive prompt functions
# ---------------------------------------------------------------------------


def _prompt_cloud() -> bool:
    """Prompt for cloud GPU usage. Returns False if not configured."""
    try:
        from podx.cloud import CloudConfig

        cloud_config = CloudConfig.from_podx_config()
        if not cloud_config.is_configured:
            return False
    except Exception:
        return False

    try:
        choice = input("Use cloud GPU? [Y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise SystemExit(0)

    return choice not in ("n", "no")


def _prompt_listen_through(cli_value: Optional[str]) -> Optional[str]:
    """Prompt for how far the user listened. Returns timecode or None for full."""
    if cli_value is not None:
        return cli_value

    console.print("\n[bold cyan]── Analysis Setup ─────────────────────────────────[/bold cyan]")
    try:
        value = input("How far did you listen? (Enter for full, or timecode like 45:00): ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise SystemExit(0)

    return value if value else None


def _prompt_template(cli_value: Optional[str]) -> str:
    """Prompt for analysis template selection. Type ? to list templates."""
    if cli_value is not None:
        return cli_value

    from podx.cli.analyze import DEFAULT_TEMPLATE
    from podx.templates.manager import TemplateManager

    manager = TemplateManager()
    valid_names = set(manager.list_templates())

    while True:
        try:
            value = input(f"Template (default: {DEFAULT_TEMPLATE}, ? to list): ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled[/dim]")
            raise SystemExit(0)

        if not value:
            return DEFAULT_TEMPLATE

        if value == "?":
            console.print()
            for name in sorted(valid_names):
                tmpl = manager.load(name)
                desc = tmpl.description
                if "Format:" in desc:
                    desc = desc.split("Example podcasts:")[0].replace("Format:", "").strip()
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                console.print(f"  [cyan]{name:<24}[/cyan] {desc}")
            console.print()
            continue

        if value in valid_names:
            return value

        console.print(f"[red]Unknown template '{value}'. Type ? to see available templates.[/red]")


def _prompt_oracle(no_oracle: bool) -> bool:
    """Prompt for knowledge-oracle. Default yes."""
    if no_oracle:
        return False

    try:
        choice = input("Run knowledge-oracle? [Y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise SystemExit(0)

    return choice not in ("n", "no")


def _prompt_moments(cli_value: Optional[str]) -> List[Dict[str, Any]]:
    """Prompt for flagged moments. Returns list of {time, note?} dicts.

    Parses each line: if ' - ' present, split into time + note.
    Otherwise just the timecode — AI determines significance.
    """
    if cli_value is not None:
        return _parse_moments_string(cli_value)

    try:
        first = input("Flag any moments? (timecodes, one per line, Enter to skip): ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise SystemExit(0)

    if not first:
        return []

    lines = [first]
    console.print("[dim]  (one per line, Enter to finish)[/dim]")
    while True:
        try:
            line = input("  > ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not line:
            break
        lines.append(line)

    return _parse_moments_lines(lines)


def _prompt_questions(cli_value: Optional[str]) -> List[str]:
    """Prompt for follow-up questions. Returns list of question strings."""
    if cli_value is not None:
        return [cli_value] if cli_value else []

    try:
        first = input("Questions for the analysis? (one per line, Enter to skip): ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise SystemExit(0)

    if not first:
        return []

    questions = [first]
    console.print("[dim]  (one per line, Enter to finish)[/dim]")
    while True:
        try:
            line = input("  > ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not line:
            break
        questions.append(line)

    return questions


def _parse_moments_string(s: str) -> List[Dict[str, Any]]:
    """Parse comma-separated moments from CLI flag."""
    moments = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if " - " in part:
            time_str, note = part.split(" - ", 1)
            moments.append({"time": time_str.strip(), "note": note.strip()})
        else:
            moments.append({"time": part})
    return moments


def _parse_moments_lines(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse multi-line moments input."""
    moments = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if " - " in line:
            time_str, note = line.split(" - ", 1)
            moments.append({"time": time_str.strip(), "note": note.strip()})
        else:
            moments.append({"time": line})
    return moments


def _parse_timecode_to_seconds(tc: str) -> float:
    """Parse a timecode string like '45:00' or '1:02:33' to seconds."""
    parts = tc.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        else:
            return float(parts[0])
    except (ValueError, IndexError):
        return 0.0


def _show_prior_state(moments: List[Dict], questions: List[str], through: Optional[str]) -> None:
    """Display previously saved moments/questions when resuming."""
    console.print("\n[bold]Previous session:[/bold]")
    if through:
        console.print(f"  Analyzed through: {through}")
    if moments:
        console.print("  Flagged moments:")
        for m in moments:
            note = f" — {m['note']}" if m.get("note") else ""
            console.print(f"    [{m['time']}]{note}")
    if questions:
        console.print("  Questions:")
        for q in questions:
            console.print(f"    {q}")
    console.print()


def _load_partial_state(episode_dir: Path) -> Dict[str, Any]:
    """Load state from existing analysis for resume."""
    for path in sorted(episode_dir.glob("analysis*.json")):
        try:
            data = json.loads(path.read_text())
            return {
                "flagged_moments": data.get("flagged_moments", []),
                "questions": data.get("questions", []),
                "analyzed_through": data.get("analyzed_through"),
            }
        except Exception:
            continue
    return {}


# ---------------------------------------------------------------------------
# Analysis step (refactored — no internal prompts)
# ---------------------------------------------------------------------------


def _run_analyze_step(
    episode_dir: Path,
    template_name: str,
    model: Optional[str] = None,
    moments: Optional[List[Dict]] = None,
    questions: Optional[List[str]] = None,
    analyzed_through: Optional[str] = None,
    label: Optional[str] = None,
) -> bool:
    """Run a single analysis pass. Returns True on success.

    Works for both format templates and knowledge-oracle.
    """
    from podx.cli.analyze import DEFAULT_MAP_INSTRUCTIONS, DEFAULT_MODEL, analysis_output_path
    from podx.core.analyze import AnalyzeEngine, AnalyzeError
    from podx.core.backfill import compute_template_hash
    from podx.prompt_templates import ENHANCED_JSON_SCHEMA
    from podx.templates.manager import TemplateError, TemplateManager
    from podx.ui import LiveTimer

    if model is None:
        model = DEFAULT_MODEL

    display_label = label or template_name
    console.print(f"[dim]Running {display_label} analysis with {model}...[/dim]")

    # Load transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print("[red]Error:[/red] No transcript found")
        return False

    transcript = json.loads(transcript_path.read_text())
    segments = transcript.get("segments", [])

    # Filter segments if partial analysis
    if analyzed_through:
        through_seconds = _parse_timecode_to_seconds(analyzed_through)
        segments = [s for s in segments if s.get("end", 0) <= through_seconds]
        console.print(
            f"[dim]  Analyzing through {analyzed_through} ({len(segments)} segments)[/dim]"
        )

    if not segments:
        console.print("[yellow]No segments to analyze[/yellow]")
        return False

    # Check if analysis exists and is current (template hash)
    analysis_path = analysis_output_path(episode_dir, template_name, model)
    try:
        manager = TemplateManager()
        tmpl = manager.load(template_name)
    except TemplateError as e:
        console.print(f"[red]Error:[/red] {e}")
        return False

    if analysis_path.exists():
        try:
            existing = json.loads(analysis_path.read_text())
            stored_hash = existing.get("template_hash")
            current_hash = compute_template_hash(tmpl)
            if stored_hash == current_hash and not analyzed_through:
                console.print(f"[dim]{display_label} analysis up to date, skipping...[/dim]")
                return True
        except Exception:
            pass

    timer = LiveTimer(f"Analyzing ({display_label})")
    timer.start()

    try:
        provider_name = "openai"
        model_name = model
        if ":" in model:
            provider_name, model_name = model.split(":", 1)

        engine = AnalyzeEngine(model=model_name, provider_name=provider_name)

        # Build transcript text from (possibly filtered) segments
        transcript_text = "\n".join(
            (
                f"[{s.get('speaker', 'SPEAKER')}] {s.get('text', '')}"
                if s.get("speaker")
                else s.get("text", "")
            )
            for s in segments
        )

        speaker_set = set(s.get("speaker") for s in segments if s.get("speaker"))
        speaker_count = len(speaker_set) if speaker_set else 1
        speakers_str = ", ".join(sorted(speaker_set)) if speaker_set else "Unknown"

        episode_meta = {}
        meta_path = episode_dir / "episode-meta.json"
        if meta_path.exists():
            try:
                episode_meta = json.loads(meta_path.read_text())
            except Exception:
                pass

        context = {
            "transcript": transcript_text,
            "speaker_count": speaker_count,
            "speakers": speakers_str,
            "duration": int(segments[-1].get("end", 0) // 60) if segments else 0,
            "title": episode_meta.get("episode_title", episode_dir.name),
            "show": episode_meta.get("show", "Unknown"),
            "date": episode_meta.get("episode_published", "Unknown"),
            "description": episode_meta.get("episode_description", ""),
        }

        system_prompt, user_prompt = tmpl.render(context)

        # Use a temporary transcript dict with filtered segments
        filtered_transcript = dict(transcript)
        filtered_transcript["segments"] = segments

        md, json_data = engine.analyze(
            transcript=filtered_transcript,
            system_prompt=system_prompt,
            map_instructions=(tmpl.map_instructions or DEFAULT_MAP_INSTRUCTIONS),
            reduce_instructions=user_prompt,
            want_json=True,
            json_schema=(tmpl.json_schema or ENHANCED_JSON_SCHEMA),
            moments=moments,
            questions=questions,
        )
    except (AnalyzeError, TemplateError) as e:
        timer.stop()
        console.print(f"[red]Error:[/red] {e}")
        return False

    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    md = f"> **Template:** {template_name} | **Model:** {model}\n\n{md}"

    result: Dict[str, Any] = {
        "markdown": md,
        "template": template_name,
        "template_hash": compute_template_hash(tmpl),
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if analyzed_through:
        result["analyzed_through"] = analyzed_through
    if moments:
        result["flagged_moments"] = moments
    if questions:
        result["questions"] = questions
    if json_data:
        result["results"] = json_data

    analysis_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[green]✓ {display_label} analysis complete ({minutes}:{seconds:02d})[/green]")
    return True


# ---------------------------------------------------------------------------
# Notion publish step
# ---------------------------------------------------------------------------


def _run_notion_step(
    episode_dir: Path,
    format_template: str,
    model: Optional[str] = None,
) -> bool:
    """Publish to Notion. Prompts if NOTION_TOKEN is set."""
    from podx.cli.analyze import DEFAULT_MODEL, analysis_output_path
    from podx.core.backfill import (
        NOTION_DB_ID,
        build_notion_page_blocks,
        build_notion_properties,
        parse_classification_json,
    )

    console.print("\n[bold cyan]── Publish ────────────────────────────────────────[/bold cyan]")

    token = os.getenv("NOTION_TOKEN")
    if not token:
        console.print("[dim]NOTION_TOKEN not set, skipping Notion publish[/dim]")
        return True

    try:
        choice = input("Publish to Notion? [Y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise SystemExit(0)

    if choice in ("n", "no"):
        console.print("[dim]Skipped[/dim]")
        return True

    if model is None:
        model = DEFAULT_MODEL

    # Load analyses
    format_path = analysis_output_path(episode_dir, format_template, model)
    oracle_path = analysis_output_path(episode_dir, "knowledge-oracle", model)

    format_md = None
    oracle_md = None

    if format_path.exists():
        format_md = json.loads(format_path.read_text()).get("markdown", "")
    if oracle_path.exists():
        oracle_md = json.loads(oracle_path.read_text()).get("markdown", "")

    if not format_md and not oracle_md:
        console.print("[dim]No analysis to publish[/dim]")
        return True

    # Load metadata and transcript
    episode_meta = {}
    meta_path = episode_dir / "episode-meta.json"
    if meta_path.exists():
        episode_meta = json.loads(meta_path.read_text())

    transcript = None
    transcript_path = episode_dir / "transcript.json"
    if transcript_path.exists():
        transcript = json.loads(transcript_path.read_text())

    # Parse classification
    classification = parse_classification_json(oracle_md) if oracle_md else None

    templates_run = []
    if format_md:
        templates_run.append(format_template)
    if oracle_md:
        templates_run.append("knowledge-oracle")

    props_extra = build_notion_properties(
        classification=classification,
        templates_run=templates_run,
        model=model,
        asr_model=transcript.get("asr_model") if transcript else None,
        has_transcript=bool(transcript and transcript.get("segments")),
        source_url=episode_meta.get("feed"),
    )

    video_url = episode_meta.get("video_url")

    # Build blocks — separate analysis from toggles (avoid block limit)
    all_blocks = build_notion_page_blocks(format_md, oracle_md, transcript, video_url)
    analysis_blocks = [b for b in all_blocks if b.get("type") != "toggle"]
    toggle_blocks = [b for b in all_blocks if b.get("type") == "toggle"]

    # Parse date
    date_iso = None
    date_str = episode_meta.get("episode_published", "")
    if date_str:
        try:
            from dateutil import parser as dtparse

            parsed = dtparse.parse(date_str)
            date_iso = parsed.strftime("%Y-%m-%d")
        except Exception:
            if len(date_str) >= 10:
                date_iso = date_str[:10]

    try:
        from notion_client import Client

        from podx.cli.notion_services.page_operations import upsert_page

        client = Client(auth=token)
        page_id = upsert_page(
            client=client,
            db_id=NOTION_DB_ID,
            podcast_name=episode_meta.get("show", "Unknown"),
            episode_title=episode_meta.get("episode_title", episode_dir.name),
            date_iso=date_iso,
            podcast_prop="Podcast",
            episode_prop="Episode",
            date_prop="Date",
            props_extra=props_extra,
            blocks=analysis_blocks,
            replace_content=True,
        )

        # Append toggles individually
        for toggle in toggle_blocks:
            try:
                client.blocks.children.append(block_id=page_id, children=[toggle])
            except Exception:
                pass

        page_url = f"https://notion.so/{page_id.replace('-', '')}"
        console.print(f"[green]✓ Published to Notion:[/green] {page_url}")
    except Exception as e:
        console.print(f"[red]Notion publish failed:[/red] {e}")
        return False

    return True


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------


@click.command("run", context_settings={"max_content_width": 120})
@click.option(
    "--model",
    "-m",
    default=None,
    help="Transcription model (see 'podx models').",
)
@click.option(
    "--cloud/--no-cloud",
    default=None,
    help="Use cloud GPU. Default: prompt if configured. --no-cloud forces local.",
)
@click.option(
    "--analyze-model",
    default=None,
    help="AI model for analysis. E.g., openai:gpt-5.1, anthropic:claude-sonnet-4-5.",
)
@click.option(
    "--template",
    "-t",
    default=None,
    help="Analysis template (see 'podx templates list').",
)
@click.option(
    "--question",
    "-q",
    default=None,
    help="Follow-up question for the analysis.",
)
@click.option(
    "--through",
    default=None,
    help="Analyze up to this timecode (e.g. '45:00' for partial analysis).",
)
@click.option(
    "--moments",
    default=None,
    help="Flagged moments (e.g. '14:30, 45:12 - pricing framework').",
)
@click.option("--no-oracle", is_flag=True, help="Skip knowledge-oracle analysis.")
@click.option("--no-notion", is_flag=True, help="Skip Notion publish.")
@click.option(
    "--resume",
    is_flag=True,
    help="Resume partial analysis, accumulating moments/questions.",
)
def run(
    model: Optional[str],
    cloud: Optional[bool],
    analyze_model: Optional[str],
    template: Optional[str],
    question: Optional[str],
    through: Optional[str],
    moments: Optional[str],
    no_oracle: bool,
    no_notion: bool,
    resume: bool,
) -> None:
    """Run the full podcast processing pipeline interactively.

    \b
    Walks you through each step:
      1. Fetch: Search and download episode
      2. Transcribe: Convert audio to text
      3. Diarize: Add speaker labels
      4. Cleanup: Clean up transcript text
      5. Analyze: Generate AI analysis (format + knowledge-oracle)
      6. Export: Create markdown files
      7. Publish: Push to Notion

    \b
    Examples:
      podx run                                    # Full interactive wizard
      podx run --cloud                            # Force cloud GPU
      podx run --through 45:00                    # Partial analysis
      podx run --resume ./episode/                # Resume partial
      podx run --moments "14:30, 45:12"           # Flag moments
      podx run -q "How does this apply to X?"     # Follow-up question
      podx run --no-oracle --no-notion            # Skip oracle + Notion
    """
    try:
        # --- Cloud decision ---
        if cloud is None:
            use_cloud = _prompt_cloud()
        else:
            use_cloud = cloud
        if use_cloud and model is None:
            model = "runpod:large-v3"

        # --- Step 1: Fetch ---
        episode_dir = _run_fetch_step()
        if episode_dir is None:
            console.print("[dim]Cancelled[/dim]")
            sys.exit(0)

        # --- Resume: load prior state ---
        prior_moments: List[Dict] = []
        prior_questions: List[str] = []
        prior_through: Optional[str] = None
        if resume:
            prior = _load_partial_state(episode_dir)
            prior_moments = prior.get("flagged_moments", [])
            prior_questions = prior.get("questions", [])
            prior_through = prior.get("analyzed_through")

        # --- Steps 2-4: Transcribe → Diarize → Cleanup ---
        if not _run_transcribe_step(episode_dir, model=model):
            sys.exit(ExitCode.PROCESSING_ERROR)

        if not _run_diarize_step(episode_dir, use_cloud=use_cloud):
            console.print("[yellow]Diarization skipped[/yellow]")

        if not _run_cleanup_step(episode_dir):
            console.print("[yellow]Cleanup skipped[/yellow]")

        # --- Gather analysis prompts ---
        analyzed_through = _prompt_listen_through(through)
        selected_template = _prompt_template(template)
        run_oracle = _prompt_oracle(no_oracle)

        # Show prior state if resuming
        if prior_moments or prior_questions:
            _show_prior_state(prior_moments, prior_questions, prior_through)

        new_moments = _prompt_moments(moments)
        new_questions = _prompt_questions(question)

        # Merge prior + new
        all_moments = prior_moments + new_moments
        all_questions = prior_questions + new_questions

        # --- Analyze (automated) ---
        console.print(
            "\n[bold cyan]── Analyze ────────────────────────────────────────[/bold cyan]"
        )

        _run_analyze_step(
            episode_dir,
            template_name=selected_template,
            model=analyze_model,
            moments=all_moments if all_moments else None,
            questions=all_questions if all_questions else None,
            analyzed_through=analyzed_through,
        )

        if run_oracle:
            _run_analyze_step(
                episode_dir,
                template_name="knowledge-oracle",
                model=analyze_model,
                moments=all_moments if all_moments else None,
                analyzed_through=analyzed_through,
                label="knowledge-oracle",
            )

        # --- Export ---
        _run_export_step(episode_dir)

        # --- Notion ---
        if not no_notion:
            _run_notion_step(episode_dir, format_template=selected_template, model=analyze_model)

        # --- Done ---
        console.print(
            "\n[bold cyan]── Done ───────────────────────────────────────────[/bold cyan]"
        )
        console.print("[green]✓ Pipeline complete[/green]")
        console.print(f"  Files saved to: {episode_dir}")

        sys.exit(ExitCode.SUCCESS)

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    run()
