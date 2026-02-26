"""CLI commands for exporting transcripts and analyses.

Simplified v4.0 with subcommands for transcript and analysis export.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.domain.exit_codes import ExitCode
from podx.ui import (
    get_export_formats_help,
    prompt_with_help,
    select_episode_interactive,
    show_confirmation,
    validate_export_format,
)

console = Console()

# Default formats for each export type
DEFAULT_TRANSCRIPT_FORMAT = "md"
DEFAULT_ANALYSIS_FORMAT = "md"


@click.group(context_settings={"max_content_width": 120})
def main() -> None:
    """Export transcript or analysis to various formats.

    \b
    Subcommands:
      transcript    Export transcript to text/subtitle formats
      analysis      Export analysis to document formats
      all           Export both transcript and analysis in all formats
    """
    pass


def _find_transcript(directory: Path) -> Optional[Path]:
    """Find transcript file in episode directory."""
    transcript = directory / "transcript.json"
    if transcript.exists():
        return transcript

    # Legacy patterns
    patterns = ["transcript-*.json"]
    for pattern in patterns:
        matches = list(directory.glob(pattern))
        if matches:
            for m in matches:
                if "preprocessed" not in m.name:
                    return m
    return None


def _find_all_analyses(directory: Path) -> list[Path]:
    """Find all analysis files in episode directory.

    Returns list of paths sorted by modification time (newest first).
    """
    candidates = []

    # Standard analysis.json
    analysis = directory / "analysis.json"
    if analysis.exists():
        candidates.append(analysis)

    # Template-specific analysis files
    for p in directory.glob("analysis.*.json"):
        if p.suffix == ".json" and p not in candidates:
            candidates.append(p)

    # Legacy patterns
    for pattern in ["deepcast-*.json", "deepcast.json"]:
        for p in directory.glob(pattern):
            if p not in candidates:
                candidates.append(p)

    # Sort by modification time, newest first
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


def _find_analysis(
    directory: Path, template: Optional[str] = None, model: Optional[str] = None
) -> Optional[Path]:
    """Find analysis file in episode directory.

    Args:
        directory: Episode directory to search
        template: Optional template name to find template-specific analysis
        model: Optional model name to find model-specific analysis
    """
    # Exact match when both template and model are provided
    if template or model:
        from podx.cli.analyze import DEFAULT_MODEL, DEFAULT_TEMPLATE, analysis_output_path

        exact = analysis_output_path(
            directory,
            template or DEFAULT_TEMPLATE,
            model or DEFAULT_MODEL,
        )
        if exact.exists():
            return exact

    # Template-specific fallback (any model) for backwards compat
    if template and template != "general":
        for p in directory.glob(f"analysis.{template}*.json"):
            if p.suffix == ".json":
                return p

    # Return first (most recent) analysis file
    candidates = _find_all_analyses(directory)
    return candidates[0] if candidates else None


def _export_transcript_txt(transcript: dict, output_path: Path, timestamps: bool = False) -> None:
    """Export transcript to plain text."""
    lines = []
    for seg in transcript.get("segments", []):
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        start = seg.get("start", 0)

        if timestamps:
            ts = _format_timestamp_readable(start)
            if speaker:
                lines.append(f"{ts} {speaker}: {text}")
            else:
                lines.append(f"{ts} {text}")
        else:
            if speaker:
                lines.append(f"{speaker}: {text}")
            else:
                lines.append(text)
    output_path.write_text("\n\n".join(lines), encoding="utf-8")


def _export_transcript_md(
    transcript: dict, output_path: Path, timestamps: bool = False, video_url: str = None
) -> None:
    """Export transcript to markdown."""
    lines = ["# Transcript\n"]
    for seg in transcript.get("segments", []):
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        start = seg.get("start", 0)

        if timestamps:
            ts = _format_timestamp_readable(start, video_url)
            if speaker:
                lines.append(f"**{ts} {speaker}:** {text}\n")
            else:
                lines.append(f"**{ts}** {text}\n")
        else:
            if speaker:
                lines.append(f"**{speaker}:** {text}\n")
            else:
                lines.append(f"{text}\n")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _format_timestamp(seconds: float) -> str:
    """Format seconds as SRT/VTT timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _export_transcript_srt(transcript: dict, output_path: Path) -> None:
    """Export transcript to SRT subtitle format."""
    lines = []
    for i, seg in enumerate(transcript.get("segments", []), 1):
        start = seg.get("start", 0)
        end = seg.get("end", start + 1)
        text = seg.get("text", "").strip()
        speaker = seg.get("speaker", "")

        if speaker:
            text = f"[{speaker}] {text}"

        lines.append(str(i))
        lines.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
        lines.append(text)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _export_transcript_vtt(transcript: dict, output_path: Path) -> None:
    """Export transcript to WebVTT subtitle format."""
    lines = ["WEBVTT", ""]
    for seg in transcript.get("segments", []):
        start = seg.get("start", 0)
        end = seg.get("end", start + 1)
        text = seg.get("text", "").strip()
        speaker = seg.get("speaker", "")

        if speaker:
            text = f"<v {speaker}>{text}"

        # VTT uses . instead of , for milliseconds
        start_ts = _format_timestamp(start).replace(",", ".")
        end_ts = _format_timestamp(end).replace(",", ".")

        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _format_timestamp_readable(seconds: float, video_url: Optional[str] = None) -> str:
    """Format seconds as readable timestamp, optionally as clickable link.

    Args:
        seconds: Time in seconds
        video_url: Optional YouTube URL to create deep link

    Returns:
        Formatted timestamp like [0:15] or [[0:15]](url&t=15s)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        ts_text = f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        ts_text = f"{minutes}:{secs:02d}"

    # Make clickable if YouTube URL available
    if video_url and ("youtube.com" in video_url or "youtu.be" in video_url):
        # Handle both watch?v=xxx and youtu.be/xxx formats
        if "?" in video_url:
            linked_url = f"{video_url}&t={int(seconds)}s"
        else:
            linked_url = f"{video_url}?t={int(seconds)}s"
        return f"[[{ts_text}]]({linked_url})"

    return f"[{ts_text}]"


def _format_transcript_as_markdown(transcript: dict, video_url: Optional[str] = None) -> str:
    """Format transcript as markdown with timestamps and speakers.

    Args:
        transcript: Transcript dict with segments
        video_url: Optional YouTube URL for clickable timestamps

    Returns:
        Markdown formatted transcript
    """
    lines = ["# Transcript\n"]
    for seg in transcript.get("segments", []):
        start = seg.get("start", 0)
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()

        timestamp = _format_timestamp_readable(start, video_url)
        if speaker:
            lines.append(f"**{timestamp} {speaker}:** {text}\n")
        else:
            lines.append(f"**{timestamp}** {text}\n")

    return "\n".join(lines)


@main.command(name="transcript")
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--format",
    "format_opt",
    default=None,
    help=f"Output format(s), comma-separated (default: {DEFAULT_TRANSCRIPT_FORMAT})",
)
@click.option(
    "--timestamps/--no-timestamps",
    "-t/-T",
    default=False,
    help="Include timestamps in txt/md output",
)
def export_transcript(path: Optional[Path], format_opt: Optional[str], timestamps: bool) -> None:
    """Export transcript to text and subtitle formats.

    \b
    Arguments:
      PATH    Episode directory (default: interactive selection)

    \b
    Formats:
      txt    Plain text transcript
      md     Markdown with speakers
      srt    SubRip subtitles (for video editing)
      vtt    WebVTT subtitles (for web players)

    \b
    Options:
      -t, --timestamps    Include timestamps in txt/md output (e.g., [1:23])
                          For YouTube videos, timestamps become clickable links

    \b
    Examples:
      podx export transcript ./ep/                       # Export to markdown
      podx export transcript ./ep/ -t                    # With timestamps
      podx export transcript ./ep/ --format srt,vtt      # Export subtitles
      podx export transcript ./ep/ --format txt -t       # Text with timestamps
    """
    # Track if we're in interactive mode (no PATH provided)
    interactive_mode = path is None

    # Interactive mode if no path provided
    if interactive_mode:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
                require="transcript",
                title="Select episode to export transcript",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)
            path = Path(selected["directory"])
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    if path is None:
        console.print("[red]Error:[/red] No path specified")
        sys.exit(ExitCode.USER_ERROR)

    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find transcript
    transcript_path = _find_transcript(episode_dir)
    if not transcript_path:
        console.print(f"[red]Error:[/red] No transcript.json found in {episode_dir}")
        console.print("[dim]Run 'podx transcribe' first[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    transcript = json.loads(transcript_path.read_text())

    # Load video_url from episode metadata (for clickable timestamps in markdown)
    video_url = None
    if timestamps:
        meta_path = episode_dir / "episode-meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                video_url = meta.get("video_url")
            except Exception:
                pass

    # Interactive prompts for format (only in interactive mode)
    if interactive_mode:
        if format_opt is not None:
            show_confirmation("Format", format_opt)
            format_str = format_opt
        else:
            format_str = prompt_with_help(
                help_text=get_export_formats_help("transcript"),
                prompt_label="Format",
                default=DEFAULT_TRANSCRIPT_FORMAT,
                validator=lambda f: validate_export_format(f, "transcript"),
                error_message="Invalid format. See list above for valid options.",
            )
    else:
        # Non-interactive: use default if not specified
        format_str = format_opt if format_opt is not None else DEFAULT_TRANSCRIPT_FORMAT

    # Parse formats
    formats = [f.strip().lower() for f in format_str.split(",")]
    exported = []

    for fmt in formats:
        output_path = episode_dir / f"transcript.{fmt}"

        if fmt == "txt":
            _export_transcript_txt(transcript, output_path, timestamps=timestamps)
        elif fmt == "md":
            _export_transcript_md(
                transcript, output_path, timestamps=timestamps, video_url=video_url
            )
        elif fmt == "srt":
            _export_transcript_srt(transcript, output_path)
        elif fmt == "vtt":
            _export_transcript_vtt(transcript, output_path)
        else:
            console.print(f"[yellow]Unknown format: {fmt}[/yellow]")
            continue

        exported.append(output_path.name)

    if exported:
        console.print(f"[green]✓ Exported:[/green] {', '.join(exported)}")
        sys.exit(ExitCode.SUCCESS)
    else:
        console.print("[red]No files exported[/red]")
        sys.exit(ExitCode.USER_ERROR)


@main.command(name="analysis")
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--format",
    "format_opt",
    default=None,
    help=f"Output format(s), comma-separated (default: {DEFAULT_ANALYSIS_FORMAT})",
)
@click.option(
    "--include-transcript",
    is_flag=True,
    help="Append cleaned transcript after analysis",
)
@click.option(
    "--template",
    default=None,
    help="Export a specific template's analysis (e.g. quote-miner)",
)
def export_analysis(
    path: Optional[Path],
    format_opt: Optional[str],
    include_transcript: bool,
    template: Optional[str],
) -> None:
    """Export analysis to document formats.

    \b
    Arguments:
      PATH    Episode directory (default: interactive selection)

    \b
    Formats:
      md     Markdown summary
      html   HTML document
      pdf    PDF document (requires pandoc)

    \b
    Options:
      --include-transcript    Append cleaned transcript after analysis

    \b
    Examples:
      podx export analysis ./ep/                        # Export to markdown
      podx export analysis ./ep/ --format html          # Export to HTML
      podx export analysis ./ep/ --format md,pdf        # Markdown and PDF
      podx export analysis ./ep/ --include-transcript   # Include transcript
    """
    # Track if we're in interactive mode (no PATH provided)
    interactive_mode = path is None

    # Interactive mode if no path provided
    if interactive_mode:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
                require="analyzed",
                title="Select episode to export analysis",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)
            path = Path(selected["directory"])
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    if path is None:
        console.print("[red]Error:[/red] No path specified")
        sys.exit(ExitCode.USER_ERROR)

    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Find analysis - prompt if multiple exist and no template specified
    analysis_path: Optional[Path] = None

    if template:
        # Explicit template requested
        analysis_path = _find_analysis(episode_dir, template=template)
    else:
        # Check for multiple analyses
        all_analyses = _find_all_analyses(episode_dir)

        if len(all_analyses) == 0:
            pass  # Will error below
        elif len(all_analyses) == 1:
            analysis_path = all_analyses[0]
        else:
            # Multiple analyses found - prompt user to select
            console.print(f"[cyan]Found {len(all_analyses)} analysis files:[/cyan]")
            for i, p in enumerate(all_analyses, 1):
                # Try to read template/model from the JSON for a better label
                try:
                    _meta = json.loads(p.read_text())
                    _tmpl = _meta.get("template", "")
                    _mdl = _meta.get("model", "")
                    if _tmpl and _mdl:
                        label = f"{_tmpl} ({_mdl})"
                    elif _tmpl:
                        label = _tmpl
                    elif p.name == "analysis.json":
                        label = "general (default)"
                    else:
                        parts = p.stem.split(".", 1)
                        label = parts[1] if len(parts) == 2 else p.name
                except Exception:
                    if p.name == "analysis.json":
                        label = "general (default)"
                    else:
                        parts = p.stem.split(".", 1)
                        label = parts[1] if len(parts) == 2 else p.name
                mtime = p.stat().st_mtime
                from datetime import datetime

                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                console.print(f"  [{i}] {label} [dim]({mtime_str})[/dim]")

            try:
                choice = console.input("\n[bold]Select analysis[/bold] [dim](1)[/dim]: ").strip()
                if not choice:
                    choice = "1"
                idx = int(choice) - 1
                if 0 <= idx < len(all_analyses):
                    analysis_path = all_analyses[idx]
                else:
                    console.print("[red]Invalid selection[/red]")
                    sys.exit(ExitCode.USER_ERROR)
            except (ValueError, KeyboardInterrupt):
                console.print("\n[dim]Cancelled[/dim]")
                sys.exit(0)

    if not analysis_path:
        console.print(f"[red]Error:[/red] No analysis.json found in {episode_dir}")
        console.print("[dim]Run 'podx analyze' first[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    analysis = json.loads(analysis_path.read_text())
    md_content = analysis.get("markdown", "")

    # Derive template from the analysis JSON if not explicitly provided
    if not template:
        template = analysis.get("template")
        if not template:
            # Fallback: parse from filename (legacy files without template field)
            if analysis_path.name != "analysis.json":
                parts = analysis_path.stem.split(".", 1)
                if len(parts) == 2:
                    template = parts[1]

    if not md_content:
        console.print("[red]Error:[/red] Analysis has no markdown content")
        sys.exit(ExitCode.USER_ERROR)

    # Load video_url from episode metadata (for clickable timestamps)
    video_url = None
    meta_path = episode_dir / "episode-meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            video_url = meta.get("video_url")
        except Exception:
            pass

    # Optionally append transcript
    transcript_md = None
    if include_transcript:
        transcript_path = _find_transcript(episode_dir)
        if transcript_path:
            transcript = json.loads(transcript_path.read_text())
            transcript_md = _format_transcript_as_markdown(transcript, video_url)
            md_content = md_content + "\n\n---\n\n" + transcript_md
        else:
            console.print("[yellow]Warning:[/yellow] No transcript.json found, skipping transcript")

    # Interactive prompts for format (only in interactive mode)
    if interactive_mode:
        if format_opt is not None:
            show_confirmation("Format", format_opt)
            format_str = format_opt
        else:
            format_str = prompt_with_help(
                help_text=get_export_formats_help("analysis"),
                prompt_label="Format",
                default=DEFAULT_ANALYSIS_FORMAT,
                validator=lambda f: validate_export_format(f, "analysis"),
                error_message="Invalid format. See list above for valid options.",
            )
    else:
        # Non-interactive: use default if not specified
        format_str = format_opt if format_opt is not None else DEFAULT_ANALYSIS_FORMAT

    # Parse formats
    formats = [f.strip().lower() for f in format_str.split(",")]
    exported = []

    for fmt in formats:
        # Template-specific output names
        if template and template != "general":
            output_path = episode_dir / f"analysis.{template}.{fmt}"
        else:
            output_path = episode_dir / f"analysis.{fmt}"

        if fmt == "md":
            output_path.write_text(md_content, encoding="utf-8")
            exported.append(output_path.name)

        elif fmt == "html":
            try:
                import markdown

                # For HTML, render analysis and transcript separately
                # so we can wrap transcript in collapsible <details>
                analysis_html = markdown.markdown(analysis.get("markdown", ""))

                transcript_html = ""
                if transcript_md:
                    transcript_body = markdown.markdown(transcript_md)
                    transcript_html = f"""
