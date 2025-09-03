import json
import subprocess
from pathlib import Path

import click


def run_cmd(cmd: list, stdin_payload: dict | None = None) -> dict:
    proc = subprocess.run(
        cmd,
        input=(json.dumps(stdin_payload) if stdin_payload else None),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"Command failed: {' '.join(cmd)}")
    return json.loads(proc.stdout)


@click.group()
def main():
    """Convenience wrapper calling the smaller tools under the hood."""
    pass


@main.command("run")
@click.option("--show", required=True)
@click.option("--date")
@click.option("--title-contains")
@click.option("--align/--no-align", default=False, show_default=True)
@click.option("--diarize/--no-diarize", default=False, show_default=True)
@click.option(
    "--workdir", default="work", show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--model", default=None, help="Override model (e.g., small.en, medium.en)."
)
@click.option(
    "--compute",
    default=None,
    type=click.Choice(["int8", "int8_float16", "float16", "float32"]),
)
def run(show, date, title_contains, align, diarize, workdir, model, compute):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    meta = run_cmd(
        ["podx-fetch", "--show", show]
        + (["--date", date] if date else [])
        + (["--title-contains", title_contains] if title_contains else [])
    )
    # transcode to wav16
    audio = run_cmd(
        ["podx-transcode", "--to", "wav16", "--outdir", str(workdir)],
        stdin_payload=meta,
    )
    # transcribe
    transcribe_cmd = ["podx-transcribe"]
    if model:
        transcribe_cmd += ["--model", model]
    if compute:
        transcribe_cmd += ["--compute", compute]
    base = run_cmd(transcribe_cmd, stdin_payload=audio)

    latest = base
    if align:
        aligned = run_cmd(
            ["podx-align", "--audio", audio["audio_path"]], stdin_payload=base
        )
        latest = aligned
        if diarize:
            diar = run_cmd(
                ["podx-diarize", "--audio", audio["audio_path"]], stdin_payload=aligned
            )
            latest = diar

    # write some convenience files
    (workdir / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")
    # quick SRT/TXT
    subprocess.run(
        [
            "podx-export",
            "--srt",
            str(workdir / "latest.srt"),
            "--txt",
            str(workdir / "latest.txt"),
        ],
        input=json.dumps(latest),
        text=True,
        check=True,
    )

    print(
        json.dumps(
            {
                "meta": meta,
                "audio": audio,
                "result_path": str(workdir / "latest.json"),
                "srt": str(workdir / "latest.srt"),
                "txt": str(workdir / "latest.txt"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
