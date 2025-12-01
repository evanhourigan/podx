"""CLI wrapper for notion command.

Simplified v4.0 command for publishing to Notion.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.domain.exit_codes import ExitCode
from podx.ui import select_episode_interactive

console = Console()


def _find_analysis(directory: Path) -> Optional[Path]:
    """Find analysis file in episode directory."""
    # Check for analysis.json first (new standard name)
    analysis = directory / "analysis.json"
    if analysis.exists():
        return analysis

    # Fall back to legacy deepcast patterns
    patterns = ["deepcast-*.json", "deepcast.json"]
    for pattern in patterns:
        matches = list(directory.glob(pattern))
        if matches:
            return matches[0]

    return None


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


def _format_timestamp_readable(seconds: float) -> str:
    """Format seconds as readable timestamp [HH:MM:SS]."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"[{hours}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes}:{secs:02d}]"


def _format_transcript_as_markdown(transcript: dict) -> str:
    """Format transcript as markdown with timestamps and speakers."""
    lines = ["# Transcript\n"]
    for seg in transcript.get("segments", []):
        start = seg.get("start", 0)
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()

        timestamp = _format_timestamp_readable(start)
        if speaker:
            lines.append(f"**{timestamp} {speaker}:** {text}\n")
        else:
            lines.append(f"**{timestamp}** {text}\n")

    return "\n".join(lines)


def _publish_to_notion(episode_dir: Path, dry_run: bool = False) -> bool:
    """Publish episode analysis to Notion. Returns True on success."""
    try:
        from notion_client import Client
    except ImportError:
        console.print("[red]Error:[/red] notion-client not installed")
        console.print("[dim]Install with: pip install notion-client[/dim]")
        return False

    # Get token
    token = os.getenv("NOTION_TOKEN")
    if not token:
        console.print("[red]Error:[/red] NOTION_TOKEN not set")
        console.print("[dim]Run 'podx config set notion-token YOUR_TOKEN'[/dim]")
        return False

    # Get database ID
    db_id = os.getenv("NOTION_DATABASE_ID")
    if not db_id:
        console.print("[red]Error:[/red] NOTION_DATABASE_ID not set")
        console.print("[dim]Run 'podx config set notion-database-id YOUR_DB_ID'[/dim]")
        return False

    # Find analysis
    analysis_path = _find_analysis(episode_dir)
    if not analysis_path:
        console.print(f"[red]Error:[/red] No analysis.json found in {episode_dir}")
        console.print("[dim]Run 'podx analyze' first[/dim]")
        return False

    # Load analysis
    analysis = json.loads(analysis_path.read_text())
    md = analysis.get("markdown", "")
    if not md:
        console.print("[red]Error:[/red] Analysis has no markdown content")
        return False

    # Always append transcript if available
    transcript_path = _find_transcript(episode_dir)
    if transcript_path:
        try:
            transcript = json.loads(transcript_path.read_text())
            transcript_md = _format_transcript_as_markdown(transcript)
            md = md + "\n\n---\n\n" + transcript_md
        except Exception:
            pass  # Continue without transcript on error

    # Load episode metadata
    meta_path = episode_dir / "episode-meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    else:
        meta = {}

    # Extract info
    show_name = meta.get("show", "Unknown Podcast")
    episode_title = meta.get("episode_title", meta.get("title", "Untitled"))
    episode_date = meta.get("episode_published", meta.get("date", ""))

    # Parse date
    date_iso = None
    if episode_date:
        try:
            from dateutil import parser as dtparse

            parsed = dtparse.parse(episode_date)
            date_iso = parsed.strftime("%Y-%m-%d")
        except Exception:
            if len(episode_date) >= 10:
                date_iso = episode_date[:10]

    if dry_run:
        console.print("\n[bold]Dry run - would publish:[/bold]")
        console.print(f"  Database: {db_id[:8]}...")
        console.print(f"  Show: {show_name}")
        console.print(f"  Episode: {episode_title}")
        console.print(f"  Date: {date_iso or 'None'}")
        console.print(f"  Content: {len(md)} characters")
        return True

    # Convert markdown to Notion blocks
    from podx.core.notion import md_to_blocks

    blocks = md_to_blocks(md)

    # Notion API limits blocks to 100 per request
    NOTION_BLOCK_LIMIT = 100

    def append_blocks_chunked(client, block_id: str, blocks: list):
        """Append blocks in chunks of 100 (Notion API limit)."""
        for i in range(0, len(blocks), NOTION_BLOCK_LIMIT):
            chunk = blocks[i : i + NOTION_BLOCK_LIMIT]
            client.blocks.children.append(block_id=block_id, children=chunk)

    # Create/update page
    client = Client(auth=token)

    # Query database schema to find the title property
    try:
        db_info = client.databases.retrieve(database_id=db_id)
        db_properties = db_info.get("properties", {})
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to retrieve database schema: {e}")
        return False

    # Find the title property name (there's always exactly one title property)
    title_prop_name = None
    for prop_name, prop_info in db_properties.items():
        if prop_info.get("type") == "title":
            title_prop_name = prop_name
            break

    if not title_prop_name:
        console.print("[red]Error:[/red] Could not find title property in database")
        return False

    # Build properties - use discovered title property
    properties = {
        title_prop_name: {"title": [{"text": {"content": episode_title}}]},
    }

    # Add optional properties if they exist in the database
    for prop_name, prop_info in db_properties.items():
        prop_type = prop_info.get("type")

        # Add show name to a rich_text property named "Show" or similar
        if prop_type == "rich_text" and prop_name.lower() in ("show", "podcast name"):
            if show_name:
                properties[prop_name] = {
                    "rich_text": [{"text": {"content": show_name}}]
                }

        # Add date to a date property
        if prop_type == "date" and prop_name.lower() in (
            "date",
            "published",
            "episode date",
        ):
            if date_iso:
                properties[prop_name] = {"date": {"start": date_iso}}

    # Check if page exists (by title)
    try:
        query = client.databases.query(
            database_id=db_id,
            filter={"property": title_prop_name, "title": {"equals": episode_title}},
        )
        existing = query.get("results", [])
    except Exception:
        existing = []

    if existing:
        # Update existing page
        page_id = existing[0]["id"]

        # Clear existing content
        try:
            existing_blocks = client.blocks.children.list(block_id=page_id)
            for block in existing_blocks.get("results", []):
                try:
                    client.blocks.delete(block_id=block["id"])
                except Exception:
                    pass
        except Exception:
            pass

        # Add new content (chunked to respect 100 block limit)
        append_blocks_chunked(client, page_id, blocks)

        page_url = f"https://notion.so/{page_id.replace('-', '')}"
        console.print(f"\n[green]✓ Updated existing page:[/green] {page_url}")
    else:
        # Create new page with first chunk of blocks
        first_chunk = blocks[:NOTION_BLOCK_LIMIT]
        page = client.pages.create(
            parent={"database_id": db_id},
            properties=properties,
            children=first_chunk,
        )
        page_id = page["id"]

        # Append remaining blocks if any
        if len(blocks) > NOTION_BLOCK_LIMIT:
            remaining = blocks[NOTION_BLOCK_LIMIT:]
            append_blocks_chunked(client, page_id, remaining)

        page_url = f"https://notion.so/{page_id.replace('-', '')}"
        console.print(f"\n[green]✓ Created new page:[/green] {page_url}")

    return True


