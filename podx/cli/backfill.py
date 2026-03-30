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
@click.option(
    "--include-published",
    is_flag=True,
    help="Include episodes already in Notion (default: skip them)",
)
@click.option(
    "--no-analysis", is_flag=True, help="Skip analysis, only publish existing files to Notion"
)
@click.option("--force", is_flag=True, help="Re-analyze even if template hash matches")
@click.option("--limit", default=None, type=int, help="Process at most N episodes")
@click.option("--no-notion", is_flag=True, help="Run analysis only, skip Notion publishing")
@click.option(
    "--review",
    is_flag=True,
    help="Review each episode's template assignment before re-analyzing",
)
def main(
    path: Path,
    dry_run: bool,
    model: str,
    show_filter: Optional[str],
    since: Optional[str],
    include_published: bool,
    no_analysis: bool,
    force: bool,
    limit: Optional[int],
    no_notion: bool,
    review: bool,
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
      podx backfill ~/podcasts/ --include-published       # Re-process already-published episodes
      podx backfill ~/podcasts/ --no-analysis            # Publish existing only
      podx backfill ~/podcasts/ --force                  # Re-analyze everything
      podx backfill ~/podcasts/ --limit 5                # Cap at N episodes
      podx backfill ~/podcasts/ --review                  # Review/fix template per episode
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

    # Skip episodes already in Notion (default behavior)
    if not include_published and not no_notion:
        console.print("[dim]Checking Notion for already-published episodes...[/dim]")
        existing = _get_existing_notion_episodes(BackfillConfig.notion_db_id)
        console.print(f"[dim]Found {len(existing)} existing entries in Notion[/dim]")

        filtered = []
        for ep in episodes:
            ep_title = ep.get("episode_title", ep.get("title", ""))
            if not any(ep_title == t for t, _ in existing):
                filtered.append(ep)

        skipped = len(episodes) - len(filtered)
        if skipped:
            console.print(f"[dim]Skipping {skipped} already-published episodes[/dim]")
        episodes = filtered

    # Apply limit
    if limit:
        episodes = episodes[:limit]

    if not episodes:
        console.print("[green]All episodes are up to date[/green]")
        sys.exit(ExitCode.SUCCESS)

    console.print(f"\n[bold]Backfill: {len(episodes)} episode(s)[/bold]")
    console.print(f"[dim]Model: {model} | Notion: {'skip' if no_notion else 'publish'}[/dim]\n")

    # Review mode implies --include-published and --force
    if review:
        force = True

    # Build base config
    config = BackfillConfig(
        model=model,
        dry_run=dry_run,
        force_reanalyze=force,
        publish_to_notion=not no_notion and not no_analysis,
    )

    # Process episodes
    successes = 0
    failures = 0
    skipped = 0

    for i, ep in enumerate(episodes, 1):
        ep_dir = Path(ep.get("directory", ep.get("path", "")))
        show = ep.get("show", "Unknown")
        title = ep.get("episode_title", ep.get("title", ep_dir.name))

        prefix = f"[{i}/{len(episodes)}]"

        if dry_run and not review:
            console.print(f"  {prefix} [cyan]{show}[/cyan] — {title}")
            successes += 1
            continue

        console.print(f"\n{prefix} [cyan]{show}[/cyan] — {title}")

        # Review mode: show auto-detected template, let user confirm or change
        ep_config = config
        if review:
            template_choice = _review_template(ep_dir, ep)
            if template_choice is None:
                console.print("  [dim]Skipped[/dim]")
                skipped += 1
                continue
            # Create per-episode config with template override
            ep_config = BackfillConfig(
                model=config.model,
                dry_run=config.dry_run,
                force_reanalyze=True,
                notion_db_id=config.notion_db_id,
                publish_to_notion=config.publish_to_notion,
                format_template_override=template_choice,
            )

        def progress(msg: str) -> None:
            console.print(f"  [dim]{msg}[/dim]")

        result = backfill_episode(ep_dir, ep_config, progress_callback=progress)

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
    if skipped:
        console.print(f"  [dim]{skipped} skipped[/dim]")
    if failures:
        console.print(f"  [red]{failures} failed[/red]")

    sys.exit(ExitCode.SUCCESS if failures == 0 else ExitCode.PROCESSING_ERROR)


def _review_template(ep_dir: Path, ep: dict) -> Optional[str]:
    """Interactive template review for a single episode.

    Shows auto-detected template and lets user confirm, change, or skip.
    Returns template name, or None to skip this episode.
    """
    import json as json_module

    from podx.core.backfill import detect_format_template, find_transcript
    from podx.templates.manager import TemplateManager

    # Load transcript for auto-detection
    transcript_path = find_transcript(ep_dir)
    if not transcript_path:
        return None

    transcript = json_module.loads(transcript_path.read_text())

    episode_meta = {}
    meta_path = ep_dir / "episode-meta.json"
    if meta_path.exists():
        episode_meta = json_module.loads(meta_path.read_text())

    # Auto-detect
    detected = detect_format_template(transcript, episode_meta)

    # Count speakers for context
    speakers = set(s.get("speaker") for s in transcript.get("segments", []) if s.get("speaker"))

    console.print(f"  Speakers: {len(speakers)} | Auto-detected: [cyan]{detected}[/cyan]")

    manager = TemplateManager()
    valid_names = set(manager.list_templates())

    while True:
        try:
            choice = input(f"  Template (Enter={detected}, ?=list, s=skip): ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled[/dim]")
            raise SystemExit(0)

        if not choice:
            return detected

        if choice.lower() == "s":
            return None

        if choice == "?":
            for name in sorted(valid_names):
                tmpl = manager.load(name)
                desc = tmpl.description
                if "Format:" in desc:
                    desc = desc.split("Example podcasts:")[0].replace("Format:", "").strip()
                if len(desc) > 55:
                    desc = desc[:52] + "..."
                marker = " <--" if name == detected else ""
                console.print(f"    [cyan]{name:<24}[/cyan] {desc}{marker}")
            continue

        if choice in valid_names:
            return choice

        console.print(f"  [red]Unknown template '{choice}'. Type ? to list.[/red]")
