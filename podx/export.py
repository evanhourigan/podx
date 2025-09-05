import json
import sys
from pathlib import Path

import click


def ts(sec: float) -> str:
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


@click.command()
@click.option(
    "--formats",
    default="txt,srt",
    help="Comma-separated list of output formats (txt, srt, vtt, md) [default: txt,srt]",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory for files (default: same as input)",
)
@click.option(
    "--replace", is_flag=True, help="Only overwrite files if content has changed"
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read Transcript JSON from file instead of stdin",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save output info JSON to file (also prints to stdout)",
)
def main(formats, output_dir, replace, input, output):
    """
    Read (aligned or diarized) Transcript JSON on stdin and write files.
    """
    # Read input
    if input:
        data = json.loads(input.read_text())
    else:
        data = json.loads(sys.stdin.read())

    # Validate input format
    if not data or "segments" not in data:
        raise SystemExit("input must contain Transcript JSON with 'segments' field")

    # Parse formats
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
    result = {
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
