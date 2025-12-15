"""Main run command - interactive wizard for full pipeline.

No options - walks through each step sequentially using the same UI
as individual commands. For scripting, use individual commands instead.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.domain.exit_codes import ExitCode

console = Console()


def _run_fetch_step() -> Optional[Path]:
    """Run fetch step interactively. Returns episode directory or None."""
    from podx.cli.fetch import PodcastFetcher, _run_interactive

    console.print("\n[bold cyan]── Fetch ──────────────────────────────────────────[/bold cyan]")

    fetcher = PodcastFetcher()
    result = _run_interactive(fetcher)

    if result is None:
        return None

    return Path(result["directory"])


def _run_transcribe_step(episode_dir: Path) -> bool:
    """Run transcribe step. Returns True on success."""
    import json

    from podx.cli.transcribe import _find_audio_file
    from podx.config import get_config
    from podx.core.transcribe import TranscriptionEngine, TranscriptionError
    from podx.ui import LiveTimer

    console.print("\n[bold cyan]── Transcribe ─────────────────────────────────────[/bold cyan]")

    # Check if already transcribed
    transcript_path = episode_dir / "transcript.json"
    if transcript_path.exists():
        console.print("[dim]Transcript already exists, skipping...[/dim]")
        return True

    # Find audio
    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        console.print("[red]Error:[/red] No audio file found")
        return False

    model = get_config().default_asr_model
    console.print(f"[dim]Transcribing with {model}...[/dim]")

    timer = LiveTimer("Transcribing")
    timer.start()

    try:
        engine = TranscriptionEngine(model=model)
        result = engine.transcribe(audio_file)
    except TranscriptionError as e:
        timer.stop()
        console.print(f"[red]Error:[/red] {e}")
        return False

    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    result["audio_path"] = str(audio_file)
    transcript_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[green]✓ Transcription complete ({minutes}:{seconds:02d})[/green]")
    return True


def _run_diarize_step(episode_dir: Path) -> bool:
    """Run diarize step. Returns True on success."""
    import json
    import os
    from contextlib import redirect_stderr, redirect_stdout

    from podx.cli.diarize import _find_audio_file
    from podx.core.diarize import DiarizationEngine, DiarizationError
    from podx.ui import LiveTimer

    console.print("\n[bold cyan]── Diarize ────────────────────────────────────────[/bold cyan]")

    # Load transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print("[red]Error:[/red] No transcript found")
        return False

    transcript = json.loads(transcript_path.read_text())

    # Check if already diarized
    if transcript.get("diarized"):
        console.print("[dim]Already diarized, skipping...[/dim]")
        return True

    # Find audio
    audio_file = _find_audio_file(episode_dir)
    if not audio_file:
        console.print("[red]Error:[/red] No audio file found")
        return False

    console.print("[dim]Adding speaker labels...[/dim]")

    timer = LiveTimer("Diarizing")
    timer.start()

    try:
        with (
            redirect_stdout(open(os.devnull, "w")),
            redirect_stderr(open(os.devnull, "w")),
        ):
            engine = DiarizationEngine(
                language=transcript.get("language", "en"),
                hf_token=os.getenv("HUGGINGFACE_TOKEN"),
            )
            result = engine.diarize(audio_file, transcript["segments"])
    except DiarizationError as e:
        timer.stop()
        console.print(f"[red]Error:[/red] {e}")
        return False

    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Update transcript
    transcript["segments"] = result["segments"]
    transcript["diarized"] = True
    transcript_path.write_text(
        json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Count speakers
    speakers = set(s.get("speaker") for s in result["segments"] if s.get("speaker"))
    console.print(f"[green]✓ Diarization complete ({minutes}:{seconds:02d})[/green]")
    console.print(f"  Speakers found: {len(speakers)}")
    return True


def _run_cleanup_step(episode_dir: Path) -> bool:
    """Run cleanup step. Returns True on success."""
    import json
    import os

    from podx.core.preprocess import PreprocessError, TranscriptPreprocessor
    from podx.ui import LiveTimer

    console.print("\n[bold cyan]── Cleanup ────────────────────────────────────────[/bold cyan]")

    # Load transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print("[red]Error:[/red] No transcript found")
        return False

    transcript = json.loads(transcript_path.read_text())

    # Check if already cleaned
    if transcript.get("cleaned"):
        console.print("[dim]Already cleaned, skipping...[/dim]")
        return True

    # Check if we have OpenAI key for restore
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

    # Preserve existing metadata
    original_keys = [
        "audio_path",
        "language",
        "asr_model",
        "asr_provider",
        "decoder_options",
        "diarized",
    ]
    for key in original_keys:
        if key in transcript:
            result[key] = transcript[key]

    # Set cleanup state flags
    result["cleaned"] = True
    result["restored"] = do_restore

    # Save updated transcript
    transcript_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    original_count = len(transcript["segments"])
    merged_count = len(result["segments"])
    console.print(f"[green]✓ Cleanup complete ({minutes}:{seconds:02d})[/green]")
    console.print(f"  Segments: {original_count} → {merged_count}")
    return True


def _run_analyze_step(episode_dir: Path) -> bool:
    """Run analyze step. Returns True on success."""
    import json
    from datetime import datetime, timezone

    from podx.core.analyze import AnalyzeEngine, AnalyzeError
    from podx.templates.manager import TemplateManager
    from podx.ui import LiveTimer

    console.print("\n[bold cyan]── Analyze ────────────────────────────────────────[/bold cyan]")

    # Load transcript
    transcript_path = episode_dir / "transcript.json"
    if not transcript_path.exists():
        console.print("[red]Error:[/red] No transcript found")
        return False

    transcript = json.loads(transcript_path.read_text())

    # Check if already analyzed
    analysis_path = episode_dir / "analysis.json"
    if analysis_path.exists():
        console.print("[dim]Analysis already exists, skipping...[/dim]")
        return True

    model = "gpt-4o-mini"  # Default
    template = "general"

    console.print(f"[dim]Analyzing with {model}...[/dim]")

    timer = LiveTimer("Analyzing")
    timer.start()

    try:
        manager = TemplateManager()
        tmpl = manager.load(template)

        engine = AnalyzeEngine(model=model)

        # Build transcript text
        segments = transcript.get("segments", [])
        transcript_text = "\n".join(
            (
                f"[{s.get('speaker', 'SPEAKER')}] {s.get('text', '')}"
                if s.get("speaker")
                else s.get("text", "")
            )
            for s in segments
        )

        speakers = set(s.get("speaker") for s in segments if s.get("speaker"))
        context = {
            "transcript": transcript_text,
            "speaker_count": len(speakers) if speakers else 1,
            "duration": int(segments[-1].get("end", 0) // 60) if segments else 0,
        }

        system_prompt, user_prompt = tmpl.render(context)
        md, json_data = engine.analyze(
            transcript=transcript,
            system_prompt=system_prompt,
            map_instructions="Extract key points, notable quotes, and insights from this section.",
            reduce_instructions=user_prompt,
            want_json=True,
        )
    except AnalyzeError as e:
        timer.stop()
        console.print(f"[red]Error:[/red] {e}")
        return False

    elapsed = timer.stop()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Save analysis
    result = {
        "markdown": md,
        "template": template,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if json_data:
        result.update(json_data)

    analysis_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[green]✓ Analysis complete ({minutes}:{seconds:02d})[/green]")
    return True


def _run_export_step(episode_dir: Path) -> bool:
    """Run export step. Returns True on success."""
    console.print("\n[bold cyan]── Export ─────────────────────────────────────────[/bold cyan]")

    # Export transcript to markdown
    transcript_path = episode_dir / "transcript.json"
    if transcript_path.exists():
        import json

        transcript = json.loads(transcript_path.read_text())
        segments = transcript.get("segments", [])

        # Build markdown
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

    # Export analysis to markdown
    analysis_path = episode_dir / "analysis.json"
    if analysis_path.exists():
        import json

        analysis = json.loads(analysis_path.read_text())
        md = analysis.get("markdown", "")
        if md:
            md_path = episode_dir / "analysis.md"
            md_path.write_text(md, encoding="utf-8")
            console.print("  Exported: analysis.md")

    return True


@click.command("run", context_settings={"max_content_width": 120})
def run():
    """Run the full podcast processing pipeline interactively.

    \b
    No options - walks you through each step:
      1. Fetch: Search and download episode
      2. Transcribe: Convert audio to text
      3. Diarize: Add speaker labels
      4. Cleanup: Clean up transcript text
      5. Analyze: Generate AI analysis
      6. Export: Create markdown files

    \b
    For scripting, use individual commands:
      podx fetch --show "Lex" --date 2024-11-24
      podx transcribe ./episode/
      podx diarize ./episode/
      podx cleanup ./episode/
      podx analyze ./episode/
    """
    try:
        # Step 1: Fetch
        episode_dir = _run_fetch_step()
        if episode_dir is None:
            console.print("[dim]Cancelled[/dim]")
            sys.exit(0)

        # Step 2: Transcribe
        if not _run_transcribe_step(episode_dir):
            sys.exit(ExitCode.PROCESSING_ERROR)

        # Step 3: Diarize
        if not _run_diarize_step(episode_dir):
            # Diarization failure is not fatal - continue
            console.print("[yellow]Diarization skipped[/yellow]")

        # Step 4: Cleanup
        if not _run_cleanup_step(episode_dir):
            # Cleanup failure is not fatal - continue
            console.print("[yellow]Cleanup skipped[/yellow]")

        # Step 5: Analyze
        if not _run_analyze_step(episode_dir):
            # Analysis failure is not fatal - continue
            console.print("[yellow]Analysis skipped[/yellow]")

        # Step 6: Export
        _run_export_step(episode_dir)

        # Done
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
