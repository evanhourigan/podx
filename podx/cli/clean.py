"""CLI command for disk cleanup of episode directories.

Removes intermediate files after verified Notion publish,
keeping only episode-meta.json, transcript.json, and speaker-map.json.
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from podx.core.backfill import NOTION_DB_ID
from podx.core.disk_cleanup import (
    CleanupPlan,
    execute_cleanup,
    format_bytes,
    plan_cleanup,
    verify_notion_publish,
)
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger

logger = get_logger(__name__)
console = Console()


def _show_plan(plan: CleanupPlan) -> None:
    """Display a cleanup plan."""
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Tier", style="cyan", width=8)
    table.add_column("Files", style="white")
    table.add_column("Size", style="yellow", justify="right")

    if plan.tier1_files:
        names = ", ".join(f.name for f in plan.tier1_files[:5])
        if len(plan.tier1_files) > 5:
            names += f" (+{len(plan.tier1_files) - 5} more)"
        table.add_row("Tier 1", names, format_bytes(plan.total_bytes_tier1))

    if plan.tier2_files:
        names = ", ".join(f.name for f in plan.tier2_files)
        table.add_row("Tier 2", names, format_bytes(plan.total_bytes_tier2))

    if plan.tier3_files:
        names = ", ".join(f.name for f in plan.tier3_files)
        table.add_row("Keep", names, "[dim]kept[/dim]")

    console.print(table)

    total = plan.total_bytes_tier1 + plan.total_bytes_tier2
    console.print(f"\n  [bold]Total freeable:[/bold] {format_bytes(total)}")
    if plan.notion_verified:
        console.print("  [green]Notion publish verified[/green]")
    else:
        console.print("  [yellow]Notion publish NOT verified[/yellow]")


@click.command(context_settings={"max_content_width": 120})
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--all-episodes", is_flag=True, help="Clean all episode directories recursively")
@click.option("--keep-audio", is_flag=True, help="Preserve original audio files (skip Tier 2)")
@click.option("--force", is_flag=True, help="Skip Notion verification and confirmation prompts")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting")
def main(
    path: Path,
    all_episodes: bool,
    keep_audio: bool,
    force: bool,
    dry_run: bool,
) -> None:
    """Clean up episode directories after Notion publish.

    Removes intermediate files (WAV, analysis JSONs, exports) while
    preserving episode-meta.json, transcript.json, and speaker-map.json.

    \b
    Tiers:
      Tier 1 (always): audio.wav, analysis files, SRT/VTT exports
      Tier 2 (confirm): original audio (MP3, M4A)
      Tier 3 (never):  episode-meta.json, transcript.json, speaker-map.json

    \b
    Examples:
      podx clean ./episode/                    # Clean single episode
      podx clean ./podcasts/ --all-episodes    # Clean all episodes
      podx clean ./episode/ --dry-run          # Preview what would be deleted
      podx clean ./episode/ --keep-audio       # Keep original audio
      podx clean ./episode/ --force            # Skip verification
    """
    # Find episode directories
    if all_episodes:
        episode_dirs = [d.parent for d in path.rglob("episode-meta.json") if d.parent.is_dir()]
    elif (path / "episode-meta.json").exists():
        episode_dirs = [path]
    else:
        console.print(f"[red]Error:[/red] No episode-meta.json found in {path}")
        console.print("[dim]Use --all-episodes to scan recursively[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    if not episode_dirs:
        console.print("[yellow]No episode directories found[/yellow]")
        sys.exit(ExitCode.SUCCESS)

    console.print(f"\n[bold]Cleanup: {len(episode_dirs)} episode(s)[/bold]\n")

    total_files = 0
    total_bytes = 0

    for ep_dir in sorted(episode_dirs):
        plan = plan_cleanup(ep_dir)

        if not plan.tier1_files and not plan.tier2_files:
            continue

        # Verify Notion publish
        if not force:
            plan.notion_verified = verify_notion_publish(ep_dir, NOTION_DB_ID)

        show = ep_dir.parent.name
        episode = ep_dir.name
        console.print(f"[cyan]{show}[/cyan] / {episode}")

        if dry_run:
            _show_plan(plan)
            console.print()
            continue

        # Check Notion verification
        if not force and not plan.notion_verified:
            console.print("  [yellow]Skipped:[/yellow] Notion publish not verified")
            console.print("  [dim]Run 'podx backfill' first, or use --force[/dim]")
            continue

        # Confirm tier 2 deletion
        include_tier2 = not keep_audio
        if include_tier2 and plan.tier2_files and not force:
            audio_names = ", ".join(f.name for f in plan.tier2_files)
            audio_size = format_bytes(plan.total_bytes_tier2)
            try:
                confirm = (
                    input(f"  Delete original audio ({audio_names}, {audio_size})? [y/N]: ")
                    .strip()
                    .lower()
                )
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Cancelled[/dim]")
                sys.exit(0)
            include_tier2 = confirm in ("y", "yes")

        # Execute
        try:
            files, freed = execute_cleanup(
                plan,
                include_tier2=include_tier2,
                require_notion_verification=not force,
            )
            total_files += files
            total_bytes += freed
            console.print(f"  [green]Cleaned {files} files ({format_bytes(freed)})[/green]")
        except RuntimeError as e:
            console.print(f"  [red]Error:[/red] {e}")

    if not dry_run:
        console.print(
            f"\n[bold]Total:[/bold] {total_files} files, {format_bytes(total_bytes)} freed"
        )

    sys.exit(ExitCode.SUCCESS)
