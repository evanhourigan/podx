"""CLI wrapper for export command.

Thin Click wrapper that uses core.export.ExportEngine for actual logic.
Handles CLI arguments, input/output, and result formatting.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import click

from .cli_shared import read_stdin_json
from .core.export import ExportEngine, ExportError


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

    # Parse formats
    format_list = [f.strip().lower() for f in formats.split(",")]

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

    # Use core export engine
    try:
        engine = ExportEngine()
        result = engine.export(
            transcript=data,
            formats=format_list,
            output_dir=out_dir,
            base_name=base_name,
            replace=replace,
        )
    except ExportError as e:
        raise SystemExit(str(e))

    # Save output info if requested
    if output:
        output.write_text(json.dumps(result, indent=2))

    # Always print to stdout
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
