#!/usr/bin/env python3
"""CLI commands for transcript analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from podx.domain.models.transcript import Transcript
from podx.search import QuoteExtractor

console = Console()


@click.group()
def analyze_group() -> None:
    """Analyze transcript content."""
    pass


@analyze_group.command(name="quotes")
@click.argument("transcript_path", type=click.Path(exists=True))
@click.option("--max-quotes", default=20, help="Maximum quotes to extract")
@click.option("--speaker", help="Filter by speaker")
@click.option("--by-speaker", is_flag=True, help="Group quotes by speaker")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def extract_quotes(
    transcript_path: str,
    max_quotes: int,
    speaker: Optional[str],
    by_speaker: bool,
    json_output: bool,
) -> None:
    """Extract notable quotes from a transcript.

    Examples:
        # Extract top 20 quotes
        podx-analyze quotes transcript.json

        # Filter by speaker
        podx-analyze quotes transcript.json --speaker "Alice"

        # Group by speaker
        podx-analyze quotes transcript.json --by-speaker

        # JSON output
        podx-analyze quotes transcript.json --json-output
    """
    # Load transcript
    transcript = Transcript.from_file(Path(transcript_path))
    extractor = QuoteExtractor()

    if by_speaker:
        results = extractor.extract_by_speaker(transcript, top_n=5)

        if json_output:
            console.print(json.dumps(results, indent=2))
        else:
            _display_quotes_by_speaker(results)
    else:
        quotes = extractor.extract_quotes(
            transcript, max_quotes=max_quotes, speaker_filter=speaker
        )

        if json_output:
            console.print(json.dumps(quotes, indent=2))
        else:
            _display_quotes(quotes)


@analyze_group.command(name="highlights")
@click.argument("transcript_path", type=click.Path(exists=True))
@click.option("--duration", default=30.0, help="Max time gap between quotes (seconds)")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def find_highlights(
    transcript_path: str, duration: float, json_output: bool
) -> None:
    """Find highlight moments in a transcript.

    Highlights are clusters of high-quality quotes close in time.

    Examples:
        # Find highlights
        podx-analyze highlights transcript.json

        # Adjust clustering threshold
        podx-analyze highlights transcript.json --duration 60
    """
    # Load transcript
    transcript = Transcript.from_file(Path(transcript_path))
    extractor = QuoteExtractor()

    highlights = extractor.find_highlights(transcript, duration_threshold=duration)

    if json_output:
        console.print(json.dumps(highlights, indent=2))
    else:
        _display_highlights(highlights)


@analyze_group.command(name="topics")
@click.argument("episode_id", required=False)
@click.option("--clusters", default=10, help="Number of topic clusters")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def cluster_topics(
    episode_id: Optional[str], clusters: int, json_output: bool
) -> None:
    """Cluster transcript segments into topics.

    Requires semantic search to be installed.

    Examples:
        # Cluster all indexed transcripts
        podx-analyze topics

        # Cluster specific episode
        podx-analyze topics ep001

        # Adjust number of clusters
        podx-analyze topics ep001 --clusters 15
    """
    try:
        from podx.search.semantic import SemanticSearch
    except ImportError:
        console.print(
            "[red]Topic clustering requires semantic search[/red]\n"
            "[dim]Install: pip install sentence-transformers faiss-cpu scikit-learn[/dim]"
        )
        return

    semantic = SemanticSearch()
    topic_clusters = semantic.cluster_topics(
        n_clusters=clusters, episode_filter=episode_id
    )

    if json_output:
        console.print(json.dumps(topic_clusters, indent=2))
    else:
        _display_topics(topic_clusters)


@analyze_group.command(name="speakers")
@click.argument("transcript_path", type=click.Path(exists=True))
@click.option("--json-output", is_flag=True, help="Output as JSON")
def analyze_speakers(transcript_path: str, json_output: bool) -> None:
    """Analyze speaker statistics in a transcript.

    Examples:
        # Show speaker stats
        podx-analyze speakers transcript.json
    """
    # Load transcript
    transcript = Transcript.from_file(Path(transcript_path))

    # Calculate stats
    speaker_stats = {}
    total_duration = 0.0

    for segment in transcript.segments:
        speaker = segment.speaker or "Unknown"
        duration = segment.end - segment.start

        if speaker not in speaker_stats:
            speaker_stats[speaker] = {
                "segment_count": 0,
                "total_duration": 0.0,
                "word_count": 0,
            }

        speaker_stats[speaker]["segment_count"] += 1
        speaker_stats[speaker]["total_duration"] += duration
        speaker_stats[speaker]["word_count"] += len(segment.text.split())
        total_duration += duration

    # Calculate percentages
    for speaker in speaker_stats:
        stats = speaker_stats[speaker]
        stats["percentage"] = (stats["total_duration"] / total_duration * 100) if total_duration > 0 else 0

    if json_output:
        console.print(json.dumps(speaker_stats, indent=2))
    else:
        _display_speaker_stats(speaker_stats, total_duration)


def _display_quotes(quotes: list) -> None:
    """Display quote list."""
    if not quotes:
        console.print("[yellow]No notable quotes found[/yellow]")
        return

    console.print(f"\n[bold cyan]Notable Quotes ({len(quotes)})[/bold cyan]\n")

    for i, quote in enumerate(quotes, 1):
        score_pct = quote["score"] * 100
        timestamp = quote["timestamp"]
        mins = int(timestamp // 60)
        secs = int(timestamp % 60)

        console.print(f"[cyan]{i}. {quote['speaker']} [{mins:02d}:{secs:02d}] (score: {score_pct:.0f}%)[/cyan]")
        console.print(f"   \"{quote['text']}\"")
        console.print()


def _display_quotes_by_speaker(results: dict) -> None:
    """Display quotes grouped by speaker."""
    if not results:
        console.print("[yellow]No notable quotes found[/yellow]")
        return

    console.print("\n[bold cyan]Notable Quotes by Speaker[/bold cyan]\n")

    for speaker, quotes in results.items():
        console.print(f"[bold magenta]{speaker}[/bold magenta] ({len(quotes)} quotes)")

        for i, quote in enumerate(quotes, 1):
            score_pct = quote["score"] * 100
            timestamp = quote["timestamp"]
            mins = int(timestamp // 60)
            secs = int(timestamp % 60)

            console.print(
                f"  {i}. [{mins:02d}:{secs:02d}] (score: {score_pct:.0f}%) {quote['text'][:80]}..."
            )

        console.print()


def _display_highlights(highlights: list) -> None:
    """Display highlight moments."""
    if not highlights:
        console.print("[yellow]No highlights found[/yellow]")
        return

    console.print(f"\n[bold cyan]Highlight Moments ({len(highlights)})[/bold cyan]\n")

    for i, highlight in enumerate(highlights, 1):
        start = highlight["start"]
        end = highlight["end"]
        duration = highlight["duration"]
        quote_count = highlight["quote_count"]
        avg_score = highlight["avg_score"] * 100

        start_min = int(start // 60)
        start_sec = int(start % 60)
        end_min = int(end // 60)
        end_sec = int(end % 60)

        console.print(
            f"[cyan]{i}. [{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}] "
            f"({duration:.0f}s, {quote_count} quotes, avg score: {avg_score:.0f}%)[/cyan]"
        )

        for quote in highlight["quotes"][:3]:  # Show first 3 quotes
            console.print(f"   • {quote['speaker']}: {quote['text'][:80]}...")

        if len(highlight["quotes"]) > 3:
            console.print(f"   [dim]... and {len(highlight['quotes']) - 3} more[/dim]")

        console.print()


def _display_topics(topics: list) -> None:
    """Display topic clusters."""
    if not topics:
        console.print("[yellow]No topics found[/yellow]")
        return

    console.print(f"\n[bold cyan]Topic Clusters ({len(topics)})[/bold cyan]\n")

    for topic in topics:
        cluster_id = topic["cluster_id"]
        size = topic["size"]
        rep = topic["representative"]

        console.print(f"[bold magenta]Topic {cluster_id + 1}[/bold magenta] ({size} segments)")
        console.print(f"  Representative: {rep['speaker']}")
        console.print(f"  {rep['text'][:100]}...")
        console.print()


def _display_speaker_stats(stats: dict, total_duration: float) -> None:
    """Display speaker statistics table."""
    if not stats:
        console.print("[yellow]No speakers found[/yellow]")
        return

    table = Table(title="Speaker Statistics")
    table.add_column("Speaker", style="cyan")
    table.add_column("Segments", justify="right", style="white")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Percentage", justify="right", style="magenta")
    table.add_column("Words", justify="right", style="yellow")

    # Sort by duration
    sorted_speakers = sorted(
        stats.items(), key=lambda x: x[1]["total_duration"], reverse=True
    )

    for speaker, speaker_stats in sorted_speakers:
        duration = speaker_stats["total_duration"]
        mins = int(duration // 60)
        secs = int(duration % 60)
        percentage = speaker_stats["percentage"]

        table.add_row(
            speaker,
            str(speaker_stats["segment_count"]),
            f"{mins:02d}:{secs:02d}",
            f"{percentage:.1f}%",
            str(speaker_stats["word_count"]),
        )

    console.print()
    console.print(table)

    # Summary
    total_mins = int(total_duration // 60)
    total_secs = int(total_duration % 60)
    console.print(f"\n[dim]Total duration: {total_mins:02d}:{total_secs:02d}[/dim]\n")


@click.command()
@click.pass_context
def main(ctx: click.Context) -> None:
    """Analyze podcast transcripts.

    Extract quotes, find highlights, cluster topics, and analyze speakers.
    """
    # Forward to group
    analyze_group(standalone_mode=False)


if __name__ == "__main__":
    main()
