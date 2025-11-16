#!/usr/bin/env python3
"""CLI commands for transcript search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from podx.domain.models.transcript import Transcript
from podx.search import TranscriptDatabase

console = Console()


@click.group()
def search_group() -> None:
    """Search and analyze transcripts."""
    pass


@search_group.command(name="index")
@click.argument("transcript_path", type=click.Path(exists=True))
@click.option("--episode-id", required=True, help="Unique episode identifier")
@click.option("--title", help="Episode title")
@click.option("--show", help="Show name")
@click.option("--date", help="Episode date")
def index_transcript(
    transcript_path: str,
    episode_id: str,
    title: Optional[str],
    show: Optional[str],
    date: Optional[str],
) -> None:
    """Index a transcript for searching.

    Examples:
        # Index a transcript
        podx-search index transcript.json --episode-id ep001 --title "Episode 1"

        # With full metadata
        podx-search index transcript.json --episode-id ep001 \\
            --title "AI Safety" --show "Lex Fridman" --date 2024-01-15
    """
    # Load transcript
    transcript = Transcript.from_file(Path(transcript_path))

    # Build metadata
    metadata = {}
    if title:
        metadata["title"] = title
    if show:
        metadata["show_name"] = show
    if date:
        metadata["date"] = date

    # Index in database
    db = TranscriptDatabase()
    db.index_transcript(episode_id, transcript, metadata)

    console.print(f"[green]✓ Indexed {len(transcript.segments)} segments[/green]")
    console.print(f"[dim]Episode ID: {episode_id}[/dim]")

    # Try semantic indexing if available
    try:
        from podx.search.semantic import SemanticSearch

        semantic = SemanticSearch()
        semantic.index_transcript(episode_id, transcript, metadata)
        console.print("[green]✓ Semantic index updated[/green]")
    except ImportError:
        console.print(
            "[yellow]! Semantic search not available "
            "(install: pip install sentence-transformers faiss-cpu)[/yellow]"
        )


@search_group.command(name="query")
@click.argument("query")
@click.option("--limit", default=10, help="Maximum results")
@click.option("--episode", help="Filter by episode ID")
@click.option("--speaker", help="Filter by speaker name")
@click.option("--semantic", is_flag=True, help="Use semantic search")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def search_query(
    query: str,
    limit: int,
    episode: Optional[str],
    speaker: Optional[str],
    semantic: bool,
    json_output: bool,
) -> None:
    """Search transcripts.

    Examples:
        # Keyword search
        podx-search query "artificial intelligence"

        # Semantic search
        podx-search query "dangers of AI" --semantic

        # Filter by episode and speaker
        podx-search query "quantum computing" --episode ep001 --speaker "Alice"

        # JSON output
        podx-search query "machine learning" --json-output
    """
    if semantic:
        try:
            from podx.search.semantic import SemanticSearch

            search_engine = SemanticSearch()
            results = search_engine.search(
                query, k=limit, episode_filter=episode, speaker_filter=speaker
            )

            if json_output:
                console.print(json.dumps(results, indent=2))
            else:
                _display_semantic_results(results, query)

        except ImportError:
            console.print(
                "[red]Semantic search requires: "
                "pip install sentence-transformers faiss-cpu[/red]"
            )
            return
    else:
        db = TranscriptDatabase()
        results = db.search(
            query, limit=limit, episode_filter=episode, speaker_filter=speaker
        )

        if json_output:
            console.print(json.dumps(results, indent=2))
        else:
            _display_search_results(results, query)


@search_group.command(name="list")
@click.option("--show", help="Filter by show name")
@click.option("--limit", default=20, help="Maximum episodes to list")
def list_episodes(show: Optional[str], limit: int) -> None:
    """List indexed episodes.

    Examples:
        # List all episodes
        podx-search list

        # Filter by show
        podx-search list --show "Lex Fridman"
    """
    db = TranscriptDatabase()
    episodes = db.list_episodes(show_filter=show, limit=limit)

    if not episodes:
        console.print("[yellow]No indexed episodes found[/yellow]")
        return

    table = Table(title="Indexed Episodes")
    table.add_column("Episode ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Show", style="magenta")
    table.add_column("Date", style="green")

    for ep in episodes:
        table.add_row(
            ep["episode_id"],
            ep.get("title", ""),
            ep.get("show_name", ""),
            ep.get("date", ""),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(episodes)} episodes[/dim]")


@search_group.command(name="quotes")
@click.argument("episode_id")
@click.option("--max-quotes", default=10, help="Maximum quotes to extract")
@click.option("--speaker", help="Filter by speaker")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def extract_quotes(
    episode_id: str, max_quotes: int, speaker: Optional[str], json_output: bool
) -> None:
    """Extract notable quotes from an episode.

    Examples:
        # Extract top 10 quotes
        podx-search quotes ep001

        # Filter by speaker
        podx-search quotes ep001 --speaker "Alice"

        # Get more quotes
        podx-search quotes ep001 --max-quotes 20
    """
    # Get episode from database
    db = TranscriptDatabase()
    episode_info = db.get_episode_info(episode_id)

    if not episode_info:
        console.print(f"[red]Episode not found: {episode_id}[/red]")
        return

    # Load transcript (need to reconstruct from segments)
    # For now, just show error - proper implementation would cache transcript path
    console.print(
        "[yellow]Quote extraction from indexed episodes coming soon![/yellow]"
    )
    console.print(
        "[dim]Tip: Use podx-search quotes on a transcript file directly[/dim]"
    )


@search_group.command(name="stats")
def show_stats() -> None:
    """Show search index statistics.

    Examples:
        podx-search stats
    """
    db = TranscriptDatabase()
    stats = db.get_stats()

    console.print("\n[bold cyan]Search Index Statistics[/bold cyan]\n")
    console.print(f"  Episodes: {stats['episodes']}")
    console.print(f"  Segments: {stats['segments']}")
    console.print(f"  Shows: {stats['shows']}")

    # Semantic index stats
    try:
        from podx.search.semantic import SemanticSearch

        semantic = SemanticSearch()
        sem_stats = semantic.get_stats()

        console.print("\n[bold cyan]Semantic Index[/bold cyan]\n")
        console.print(f"  Model: {sem_stats['model']}")
        console.print(f"  Indexed segments: {sem_stats['indexed_segments']}")
        console.print(f"  Embedding dimension: {sem_stats['embedding_dim']}")
    except ImportError:
        console.print(
            "\n[yellow]Semantic search not available[/yellow]"
            "\n[dim]Install: pip install sentence-transformers faiss-cpu[/dim]"
        )

    console.print()


def _display_search_results(results: list, query: str) -> None:
    """Display keyword search results."""
    if not results:
        console.print(f"[yellow]No results found for '{query}'[/yellow]")
        return

    console.print(f"\n[bold]Search results for '{query}'[/bold]\n")

    for i, result in enumerate(results, 1):
        console.print(
            f"[cyan]{i}. [{result['episode_id']}] {result.get('title', '')}[/cyan]"
        )
        console.print(f"   {result['speaker']} @ {result['timestamp']:.1f}s")
        console.print(f"   {result['text'][:150]}...")
        console.print()


def _display_semantic_results(results: list, query: str) -> None:
    """Display semantic search results."""
    if not results:
        console.print(f"[yellow]No results found for '{query}'[/yellow]")
        return

    console.print(f"\n[bold]Semantic search results for '{query}'[/bold]\n")

    for i, result in enumerate(results, 1):
        similarity_pct = result["similarity"] * 100
        console.print(
            f"[cyan]{i}. [{result['episode_id']}] "
            f"(similarity: {similarity_pct:.1f}%)[/cyan]"
        )
        console.print(f"   {result['speaker']} @ {result['timestamp']:.1f}s")
        console.print(f"   {result['text'][:150]}...")
        console.print()


@click.command()
@click.pass_context
def main(ctx: click.Context) -> None:
    """Search and analyze podcast transcripts.

    Full-text search, semantic search, and quote extraction.
    """
    # Forward to group
    search_group(standalone_mode=False)


if __name__ == "__main__":
    main()
