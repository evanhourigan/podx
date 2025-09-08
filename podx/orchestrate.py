#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import click

from .fetch import _generate_workdir
from .progress import (
    PodxProgress,
    format_duration,
    print_podx_header,
    print_podx_info,
    print_podx_success,
)


def _run(
    cmd: List[str],
    stdin_payload: Dict | None = None,
    verbose: bool = False,
    save_to: Path | None = None,
    label: str | None = None,
) -> Dict:
    """Run a CLI tool that prints JSON to stdout; return parsed dict. If verbose, echo stdout to console. Optionally save stdout JSON to file."""
    if label:
        click.secho(f"→ {label}", fg="cyan", bold=True)

    proc = subprocess.run(
        cmd,
        input=json.dumps(stdin_payload) if stdin_payload else None,
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        raise SystemExit(f"Command failed: {' '.join(cmd)}\n{err}")

    # stdout should be JSON; optionally mirror to console
    out = proc.stdout

    if verbose:
        # Show a compact preview of the JSON output
        preview = out[:400] + "..." if len(out) > 400 else out
        click.secho(preview, fg="white")

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # Some subcommands (e.g., deepcast/notion) print plain text "Wrote: ..."
        data = {"stdout": out.strip()}

    if save_to:
        save_to.write_text(out, encoding="utf-8")
        # Don't print "saved:" message when in progress context
        # The progress system will handle completion messages

    return data


@click.group()
def main():
    """Podx: Composable podcast processing pipeline

    A modular toolkit for podcast transcription, analysis, and publishing.
    Use 'podx run' for the complete pipeline or individual tools for specific tasks.
    """
    pass


@main.command("run", help="Orchestrate the complete podcast processing pipeline.")
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--workdir",
    type=click.Path(path_type=Path),
    help="Override working directory (bypasses smart naming)",
)
@click.option(
    "--fmt",
    default="wav16",
    type=click.Choice(["wav16", "mp3", "aac"]),
    help="Transcode format for ASR step [default: wav16]",
)
@click.option(
    "--model",
    default=lambda: os.getenv("PODX_DEFAULT_MODEL", "small.en"),
    help="ASR transcription model (tiny, base, small, medium, large, large-v2, large-v3) [default: small.en]",
)
@click.option(
    "--compute",
    default=lambda: os.getenv("PODX_DEFAULT_COMPUTE", "int8"),
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type [default: int8]",
)
@click.option(
    "--align",
    is_flag=True,
    help="Run WhisperX alignment (default: no alignment)",
)
@click.option(
    "--diarize",
    is_flag=True,
    help="Run diarization (default: no diarization)",
)
@click.option(
    "--deepcast",
    is_flag=True,
    help="Run LLM summarization (default: no AI analysis)",
)
@click.option(
    "--deepcast-model",
    default=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    help="OpenAI model for AI analysis (gpt-4.1, gpt-4.1-mini) [default: gpt-4.1-mini]",
)
@click.option(
    "--deepcast-temp",
    default=lambda: float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
    type=float,
    help="OpenAI temperature for deepcast [default: 0.2]",
)
@click.option(
    "--extract-markdown",
    is_flag=True,
    help="Also extract raw markdown file when running deepcast",
)
@click.option(
    "--notion",
    is_flag=True,
    help="Upload to Notion database (default: no upload)",
)
@click.option(
    "--db",
    "notion_db",
    default=lambda: os.getenv("NOTION_DB_ID"),
    help="Notion database ID (required if --notion)",
)
@click.option(
    "--title-prop",
    default=lambda: os.getenv("NOTION_TITLE_PROP", "Name"),
    help="Notion property name for title",
)
@click.option(
    "--date-prop",
    default=lambda: os.getenv("NOTION_DATE_PROP", "Date"),
    help="Notion property name for date",
)
@click.option(
    "--append-content",
    is_flag=True,
    help="Append to page body in Notion instead of replacing (default: replace)",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
@click.option(
    "--clean",
    is_flag=True,
    help="Delete intermediates after success (default: keep all files)",
)
@click.option(
    "--no-keep-audio",
    is_flag=True,
    help="Delete audio files when --clean is used (default: keep audio)",
)
def run(
    show: Optional[str],
    rss_url: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
    workdir: Optional[Path],
    fmt: str,
    model: str,
    compute: str,
    align: bool,
    diarize: bool,
    deepcast: bool,
    deepcast_model: str,
    deepcast_temp: float,
    extract_markdown: bool,
    notion: bool,
    notion_db: Optional[str],
    title_prop: str,
    date_prop: str,
    append_content: bool,
    verbose: bool,
    clean: bool,
    no_keep_audio: bool,
):
    """Orchestrate the complete podcast processing pipeline."""
    # Print header and start progress tracking
    print_podx_header()

    # Show pipeline configuration
    steps = ["fetch", "transcode", "transcribe"]
    if align:
        steps.append("align")
    if diarize:
        steps.append("diarize")
    steps.extend(["export"])
    if deepcast:
        steps.append("deepcast")
    if notion:
        steps.append("notion")

    print_podx_info(f"Pipeline: {' → '.join(steps)}")

    start_time = time.time()

    # Initialize results dictionary
    results = {}

    # Use progress tracking for the entire pipeline
    with PodxProgress() as progress:
        # We'll determine the actual workdir after fetching metadata
        wd = None  # Will be set after fetch

        # 1) FETCH → meta.json
        fetch_cmd = ["podx-fetch"]
        if show:
            fetch_cmd.extend(["--show", show])
        elif rss_url:
            fetch_cmd.extend(["--rss-url", rss_url])
        else:
            raise SystemExit("Either --show or --rss-url must be provided.")

        if date:
            fetch_cmd.extend(["--date", date])
        if title_contains:
            fetch_cmd.extend(["--title-contains", title_contains])

        # Run fetch first to get metadata, then determine workdir
        progress.start_step("Fetching episode metadata")
        meta = _run(
            fetch_cmd,
            verbose=verbose,
            save_to=None,  # Don't save yet, we'll save after determining workdir
            label=None,  # Progress handles the display
        )
        progress.complete_step(
            f"Episode fetched: {meta.get('episode_title', 'Unknown')}"
        )

        # Determine workdir from metadata
        if workdir:
            # Override: use specified workdir
            wd = Path(workdir)
        else:
            # Default: use smart naming with spaces
            show_name = meta.get("show", "Unknown Show")
            episode_date = meta.get("episode_published") or date or "unknown"
            wd = _generate_workdir(show_name, episode_date)

        wd.mkdir(parents=True, exist_ok=True)
        # Save metadata to the determined workdir
        (wd / "episode-meta.json").write_text(json.dumps(meta, indent=2))

        # Track original audio path for cleanup
        original_audio_path = Path(meta["audio_path"]) if "audio_path" in meta else None

        # 2) TRANSCODE → audio-meta.json
        progress.start_step(f"Transcoding audio to {fmt}")
        step_start = time.time()
        audio = _run(
            ["podx-transcode", "--to", fmt, "--outdir", str(wd)],
            stdin_payload=meta,
            verbose=verbose,
            save_to=wd / "audio-meta.json",
            label=None,  # Progress handles the display
        )
        step_duration = time.time() - step_start
        progress.complete_step(f"Audio transcoded to {fmt}", step_duration)

        # Track transcoded audio path for cleanup
        transcoded_path = Path(audio["audio_path"])

        # 3) TRANSCRIBE → transcript.json
        progress.start_step(f"Transcribing with {model} model")
        step_start = time.time()
        base = _run(
            ["podx-transcribe", "--model", model, "--compute", compute],
            stdin_payload=audio,
            verbose=verbose,
            save_to=wd / "transcript.json",
            label=None,  # Progress handles the display
        )
        step_duration = time.time() - step_start
        progress.complete_step(
            f"Transcription complete - {len(base.get('segments', []))} segments",
            step_duration,
        )

        latest = base
        latest_name = "transcript"

        # 4) ALIGN (optional) → aligned-transcript.json
        if align:
            progress.start_step("Aligning transcript with audio")
            step_start = time.time()
            aligned = _run(
                ["podx-align", "--audio", audio["audio_path"]],
                stdin_payload=base,
                verbose=verbose,
                save_to=wd / "aligned-transcript.json",
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step("Audio alignment completed", step_duration)
            latest = aligned
            latest_name = "aligned-transcript"

        # 5) DIARIZE (optional) → diarized-transcript.json
        if diarize:
            progress.start_step("Identifying speakers")
            step_start = time.time()
            # Debug: Check what we're passing to diarize
            if verbose:
                click.secho(
                    f"Debug: Passing {latest_name} JSON to diarize with {len(latest.get('segments', []))} segments",
                    fg="yellow",
                )
            diar = _run(
                ["podx-diarize", "--audio", audio["audio_path"]],
                stdin_payload=latest,
                verbose=verbose,
                save_to=wd / "diarized-transcript.json",
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step("Speaker diarization completed", step_duration)
            latest = diar
            latest_name = "diarized-transcript"

        # Always keep a pointer to the latest JSON/SRT/TXT for convenience
        (wd / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

        # quick TXT/SRT from whatever we have
        progress.start_step("Exporting transcript files")
        step_start = time.time()
        export_result = _run(
            [
                "podx-export",
                "--formats",
                "txt,srt",
                "--output-dir",
                str(wd),
                "--input",
                str(wd / f"{latest_name}.json"),
                "--replace",
            ],
            stdin_payload=latest,
            verbose=verbose,
            label=None,  # Progress handles the display
        )
        step_duration = time.time() - step_start
        progress.complete_step("Transcript files exported (TXT, SRT)", step_duration)

        # Build results using export output paths when available
        exported_files = (
            export_result.get("files", {}) if isinstance(export_result, dict) else {}
        )
        results = {
            "meta": str(wd / "episode-meta.json"),
            "audio": str(wd / "audio-meta.json"),
            "transcript": str(wd / f"{latest_name}.json"),
            "latest_json": str(wd / "latest.json"),
        }
        if "txt" in exported_files:
            results["latest_txt"] = exported_files["txt"]
        else:
            results["latest_txt"] = str(wd / f"{latest_name}.txt")
        if "srt" in exported_files:
            results["latest_srt"] = exported_files["srt"]
        else:
            results["latest_srt"] = str(wd / f"{latest_name}.srt")

        # 6) DEEPCAST (optional) → deepcast-brief.md / deepcast-brief.json
        if deepcast:
            progress.start_step(f"Analyzing transcript with {deepcast_model}")
            step_start = time.time()
            inp = str(wd / "latest.json")
            md_out = wd / "deepcast-brief.md"
            json_out = wd / "deepcast-brief.json"

            cmd = [
                "podx-deepcast",
                "--input",
                inp,
                "--output",
                str(json_out),
                "--model",
                deepcast_model,
                "--temperature",
                str(deepcast_temp),
            ]

            if extract_markdown:
                cmd.append("--extract-markdown")

            _run(
                cmd, verbose=verbose, save_to=None, label=None
            )  # Progress handles the display
            step_duration = time.time() - step_start
            progress.complete_step("AI analysis completed", step_duration)
            results.update({"deepcast_json": str(json_out)})
            # Record markdown path when extracted
            if extract_markdown and md_out.exists():
                results.update({"deepcast_md": str(md_out)})

        # 7) NOTION (optional) — requires DB id
        if notion:
            if not notion_db:
                raise SystemExit(
                    "Please pass --db or set NOTION_DB_ID environment variable"
                )

            progress.start_step("Uploading to Notion")
            step_start = time.time()
            # Prefer brief.md from deepcast, fallback to latest.txt
            # Prefer deepcast outputs; fallback to latest.txt
            md_path = (
                str(wd / "deepcast-brief.md")
                if (wd / "deepcast-brief.md").exists()
                else str(wd / "latest.txt")
            )
            json_path = (
                str(wd / "deepcast-brief.json")
                if (wd / "deepcast-brief.json").exists()
                else None
            )

            cmd = [
                "podx-notion",
                "--markdown",
                md_path,
                "--meta",
                str(wd / "latest.json"),
                "--db",
                notion_db,
                "--title-prop",
                title_prop,
                "--date-prop",
                date_prop,
            ]

            if json_path:
                cmd += ["--json", json_path]

            if append_content:
                cmd += ["--append-content"]
            # Default is replace, so no flag needed when append_content is False

            notion_resp = _run(
                cmd,
                verbose=verbose,
                save_to=wd / "notion.out.json",
                label=None,  # Progress handles the display
            )
            step_duration = time.time() - step_start
            progress.complete_step("Notion page created/updated", step_duration)
            results.update({"notion": str(wd / "notion.out.json")})

        # 8) Optional cleanup
        if clean:
            progress.start_step("Cleaning up intermediate files")
            step_start = time.time()
            # Keep final artifacts (small pointers)
            keep = {
                wd / "latest.json",
                wd / f"{latest_name}.txt",
                wd / f"{latest_name}.srt",
                wd / "deepcast-brief.md",
                wd / "deepcast-brief.json",
                wd / "notion.out.json",
                wd / "episode-meta.json",
                wd / "audio-meta.json",
            }

            # Remove intermediate JSON files
            for p in [
                wd / "transcript.json",
                wd / "aligned-transcript.json",
                wd / "diarized-transcript.json",
            ]:
                if p.exists() and p not in keep:
                    try:
                        p.unlink()
                    except Exception:
                        pass

            # Remove audio files if not keeping them
            if no_keep_audio:
                for p in [transcoded_path, original_audio_path]:
                    if p and p.exists():
                        try:
                            p.unlink()
                        except Exception:
                            pass
            step_duration = time.time() - step_start
            progress.complete_step("Cleanup completed", step_duration)

    # Final summary
    total_time = time.time() - start_time
    print_podx_success(f"Pipeline completed in {format_duration(total_time)}")

    # Show key results
    key_files = []
    if "latest_txt" in results:
        key_files.append(f"📄 Transcript: {results['latest_txt']}")
    if "latest_srt" in results:
        key_files.append(f"📺 Subtitles: {results['latest_srt']}")
    if "deepcast_md" in results:
        key_files.append(f"🤖 Analysis: {results['deepcast_md']}")
    if "notion" in results:
        key_files.append(f"☁️ Notion: {results['notion']}")

    if key_files:
        print_podx_info("\n".join(key_files))

    # Still print JSON for programmatic use
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
