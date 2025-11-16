"""CLI wrapper for export command.

Thin Click wrapper that uses core.export.ExportEngine for actual logic.
Handles CLI arguments, input/output, and result formatting.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console

from podx.cli.cli_shared import read_stdin_json
from podx.core.export import ExportEngine, ExportError
from podx.domain.exit_codes import ExitCode

console = Console()


@click.command(
    help="Export transcript JSON to text formats (txt, srt, vtt, md, pdf, html)"
)
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
    help="Output formats: txt, srt, vtt, md, pdf, html (comma-separated, default: txt,srt)",
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
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output structured JSON (suppresses Rich formatting)",
)
def main(
    input: Optional[Path],
    output: Optional[Path],
    formats: str,
    output_dir: Optional[Path],
    replace: bool,
    json_output: bool,
):
    """
    Convert transcript JSON to various text formats.

    Supports:
    - TXT: Plain text, one segment per line
    - SRT: SubRip subtitle format with timestamps
    - VTT: WebVTT subtitle format with timestamps
    - MD: Markdown format with heading
    - PDF: Professional PDF document (ReportLab)
    - HTML: Interactive HTML with search and dark mode

    Reads transcript JSON from --input file or stdin.
    Writes output files to --output-dir or same directory as input.

    Examples:
        podx-export -i transcript.json --formats txt,srt,md
        podx-export -i transcript.json --formats pdf,html
        cat transcript.json | podx-export --formats vtt
    """
    # Read input
    data: Optional[Dict[str, Any]] = None
    if input:
        try:
            data = json.loads(input.read_text(encoding="utf-8"))
        except Exception as e:
            if json_output:
                print(
                    json.dumps(
                        {
                            "error": f"Failed to read input file: {e}",
                            "type": "file_error",
                        }
                    )
                )
            else:
                console.print(f"[red]Error:[/red] Failed to read input file: {e}")
            sys.exit(ExitCode.USER_ERROR)
    else:
        raw = read_stdin_json()
        if isinstance(raw, dict):
            data = raw

    if not data:
        if json_output:
            print(
                json.dumps(
                    {
                        "error": "Provide transcript JSON via --input or stdin",
                        "type": "validation_error",
                    }
                )
            )
        else:
            console.print(
                "[red]Error:[/red] Provide transcript JSON via --input or stdin"
            )
        sys.exit(ExitCode.USER_ERROR)

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
        if json_output:
            print(json.dumps({"error": str(e), "type": "export_error"}))
        else:
            console.print(f"[red]Export Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)

    # Save output info if requested
    if output:
        output.write_text(json.dumps(result, indent=2))

    # Output to stdout
    if json_output:
        # Structured JSON output
        output_data = {
            "success": True,
            "files": result,
            "stats": {
                "formats": format_list,
                "files_created": len(result),
            },
        }
        print(json.dumps(output_data, indent=2))
    else:
        # Rich formatted output (existing behavior)
        print(json.dumps(result, indent=2))

    # Exit with success
    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
