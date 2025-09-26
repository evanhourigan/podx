#!/usr/bin/env python3
"""
podx-info: Display episode information and processing status.
Shows what files exist, which models have been used, and processing history.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .fetch import find_feed_for_show
from .youtube import get_youtube_metadata, is_youtube_url


def get_episode_workdir(show: str, date: str) -> Path:
    """Get the working directory for an episode."""
    return Path(show) / date


def scan_episode_files(workdir: Path) -> Dict[str, any]:
    """Scan an episode directory and return information about existing files."""
    if not workdir.exists():
        return {"exists": False}

    info = {
        "exists": True,
        "workdir": str(workdir),
        "files": {},
        "deepcast_analyses": [],
        "metadata": {},
    }

    # Check for core files
    files_to_check = [
        ("episode-meta.json", "Episode metadata"),
        ("audio-meta.json", "Audio metadata"),
        ("transcript.json", "Transcript"),
        ("aligned-transcript.json", "Aligned transcript"),
        ("latest.json", "Latest processed transcript"),
        ("latest.txt", "Text export"),
        ("latest.srt", "SRT subtitles"),
        ("notion.out.json", "Notion upload result"),
    ]

    for filename, description in files_to_check:
        file_path = workdir / filename
        if file_path.exists():
            stat = file_path.stat()
            file_info = {
                "description": description,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "exists": True,
            }

            # Load transcript metadata for ASR model info
            if filename == "transcript.json":
                try:
                    transcript_data = json.loads(file_path.read_text())
                    file_info["asr_model"] = transcript_data.get("asr_model")
                    file_info["language"] = transcript_data.get("language")
                except (json.JSONDecodeError, FileNotFoundError):
                    pass

            info["files"][filename] = file_info
        else:
            info["files"][filename] = {"exists": False}

    # Load episode metadata if available
    episode_meta_file = workdir / "episode-meta.json"
    if episode_meta_file.exists():
        try:
            info["metadata"] = json.loads(episode_meta_file.read_text())
        except json.JSONDecodeError:
            pass

    # Scan for deepcast analyses
    deepcast_files = list(workdir.glob("deepcast-brief-*.json"))
    for file_path in deepcast_files:
        model_name = file_path.stem.replace("deepcast-brief-", "")
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                metadata = data.get("deepcast_metadata", {})
                info["deepcast_analyses"].append(
                    {
                        "model": model_name,
                        "file": str(file_path),
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime,
                        "metadata": metadata,
                        "has_markdown": (
                            workdir / f"deepcast-brief-{model_name}.md"
                        ).exists(),
                    }
                )
        except (json.JSONDecodeError, FileNotFoundError):
            # Handle corrupted or missing files
            info["deepcast_analyses"].append(
                {
                    "model": model_name,
                    "file": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                    "metadata": {},
                    "error": "Could not read file",
                    "has_markdown": False,
                }
            )

    # Sort by modification time (newest first)
    info["deepcast_analyses"].sort(key=lambda x: x.get("modified", 0), reverse=True)

    return info


def format_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def format_timestamp(timestamp: float) -> str:
    """Format timestamp as human readable date."""
    from datetime import datetime

    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def display_episode_info(info: Dict, show_files: bool = True) -> None:
    """Display episode information in a formatted way."""
    console = Console()

    if not info["exists"]:
        console.print(
            f"❌ Episode directory does not exist: [red]{info.get('workdir', 'unknown')}[/red]"
        )
        return

    # Episode metadata panel
    metadata = info["metadata"]
    if metadata:
        title = metadata.get("episode_title", "Unknown Episode")
        show_name = metadata.get("show", "Unknown Show")
        date = metadata.get("episode_published", "Unknown Date")

        meta_text = f"[bold cyan]{show_name}[/bold cyan]\n"
        meta_text += f"[white]{title}[/white]\n"
        meta_text += f"[dim]Published: {date}[/dim]"

        if "video_url" in metadata:
            meta_text += f"\n[dim]Source: YouTube ({metadata['video_id']})[/dim]"

        console.print(
            Panel(meta_text, title="📝 Episode Information", border_style="blue")
        )

    # Processing status
    files = info["files"]
    status_items = []

    transcript_file = files.get("transcript.json", {})
    if transcript_file.get("exists"):
        asr_model = transcript_file.get("asr_model", "unknown")
        language = transcript_file.get("language", "unknown")
        status_items.append(
            f"[green]✅ Transcribed[/green] [dim]({asr_model}, {language})[/dim]"
        )
    else:
        status_items.append("[red]❌ Not transcribed[/red]")

    if files.get("aligned-transcript.json", {}).get("exists"):
        status_items.append("[green]✅ Aligned[/green]")
    else:
        status_items.append("[dim]⚪ Not aligned[/dim]")

    if info["deepcast_analyses"]:
        status_items.append(
            f"[green]✅ Analyzed ({len(info['deepcast_analyses'])} models)[/green]"
        )
    else:
        status_items.append("[red]❌ Not analyzed[/red]")

    if files.get("notion.out.json", {}).get("exists"):
        status_items.append("[green]✅ Uploaded to Notion[/green]")
    else:
        status_items.append("[dim]⚪ Not uploaded[/dim]")

    console.print(
        Panel(
            " | ".join(status_items), title="🔄 Processing Status", border_style="green"
        )
    )

    # Deepcast analyses
    if info["deepcast_analyses"]:
        table = Table(title="🤖 AI Analyses")
        table.add_column("Model", style="cyan", no_wrap=True)
        table.add_column("Date", style="white")
        table.add_column("Size", style="yellow")
        table.add_column("Markdown", style="green")
        table.add_column("Temperature", style="blue")

        for analysis in info["deepcast_analyses"]:
            model = analysis["model"].replace("_", ".")
            date = format_timestamp(analysis["modified"])
            size = format_size(analysis["size"])
            markdown = "✅" if analysis["has_markdown"] else "❌"
            temp = str(analysis["metadata"].get("temperature", "Unknown"))

            table.add_row(model, date, size, markdown, temp)

        console.print(table)

    # Files overview
    if show_files:
        table = Table(title="📁 Files")
        table.add_column("File", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Status", style="green")
        table.add_column("Size", style="yellow")

        for filename, file_info in files.items():
            if file_info["exists"]:
                status = "✅ Exists"
                size = format_size(file_info["size"])
            else:
                status = "❌ Missing"
                size = "-"

            table.add_row(filename, file_info.get("description", ""), status, size)

        console.print(table)


def list_all_episodes(show: str) -> None:
    """List all episodes for a show with their processing status."""
    console = Console()
    show_dir = Path(show)

    if not show_dir.exists():
        console.print(f"❌ No episodes found for show: [red]{show}[/red]")
        return

    # Find all episode directories (assuming YYYY-MM-DD format)
    episode_dirs = [d for d in show_dir.iterdir() if d.is_dir() and len(d.name) == 10]
    episode_dirs.sort(reverse=True)  # Newest first

    if not episode_dirs:
        console.print(f"❌ No episode directories found in: [red]{show_dir}[/red]")
        return

    table = Table(title=f"🎙️ {show} - All Episodes")
    table.add_column("Date", style="cyan", no_wrap=True)
    table.add_column("Episode", style="white")
    table.add_column("Transcribed", style="green")
    table.add_column("Aligned", style="blue")
    table.add_column("Analyzed", style="yellow")
    table.add_column("Notion", style="magenta")

    for episode_dir in episode_dirs:
        info = scan_episode_files(episode_dir)

        # Get episode title from metadata
        title = "Unknown Episode"
        if info["metadata"]:
            title = info["metadata"].get("episode_title", "Unknown Episode")
            if len(title) > 50:
                title = title[:47] + "..."

        # Status indicators
        transcribed = (
            "✅" if info["files"].get("transcript.json", {}).get("exists") else "❌"
        )
        aligned = (
            "✅"
            if info["files"].get("aligned-transcript.json", {}).get("exists")
            else "⚪"
        )
        analyzed = (
            f"✅ ({len(info['deepcast_analyses'])})"
            if info["deepcast_analyses"]
            else "❌"
        )
        notion = (
            "✅" if info["files"].get("notion.out.json", {}).get("exists") else "⚪"
        )

        table.add_row(episode_dir.name, title, transcribed, aligned, analyzed, notion)

    console.print(table)


@click.command()
@click.option("--show", help="Podcast show name")
@click.option("--date", help="Episode date (YYYY-MM-DD)")
@click.option("--youtube-url", help="YouTube video URL")
@click.option("--files", is_flag=True, help="Show detailed file information")
@click.option(
    "--workdir", type=click.Path(path_type=Path), help="Override working directory"
)
def main(
    show: Optional[str],
    date: Optional[str],
    youtube_url: Optional[str],
    files: bool,
    workdir: Optional[Path],
):
    """
    Display episode information and processing status.

    Examples:
      podx-info --show "Lenny's Podcast"                    # List all episodes
      podx-info --show "Lenny's Podcast" --date 2025-08-17  # Specific episode
      podx-info --youtube-url "https://youtube.com/..."     # YouTube episode
      podx-info --workdir "./episode"                       # Custom directory
    """

    if workdir:
        # Direct directory inspection
        info = scan_episode_files(workdir)
        display_episode_info(info, show_files=files)

    elif youtube_url:
        # YouTube episode
        if not is_youtube_url(youtube_url):
            click.echo(f"❌ Invalid YouTube URL: {youtube_url}")
            return

        try:
            # Get YouTube metadata to determine workdir
            metadata = get_youtube_metadata(youtube_url)
            show_name = metadata["channel"]
            upload_date = metadata.get("upload_date", "")

            if upload_date and len(upload_date) == 8:  # YYYYMMDD
                formatted_date = (
                    f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                )
                workdir = get_episode_workdir(show_name, formatted_date)
                info = scan_episode_files(workdir)
                display_episode_info(info, show_files=files)
            else:
                click.echo(f"❌ Could not determine episode date from YouTube metadata")

        except Exception as e:
            click.echo(f"❌ Error processing YouTube URL: {e}")

    elif show and date:
        # Specific episode
        workdir = get_episode_workdir(show, date)
        info = scan_episode_files(workdir)
        display_episode_info(info, show_files=files)

    elif show:
        # List all episodes for the show
        list_all_episodes(show)

    else:
        click.echo("❌ Please provide either --show, --youtube-url, or --workdir")
        click.echo("Use --help for usage examples")


if __name__ == "__main__":
    main()
