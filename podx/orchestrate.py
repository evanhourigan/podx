#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import click


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
        click.secho(f"  saved: {save_to}", fg="green")

    return data


@click.group()
def main():
    """podx orchestrator: fetch → transcode → transcribe → (align) → (diarize) → (deepcast) → (notion)."""
    pass


@main.command("run")
@click.option("--show", help="Podcast show name (iTunes search)")
@click.option("--rss-url", help="Direct RSS feed URL (alternative to --show)")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--title-contains", help="Substring to match in episode title")
@click.option(
    "--workdir",
    default="work",
    type=click.Path(path_type=Path),
    help="Working directory",
)
@click.option(
    "--fmt",
    default="wav16",
    type=click.Choice(["wav16", "mp3", "aac"]),
    help="Transcode format for ASR step",
)
@click.option(
    "--model",
    default=lambda: os.getenv("PODX_DEFAULT_MODEL", "small.en"),
    help="ASR model",
)
@click.option(
    "--compute",
    default=lambda: os.getenv("PODX_DEFAULT_COMPUTE", "int8"),
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
    help="Compute type",
)
@click.option(
    "--align/--no-align",
    default=False,
    show_default=True,
    help="Run WhisperX alignment",
)
@click.option(
    "--diarize/--no-diarize", default=False, show_default=True, help="Run diarization"
)
@click.option(
    "--deepcast/--no-deepcast",
    default=False,
    show_default=True,
    help="Run LLM summarization",
)
@click.option(
    "--deepcast-model",
    default=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    help="OpenAI model for deepcast",
)
@click.option(
    "--deepcast-temp",
    default=lambda: float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
    type=float,
    help="OpenAI temperature for deepcast",
)
@click.option(
    "--notion/--no-notion",
    default=False,
    show_default=True,
    help="Upload to Notion database",
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
    "--replace-content/--append-content",
    default=False,
    help="Replace page body in Notion instead of appending",
)
@click.option("-v", "--verbose", is_flag=True, help="Print interstitial outputs")
@click.option(
    "--clean/--no-clean",
    default=False,
    help="Delete intermediates after success (keeps final artifacts)",
)
@click.option(
    "--keep-audio/--no-keep-audio",
    default=True,
    help="Preserve downloaded/transcoded audio when --clean is used",
)
def run(
    show: Optional[str],
    rss_url: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
    workdir: Path,
    fmt: str,
    model: str,
    compute: str,
    align: bool,
    diarize: bool,
    deepcast: bool,
    deepcast_model: str,
    deepcast_temp: float,
    notion: bool,
    notion_db: Optional[str],
    title_prop: str,
    date_prop: str,
    replace_content: bool,
    verbose: bool,
    clean: bool,
    keep_audio: bool,
):
    """
    Orchestrate the whole pipeline. Each step runs only if its flag is set or required downstream.
    Saves intermediates to WORKDIR and prints a final summary with key artifact paths.
    """
    wd = Path(workdir)
    wd.mkdir(parents=True, exist_ok=True)

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

    meta = _run(
        fetch_cmd,
        verbose=verbose,
        save_to=wd / "meta.json",
        label="Fetch episode metadata",
    )

    # Track original audio path for cleanup
    original_audio_path = Path(meta["audio_path"]) if "audio_path" in meta else None

    # 2) TRANSCODE → audio.json
    audio = _run(
        ["podx-transcode", "--to", fmt, "--outdir", str(wd)],
        stdin_payload=meta,
        verbose=verbose,
        save_to=wd / "audio.json",
        label=f"Transcode → {fmt}",
    )

    # Track transcoded audio path for cleanup
    transcoded_path = Path(audio["audio_path"])

    # 3) TRANSCRIBE → base.json
    base = _run(
        ["podx-transcribe", "--model", model, "--compute", compute],
        stdin_payload=audio,
        verbose=verbose,
        save_to=wd / "base.json",
        label="Transcribe (faster-whisper)",
    )

    latest = base
    latest_name = "base"

    # 4) ALIGN (optional) → aligned.json
    if align:
        aligned = _run(
            ["podx-align", "--audio", audio["audio_path"]],
            stdin_payload=base,
            verbose=verbose,
            save_to=wd / "aligned.json",
            label="Align (WhisperX)",
        )
        latest = aligned
        latest_name = "aligned"

    # 5) DIARIZE (optional) → diar.json
    if diarize:
        diar = _run(
            ["podx-diarize", "--audio", audio["audio_path"]],
            stdin_payload=latest,
            verbose=verbose,
            save_to=wd / "diar.json",
            label="Diarize (speakers)",
        )
        latest = diar
        latest_name = "diar"

    # Always keep a pointer to the latest JSON/SRT/TXT for convenience
    (wd / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

    # quick TXT/SRT from whatever we have
    _run(
        [
            "podx-export",
            "--srt",
            str(wd / "latest.srt"),
            "--txt",
            str(wd / "latest.txt"),
        ],
        stdin_payload=latest,
        verbose=verbose,
        label="Export TXT/SRT",
    )

    results = {
        "meta": str(wd / "meta.json"),
        "audio": str(wd / "audio.json"),
        "transcript": (
            str(wd / f"{latest_name}.json")
            if (wd / f"{latest_name}.json").exists()
            else str(wd / "latest.json")
        ),
        "latest_json": str(wd / "latest.json"),
        "latest_txt": str(wd / "latest.txt"),
        "latest_srt": str(wd / "latest.srt"),
    }

    # 6) DEEPCAST (optional) → brief.md / brief.json
    if deepcast:
        inp = str(wd / "latest.json")
        md_out = wd / "brief.md"
        json_out = wd / "brief.json"

        cmd = [
            "podx-deepcast",
            "--in",
            inp,
            "--md-out",
            str(md_out),
            "--json-out",
            str(json_out),
            "--model",
            deepcast_model,
            "--temperature",
            str(deepcast_temp),
        ]

        _run(cmd, verbose=verbose, save_to=None, label="Deepcast (LLM synthesis)")
        results.update(
            {
                "deepcast_md": str(md_out),
                "deepcast_json": str(json_out),
            }
        )

    # 7) NOTION (optional) — requires DB id
    if notion:
        if not notion_db:
            raise SystemExit(
                "Please pass --db or set NOTION_DB_ID environment variable"
            )

        # Prefer brief.md from deepcast, fallback to latest.txt
        md_path = (
            str(wd / "brief.md")
            if (wd / "brief.md").exists()
            else str(wd / "latest.txt")
        )
        json_path = str(wd / "brief.json") if (wd / "brief.json").exists() else None

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

        if replace_content:
            cmd += ["--replace-content"]

        notion_resp = _run(
            cmd, verbose=verbose, save_to=wd / "notion.out.json", label="Notion upload"
        )
        results.update({"notion": str(wd / "notion.out.json")})

    # 8) Optional cleanup
    if clean:
        # Keep final artifacts (small pointers)
        keep = {
            wd / "latest.json",
            wd / "latest.txt",
            wd / "latest.srt",
            wd / "brief.md",
            wd / "brief.json",
            wd / "notion.out.json",
            wd / "meta.json",
            wd / "audio.json",
        }

        # Remove intermediate JSON files
        for p in [wd / "base.json", wd / "aligned.json", wd / "diar.json"]:
            if p.exists() and p not in keep:
                try:
                    p.unlink()
                except Exception:
                    pass

        # Remove audio files if not keeping them
        if not keep_audio:
            for p in [transcoded_path, original_audio_path]:
                if p and p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass

    # Final summary
    click.secho("✓ Pipeline complete", fg="green", bold=True)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
