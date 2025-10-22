"""Convert transcript JSON to various text formats (txt, srt, vtt, md)."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import click

from .cli_shared import read_stdin_json


def ts(sec: float) -> str:
    """Format seconds as SRT/VTT timestamp (HH:MM:SS,mmm or HH:MM:SS.mmm)."""
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_if_changed(path: Path, content: str, replace: bool = False) -> None:
    """Write content to file only if it has changed (when replace=True)."""
    if replace and path.exists():
        existing_content = path.read_text(encoding="utf-8")
        if existing_content == content:
            return  # Content unchanged, skip write

    path.write_text(content, encoding="utf-8")


@click.command(help="Export transcript JSON to text formats (txt, srt, vtt, md)")
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Input transcript JSON file (or read from stdin)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save output info JSON (summary of files written)",
)
@click.option(
    "--formats",
    default="txt,srt",
    help="Output formats: comma-separated list of txt, srt, vtt, md (default: txt,srt)",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory (default: same as input file, or current directory)",
)
@click.option(
    "--replace",
    is_flag=True,
    help="Only overwrite files if content has changed",
)
def main(
    input: Optional[Path],
    output: Optional[Path],
    formats: str,
    output_dir: Optional[Path],
    replace: bool,
):
    """
    Convert transcript JSON to various text formats.

    Supports:
    - TXT: Plain text, one segment per line
    - SRT: SubRip subtitle format with timestamps
    - VTT: WebVTT subtitle format with timestamps
    - MD: Markdown format with heading

    Reads transcript JSON from --input file or stdin.
    Writes output files to --output-dir or same directory as input.

    Examples:
        podx-export -i transcript.json --formats txt,srt,md
        cat transcript.json | podx-export --formats vtt
    """
    # Read input
    data: Optional[Dict[str, Any]] = None
    if input:
        try:
            data = json.loads(input.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit(f"Failed to read input file: {e}")
    else:
        raw = read_stdin_json()
        if isinstance(raw, dict):
            data = raw

    if not data:
        raise SystemExit("Provide transcript JSON via --input or stdin")

    # Validate input is a transcript (has segments)
    if "segments" not in data:
        raise SystemExit(
            "Input JSON does not appear to be a transcript (missing 'segments' field)"
        )

    # Parse and validate formats
    format_list = [f.strip().lower() for f in formats.split(",")]
    valid_formats = {"txt", "srt", "vtt", "md"}
    invalid_formats = set(format_list) - valid_formats
    if invalid_formats:
        raise SystemExit(
            f"Invalid formats: {', '.join(invalid_formats)}. Valid: {', '.join(valid_formats)}"
        )

    # Determine output directory
    if output_dir:
        out_dir = output_dir
    elif input:
        out_dir = input.parent
    else:
        out_dir = Path(".")

    # Generate base filename from input
    if input:
        base_name = input.stem
    else:
        base_name = "transcript"

    segs = data.get("segments") or []
    output_files = {}

    # Generate files for each requested format
    for fmt in format_list:
        if fmt == "txt":
            content = "\n".join(s["text"].strip() for s in segs) + "\n"
            out_path = out_dir / f"{base_name}.txt"
            write_if_changed(out_path, content, replace)
            output_files["txt"] = str(out_path)

        elif fmt == "srt":
            lines = []
            for i, s in enumerate(segs, 1):
                speaker = s.get("speaker")
                line = (
                    s["text"].strip()
                    if not speaker
                    else f"[{speaker}] {s['text'].strip()}"
                )
                lines += [str(i), f"{ts(s['start'])} --> {ts(s['end'])}", line, ""]
            content = "\n".join(lines)
            out_path = out_dir / f"{base_name}.srt"
            write_if_changed(out_path, content, replace)
            output_files["srt"] = str(out_path)

        elif fmt == "vtt":
            lines = ["WEBVTT", ""]
            for s in segs:
                speaker = s.get("speaker")
                line = (
                    s["text"].strip()
                    if not speaker
                    else f"[{speaker}] {s['text'].strip()}"
                )
                lines += [
                    f"{ts(s['start']).replace(',', '.')} --> {ts(s['end']).replace(',', '.')}",
                    line,
                    "",
                ]
            content = "\n".join(lines)
            out_path = out_dir / f"{base_name}.vtt"
            write_if_changed(out_path, content, replace)
            output_files["vtt"] = str(out_path)

        elif fmt == "md":
            content = (
                "# Transcript\n\n" + "\n\n".join(s["text"].strip() for s in segs) + "\n"
            )
            out_path = out_dir / f"{base_name}.md"
            write_if_changed(out_path, content, replace)
            output_files["md"] = str(out_path)

    # Create output info
    result: Dict[str, Any] = {
        "formats": format_list,
        "output_dir": str(out_dir),
        "files": output_files,
        "segments_count": len(segs),
    }

    # Save output info if requested
    if output:
        output.write_text(json.dumps(result, indent=2))

    # Always print to stdout
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