<hr>
<details>
  <summary><strong>📜 Full Transcript</strong> (click to expand)</summary>
  {transcript_body}
</details>"""

                html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Analysis</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
        h1, h2, h3 {{ color: #333; }}
        blockquote {{ border-left: 3px solid #ccc; padding-left: 1rem; color: #666; }}
        details {{ margin-top: 2rem; }}
        details summary {{ cursor: pointer; padding: 0.5rem; background: #f5f5f5; border-radius: 4px; }}
        details summary:hover {{ background: #e8e8e8; }}
    </style>
</head>
<body>
{analysis_html}
{transcript_html}
</body>
</html>"""
                output_path.write_text(html_doc, encoding="utf-8")
                exported.append(output_path.name)
            except ImportError:
                console.print("[yellow]HTML export requires 'markdown' package[/yellow]")

        elif fmt == "pdf":
            import subprocess

            # Use template-aware name for intermediate md file
            if template and template != "general":
                md_path = episode_dir / f"analysis.{template}.md"
            else:
                md_path = episode_dir / "analysis.md"
            md_path.write_text(md_content, encoding="utf-8")

            try:
                subprocess.run(
                    ["pandoc", str(md_path), "-o", str(output_path)],
                    check=True,
                    capture_output=True,
                )
                exported.append(output_path.name)
            except FileNotFoundError:
                console.print("[yellow]PDF export requires pandoc[/yellow]")
            except subprocess.CalledProcessError as e:
                console.print(f"[yellow]PDF export failed: {e}[/yellow]")

        else:
            console.print(f"[yellow]Unknown format: {fmt}[/yellow]")

    if exported:
        console.print(f"[green]✓ Exported:[/green] {', '.join(exported)}")
        sys.exit(ExitCode.SUCCESS)
    else:
        console.print("[red]No files exported[/red]")
        sys.exit(ExitCode.USER_ERROR)


