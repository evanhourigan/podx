"""CLI command for viewing processing history."""

import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from podx.core.history import get_history_manager
from podx.domain.exit_codes import ExitCode

console = Console()


@click.command()
@click.option("--show", "-s", default=None, help="Filter by show name (partial match)")
@click.option("--episode", "-e", default=None, help="Filter by episode (partial match)")
@click.option("--detailed", "-d", is_flag=True, help="Show detailed event history")
def main(show: Optional[str], episode: Optional[str], detailed: bool) -> None:
    """View processing history for episodes.

    \b
    Examples:
      podx history                          # All episodes
      podx history --show "Lenny"           # Filter by show
      podx history -s "Lex" -e "sam"        # Filter by show and episode
      podx history -s "Lenny" --detailed    # Detailed view
    """
    manager = get_history_manager()
    histories = manager.get_all(show_filter=show)

    if not histories:
        if show:
            console.print(f"[dim]No episodes found matching show '{show}'[/dim]")
        else:
            console.print("[dim]No processing history found.[/dim]")
            console.print("[dim]Run 'podx transcribe' on an episode to start tracking.[/dim]")
        sys.exit(ExitCode.SUCCESS)

    # Filter by episode name if specified
    if episode:
        ep_lower = episode.lower()
        histories = [
            h
            for h in histories
            if ep_lower in h.episode_title.lower() or ep_lower in h.episode_dir.lower()
        ]
        if not histories:
            console.print(f"[dim]No episodes found matching '{episode}'[/dim]")
            sys.exit(ExitCode.SUCCESS)

    if detailed or (episode and len(histories) == 1):
        # Detailed view for single episode or --detailed flag
        _show_detailed(histories)
    else:
        # Summary table
        _show_summary_table(histories)


def _show_summary_table(histories) -> None:
    """Show summary table of all episodes."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Show", max_width=25, no_wrap=True)
    table.add_column("Episode", max_width=30)
    table.add_column("Steps", max_width=35)
    table.add_column("Last Updated", width=16)

    for h in histories:
        # Format steps as arrow-separated
        steps = " -> ".join(h.steps_completed) if h.steps_completed else "[dim]none[/dim]"

        # Format timestamp
        last_updated = h.last_updated[:16].replace("T", " ") if h.last_updated else ""

        # Truncate episode title
        ep_title = h.episode_title
        if len(ep_title) > 28:
            ep_title = ep_title[:25] + "..."

        table.add_row(h.show, ep_title, steps, last_updated)

    console.print()
    console.print(table)
    console.print()


def _show_detailed(histories) -> None:
    """Show detailed history for episodes."""
    for h in histories:
        console.print()
        console.print(f"[bold]Episode:[/bold] {h.episode_title}")
        console.print(f"[bold]Show:[/bold] {h.show}")
        console.print(f"[bold]Path:[/bold] [dim]{h.episode_dir}[/dim]")
        console.print()
        console.print("[bold]Processing History:[/bold]")

        for event in sorted(h.events, key=lambda e: e.timestamp):
            timestamp = event.timestamp[:16].replace("T", " ")
            model_info = ""
            if event.model:
                model_info = f"  {event.model}"
            if event.template:
                model_info += f" ({event.template} template)"

            console.print(f"  [cyan]{event.step:12}[/cyan] {timestamp}{model_info}")

        console.print()


if __name__ == "__main__":
    main()
