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

    # Create/update page
    client = Client(auth=token)

    # Build properties
    properties = {
        "Name": {"title": [{"text": {"content": episode_title}}]},
    }

    # Add optional properties if they exist in the database
    # (Notion will ignore properties that don't exist)
    if show_name:
        properties["Podcast"] = {"rich_text": [{"text": {"content": show_name}}]}
    if date_iso:
        properties["Date"] = {"date": {"start": date_iso}}

    # Check if page exists (by title)
    try:
        query = client.databases.query(
            database_id=db_id,
            filter={"property": "Name", "title": {"equals": episode_title}},
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

        # Add new content
        client.blocks.children.append(block_id=page_id, children=blocks)

        page_url = f"https://notion.so/{page_id.replace('-', '')}"
        console.print(f"\n[green]✓ Updated existing page:[/green] {page_url}")
    else:
        # Create new page
        page = client.pages.create(
            parent={"database_id": db_id},
            properties=properties,
            children=blocks,
        )
        page_id = page["id"]
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
    Requirements:
      - Notion token configured
      - Notion database ID configured
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

    # Publish
    if _publish_to_notion(episode_dir, dry_run=dry_run):
        sys.exit(ExitCode.SUCCESS)
    else:
        sys.exit(ExitCode.PROCESSING_ERROR)


if __name__ == "__main__":
    main()
