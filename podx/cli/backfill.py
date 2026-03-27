"""CLI command for batch backfill and Notion publishing.

Walks episode directories, runs dual-template analysis (format + knowledge-oracle),
and upserts results to the Notion Podcast Knowledge Base.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from podx.batch.discovery import EpisodeDiscovery, EpisodeFilter
from podx.core.backfill import BackfillConfig, backfill_episode, find_transcript
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger

logger = get_logger(__name__)
console = Console()


def _get_existing_notion_episodes(db_id: str) -> set:
    """Get set of (episode_title, date) tuples already in Notion."""
    import os

    try:
        from notion_client import Client
    except ImportError:
        console.print("[red]Error:[/red] notion-client not installed")
        return set()

    token = os.getenv("NOTION_TOKEN")
    if not token:
        console.print("[red]Error:[/red] NOTION_TOKEN not set")
        return set()

    client = Client(auth=token)
    results = set()
    start_cursor = None

    while True:
        kwargs = {"database_id": db_id, "page_size": 100}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        resp = client.databases.query(**kwargs)
        for page in resp.get("results", []):
            props = page.get("properties", {})
            # Extract episode title
            episode_title = ""
            for pname, pval in props.items():
                ptype = pval.get("type")
                if ptype == "title":
                    title_items = pval.get("title", [])
                    if title_items:
                        episode_title = title_items[0].get("plain_text", "")
                elif pname.lower() == "episode" and ptype == "rich_text":
                    rt_items = pval.get("rich_text", [])
                    if rt_items:
                        episode_title = rt_items[0].get("plain_text", "")

            # Extract date
            date_str = ""
            for pname, pval in props.items():
                if pval.get("type") == "date" and pval.get("date"):
                    date_str = pval["date"].get("start", "")
                    break

            if episode_title:
                results.add((episode_title, date_str))

        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")

    return results


@click.command(context_settings={"max_content_width": 120})
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--dry-run", is_flag=True, help="Preview what would be processed without making changes"
)
@click.option("--model", default="gpt-5.1", show_default=True, help="LLM model for analysis")
@click.option("--show", "show_filter", default=None, help="Filter by show name (substring match)")
@click.option("--since", default=None, help="Only episodes after this date (YYYY-MM-DD)")
@click.option("--missing-from-notion", is_flag=True, help="Only episodes not yet in Notion")
@click.option(
    "--no-analysis", is_flag=True, help="Skip analysis, only publish existing files to Notion"
)
@click.option("--force", is_flag=True, help="Re-analyze even if template hash matches")
@click.option("--limit", default=None, type=int, help="Process at most N episodes")
@click.option("--no-notion", is_flag=True, help="Run analysis only, skip Notion publishing")
def main(
    path: Path,
    dry_run: bool,
    model: str,
    show_filter: Optional[str],
    since: Optional[str],
    missing_from_notion: bool,
    no_analysis: bool,
    force: bool,
    limit: Optional[int],
    no_notion: bool,
) -> None:
    """Batch re-analyze episodes and publish to Notion.

    Walks episode directories, runs format + knowledge-oracle analysis,
    and upserts results to the Notion Podcast Knowledge Base.

    \b
    Examples:
      podx backfill ~/podcasts/                        # Process all episodes
      podx backfill ~/podcasts/ --dry-run               # Preview only
      podx backfill ~/podcasts/ --show "Lex Fridman"    # Filter by show
      podx backfill ~/podcasts/ --since 2025-01-01      # Recent only
      podx backfill ~/podcasts/ --missing-from-notion   # Only new to Notion
      podx backfill ~/podcasts/ --no-analysis            # Publish existing only
      podx backfill ~/podcasts/ --force                  # Re-analyze everything
      podx backfill ~/podcasts/ --limit 5                # Cap at N episodes
    """
    # Discover episodes
    discovery = EpisodeDiscovery(base_dir=path)
    filters = EpisodeFilter(
        show=show_filter,
        since=since,
    )
    episodes = discovery.discover_episodes(auto_detect=True, filters=filters)

    if not episodes:
        console.print("[yellow]No episodes found[/yellow]")
        sys.exit(ExitCode.SUCCESS)

    # Filter to episodes that have transcripts
    episodes_with_transcripts = []
    for ep in episodes:
        ep_dir = Path(ep.get("directory", ep.get("path", "")))
        if ep_dir.is_dir() and find_transcript(ep_dir):
            episodes_with_transcripts.append(ep)
    episodes = episodes_with_transcripts

    if not episodes:
        console.print("[yellow]No episodes with transcripts found[/yellow]")
        sys.exit(ExitCode.SUCCESS)

    # Filter missing from Notion
    if missing_from_notion:
        console.print("[dim]Querying Notion for existing episodes...[/dim]")
        existing = _get_existing_notion_episodes(BackfillConfig.notion_db_id)
        console.print(f"[dim]Found {len(existing)} existing entries in Notion[/dim]")

        filtered = []
        for ep in episodes:
            ep_title = ep.get("episode_title", ep.get("title", ""))
            if not any(ep_title == t for t, _ in existing):
                filtered.append(ep)
        episodes = filtered

    # Apply limit
    if limit:
        episodes = episodes[:limit]

    if not episodes:
        console.print("[green]All episodes are up to date[/green]")
        sys.exit(ExitCode.SUCCESS)

    console.print(f"\n[bold]Backfill: {len(episodes)} episode(s)[/bold]")
    console.print(f"[dim]Model: {model} | Notion: {'skip' if no_notion else 'publish'}[/dim]\n")

    # Build config
    config = BackfillConfig(
        model=model,
        dry_run=dry_run,
        force_reanalyze=force,
        publish_to_notion=not no_notion and not no_analysis,
    )

    # Process episodes
    successes = 0
    failures = 0

    for i, ep in enumerate(episodes, 1):
        ep_dir = Path(ep.get("directory", ep.get("path", "")))
        show = ep.get("show", "Unknown")
        title = ep.get("episode_title", ep.get("title", ep_dir.name))

        prefix = f"[{i}/{len(episodes)}]"

        if dry_run:
            console.print(f"  {prefix} [cyan]{show}[/cyan] — {title}")
            successes += 1
            continue

        console.print(f"\n{prefix} [cyan]{show}[/cyan] — {title}")

        def progress(msg: str) -> None:
            console.print(f"  [dim]{msg}[/dim]")

        result = backfill_episode(ep_dir, config, progress_callback=progress)

        if result.success:
            successes += 1
            templates = ", ".join(result.templates_run) if result.templates_run else "none"
            console.print(f"  [green]Done[/green] (templates: {templates})")
        else:
            failures += 1
            console.print(f"  [red]Failed:[/red] {result.error}")

    # Summary
    console.print(f"\n[bold]{'Preview' if dry_run else 'Backfill'} complete:[/bold]")
    console.print(f"  [green]{successes} succeeded[/green]")
    if failures:
        console.print(f"  [red]{failures} failed[/red]")

    sys.exit(ExitCode.SUCCESS if failures == 0 else ExitCode.PROCESSING_ERROR)