@click.command(context_settings={"max_content_width": 120})
@click.argument(
    "path",
    type=click.Path(exists=True, path_type=Path),
    required=False,
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be published without uploading"
)
def main(path: Optional[Path], dry_run: bool):
    """Publish episode analysis to Notion.

    \b
    Arguments:
      PATH    Episode directory (default: interactive selection)

    \b
    Configuration (via 'podx config'):
      notion-token         Notion API token (or NOTION_TOKEN env var)
      notion-database-id   Target database ID (or NOTION_DATABASE_ID env var)

    \b
    Notes:
      - Notion token must be configured
      - Notion database ID must be configured
      - Episode must have analysis.json (run 'podx analyze' first)

    \b
    Examples:
      podx notion                              # Interactive selection
      podx notion ./Show/2024-11-24-ep/        # Direct path
      podx notion ./ep/ --dry-run              # Preview without uploading
    """
    # Interactive mode if no path provided
    if path is None:
        try:
            selected, _ = select_episode_interactive(
                scan_dir=".",
                show_filter=None,
                require="analyzed",
                title="Select episode to publish to Notion",
            )
            if not selected:
                console.print("[dim]Selection cancelled[/dim]")
                sys.exit(0)

            path = selected["directory"]
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            sys.exit(0)

    # Resolve path
    episode_dir = path.resolve()
    if episode_dir.is_file():
        episode_dir = episode_dir.parent

    # Show what we're doing
    console.print(f"[cyan]Publishing:[/cyan] {episode_dir.name}")
    if dry_run:
        console.print("[cyan]Dry run:[/cyan] yes")

    # Publish
    if _publish_to_notion(episode_dir, dry_run=dry_run):
        sys.exit(ExitCode.SUCCESS)
    else:
        sys.exit(ExitCode.PROCESSING_ERROR)


if __name__ == "__main__":
    main()