@main.command(name="all")
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--timestamps/--no-timestamps",
    "-t/-T",
    default=False,
    help="Include timestamps in transcript txt/md output",
)
@click.option(
    "--include-transcript",
    is_flag=True,
    help="Append cleaned transcript after analysis",
)
def export_all(
    path: Optional[Path],
    timestamps: bool,
    include_transcript: bool,
) -> None:
    """Export both transcript and analysis in all available formats.

    \b
    Arguments:
      PATH    Episode directory (default: interactive selection)

    \b
    Exports:
      Transcript:  txt, md, srt, vtt
      Analysis:    md, html (pdf skipped unless pandoc installed)

    \b
    Examples:
      podx export all ./ep/                     # Export everything
      podx export all ./ep/ -t                  # With timestamps
      podx export all ./ep/ --include-transcript # Transcript in analysis
    """
    # Interactive mode if no path provided
    if path is None:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
                require="transcript",
                title="Select episode to export",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)
            path = Path(selected["directory"])
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    if path is None:
        console.print("[red]Error:[/red] No path specified")
        sys.exit(ExitCode.USER_ERROR)

    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    exported = []

    # --- Transcript exports ---
    transcript_path = _find_transcript(episode_dir)
    if transcript_path:
        transcript = json.loads(transcript_path.read_text())

        # Load video_url for clickable timestamps
        video_url = None
        if timestamps:
            meta_path = episode_dir / "episode-meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    video_url = meta.get("video_url")
                except Exception:
                    pass

        for fmt in ("txt", "md", "srt", "vtt"):
            output_path = episode_dir / f"transcript.{fmt}"
            if fmt == "txt":
                _export_transcript_txt(transcript, output_path, timestamps=timestamps)
            elif fmt == "md":
                _export_transcript_md(
                    transcript, output_path, timestamps=timestamps, video_url=video_url
                )
            elif fmt == "srt":
                _export_transcript_srt(transcript, output_path)
            elif fmt == "vtt":
                _export_transcript_vtt(transcript, output_path)
            exported.append(output_path.name)
    else:
        console.print("[yellow]Warning:[/yellow] No transcript found, skipping transcript exports")

    # --- Analysis exports ---
    all_analyses = _find_all_analyses(episode_dir)
    if all_analyses:
        for analysis_path in all_analyses:
            analysis = json.loads(analysis_path.read_text())
            md_content = analysis.get("markdown", "")
            if not md_content:
                continue

            template = analysis.get("template")

            # Optionally append transcript
            if include_transcript and transcript_path:
                transcript_for_append = json.loads(transcript_path.read_text())
                video_url_for_append = None
                meta_path = episode_dir / "episode-meta.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                        video_url_for_append = meta.get("video_url")
                    except Exception:
                        pass
                transcript_md = _format_transcript_as_markdown(
                    transcript_for_append, video_url_for_append
                )
                md_content = md_content + "\n\n---\n\n" + transcript_md

            # Build output name prefix
            if template and template != "general":
                name_prefix = f"analysis.{template}"
            else:
                name_prefix = "analysis"

            # Markdown
            md_path = episode_dir / f"{name_prefix}.md"
            md_path.write_text(md_content, encoding="utf-8")
            exported.append(md_path.name)

            # HTML
            try:
                import markdown

                analysis_html = markdown.markdown(analysis.get("markdown", ""))
                transcript_html = ""
                if include_transcript and transcript_path:
                    transcript_for_html = json.loads(transcript_path.read_text())
                    video_url_html = None
                    meta_path = episode_dir / "episode-meta.json"
                    if meta_path.exists():
                        try:
                            meta = json.loads(meta_path.read_text())
                            video_url_html = meta.get("video_url")
                        except Exception:
                            pass
                    transcript_body = markdown.markdown(
                        _format_transcript_as_markdown(transcript_for_html, video_url_html)
                    )
                    transcript_html = f"""
<hr>
<details>
  <summary><strong>Full Transcript</strong> (click to expand)</summary>
  {transcript_body}
</details>"""

                html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Analysis</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
        h1, h2, h3 {{ color: #333; }}
        blockquote {{ border-left: 3px solid #ccc; padding-left: 1rem; color: #666; }}
        details {{ margin-top: 2rem; }}
        details summary {{ cursor: pointer; padding: 0.5rem; background: #f5f5f5; border-radius: 4px; }}
        details summary:hover {{ background: #e8e8e8; }}
    </style>
</head>
<body>
{analysis_html}
{transcript_html}
</body>
</html>"""
                html_path = episode_dir / f"{name_prefix}.html"
                html_path.write_text(html_doc, encoding="utf-8")
                exported.append(html_path.name)
            except ImportError:
                pass  # Silently skip HTML if markdown package not installed
    else:
        console.print("[yellow]Warning:[/yellow] No analysis found, skipping analysis exports")

    if exported:
        console.print(f"[green]✓ Exported:[/green] {', '.join(exported)}")
        sys.exit(ExitCode.SUCCESS)
    else:
        console.print("[red]No files exported[/red]")
        sys.exit(ExitCode.USER_ERROR)


if __name__ == "__main__":
    main()
