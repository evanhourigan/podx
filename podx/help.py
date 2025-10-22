#!/usr/bin/env python3
"""
Enhanced help and documentation system for podx.
"""

from typing import Dict, List

# Prefer rich-click when available for colorized --help
try:  # pragma: no cover
    import click  # type: ignore
    import rich_click  # type: ignore
    rc = rich_click.rich_click
    rc.STYLE_HEADING = "bold bright_green"
    rc.STYLE_USAGE = "bold white"
    rc.STYLE_COMMAND = "bold white"
    rc.STYLE_METAVAR = "yellow"
    rc.STYLE_SWITCH = "bright_black"
    rc.STYLE_OPTION = "bright_black"
    rc.STYLE_ARGUMENT = "yellow"
    rc.STYLE_HELP = "white"
    rc.GROUP_ARGUMENTS_OPTIONS = True
    rc.MAX_WIDTH = 100
except Exception:  # pragma: no cover
    import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from .ui import (
    make_console,
    format_example_line,
    EXAMPLE_HEADING_STYLE,
    TABLE_HEADER_STYLE,
)


def get_examples() -> Dict[str, List[str]]:
    """Get command examples organized by use case."""
    return {
        "Basic Usage": [
            "# Fetch and transcribe a podcast episode",
            "podx-fetch --show 'This American Life' --date 2024-01-15 | podx-transcribe",
            "",
            "# Complete pipeline with smart directory",
            "podx run --show 'Radio Lab' --date 2024-01-15",
        ],
        "Advanced Pipeline": [
            "# Full pipeline with AI analysis",
            "podx run --show 'The Podcast' --date 2024-01-15 --diarize --deepcast",
            "",
            "# Upload to Notion",
            "podx run --show 'The Podcast' --date 2024-01-15 --deepcast --notion",
        ],
        "Unix-style Piping": [
            "# Chain commands manually",
            "podx-fetch --show 'Radiolab' --date 2024-01-15 \\",
            "| podx-transcode --to wav16 \\",
            "| podx-transcribe --preset balanced \\",
            "| podx-export --formats txt,srt",
        ],
        "RSS Feeds": [
            "# Use direct RSS URL",
            "podx-fetch --rss-url 'https://feeds.example.com/podcast.xml' --date 2024-01-15",
            "",
            "# Private podcast with full pipeline",
            "podx run --rss-url 'https://private-feed.com/feed.xml' --date 2024-01-15 --deepcast",
        ],
        "Providers & Presets": [
            "# Local provider (default)",
            "podx-transcribe --model large-v3 --preset balanced < audio-meta.json",
            "",
            "# OpenAI provider",
            "OPENAI_API_KEY=sk-... podx-transcribe --model openai:large-v3-turbo < audio-meta.json",
            "",
            "# Hugging Face provider",
            "podx-transcribe --model hf:distil-large-v3 < audio-meta.json",
            "",
            "# Recall preset (more coverage)",
            "podx-transcribe --model large-v3 --preset recall < audio-meta.json",
            "",
            "# Expert flags (local only)",
            "podx-transcribe --expert --vad-filter --condition-on-previous-text < audio-meta.json",
        ],
        "Preprocess & Agreement": [
            "# Preprocess transcript (merge + normalize)",
            "podx-preprocess --merge --normalize -i transcript.json -o transcript-preprocessed.json",
            "",
            "# Run with orchestrator (with semantic restore)",
            "podx run --rss-url '...' --date 2024-01-15 --preprocess --restore --deepcast",
        ],
    }


def print_examples():
    """Print formatted examples to console."""
    console = make_console()
    examples = get_examples()

    console.print("\n[bold blue]📚 Podx Usage Examples[/bold blue]\n")

    for category, commands in examples.items():
        console.print(Text(f"💡 {category}", style=EXAMPLE_HEADING_STYLE))
        console.print()

        for command in commands:
            if command:
                console.print(format_example_line(command))
            else:
                console.print()

        console.print()


def print_pipeline_flow():
    """Print visual pipeline flow diagram."""
    console = make_console()

    table = Table(
        title="🎙️ Podx Pipeline Flow", show_header=True, header_style=TABLE_HEADER_STYLE
    )
    # Wider columns to avoid truncation
    table.add_column("Step", style="white", width=16)
    table.add_column("Tool", style="white", width=18)
    table.add_column("Input", style="white", width=30)
    table.add_column("Output", style="white", width=30)
    table.add_column("Optional", style="white", width=8)

    pipeline_steps = [
        ("1. Fetch", "podx-fetch", "Show name/RSS URL", "EpisodeMeta JSON", "No"),
        ("2. Transcode", "podx-transcode", "EpisodeMeta JSON", "AudioMeta JSON", "No"),
        ("3. Transcribe", "podx-transcribe", "AudioMeta JSON", "Transcript JSON", "No"),
        ("4. Preprocess", "podx-preprocess", "Any Transcript", "Preprocessed JSON", "Yes"),
        ("5. Diarize", "podx-diarize", "Transcript JSON", "Diarized JSON", "Yes"),
        ("6. Export", "podx-export", "Any Transcript", "TXT/SRT/VTT files", "No"),
        ("7. Deepcast", "podx-deepcast", "Any Transcript", "AI Analysis", "Yes"),
        ("8. Notion", "podx-notion", "Deepcast output", "Notion page", "Yes"),
    ]

    for step, tool, input_type, output_type, optional in pipeline_steps:
        table.add_row(step, tool, input_type, output_type, optional)

    console.print(table)
    console.print()

    # Print flow diagram (monochrome, aligned, no code block background)
    console.print("\n[bold white]🔄 Data Flow[/bold white]\n")
    # Columns including preprocess
    cols_sources = [
        "iTunes/RSS",
        "Audio File",
        "Transcript",
        "Preprocessed",
        "Analysis",
        "Notion",
    ]
    cols_tools = [
        "podx-fetch",
        "podx-transcode",
        "podx-transcribe",
        "podx-preprocess",
        "podx-deepcast",
        "podx-notion",
    ]
    cols_artifacts = [
        "EpisodeMeta",
        "AudioMeta",
        "Transcript JSON",
        "Preprocessed JSON",
        "Deepcast JSON",
        "Notion page",
    ]

    # Compute per-column widths to align arrows
    def row_from(parts: list[str]) -> str:
        widths = [max(len(cols_sources[i]), len(cols_tools[i]), len(cols_artifacts[i])) for i in range(len(cols_sources))]
        segments = [parts[i].ljust(widths[i]) for i in range(len(parts))]
        return "  →  ".join(segments)

    left_labels = ["Sources:", "Tools:", "Artifacts:"]
    left_pad = max(len(s) for s in left_labels) + 1
    lines = [row_from(cols_sources), row_from(cols_tools), row_from(cols_artifacts)]
    for label, content in zip(left_labels, lines):
        console.print(f"[white]{label.ljust(left_pad)}{content}[/white]")


def print_default_help():
    """Print the default top-level help content (rich, colorized when TTY)."""
    console = Console()
    help_md = """
# 🎙️ Podx - Composable Podcast Pipeline

Podx is a modular toolkit for podcast processing that follows Unix philosophy:
each tool does one thing well and can be combined via pipes.

## 🚀 Quick Start

# Simple transcription
podx run --show "This American Life" --date 2024-01-15

# Full pipeline with AI analysis
podx run --show "Radio Lab" --date 2024-01-15 --diarize --deepcast --notion

## 🔧 Available Tools (All composable)

- `podx-fetch` - Download episodes from iTunes or RSS
- `podx-transcode` - Convert audio formats
- `podx-transcribe` - Speech-to-text with Whisper
- `podx-preprocess` - Merge/normalize/restore transcript
- `podx-diarize` - Speaker identification with word-level alignment
- `podx-export` - Export to various formats
- `podx-deepcast` - AI-powered analysis
- `podx-notion` - Upload to Notion database
- `podx run` - Orchestrate full pipeline

## 📖 More Help

podx help --examples    # Show usage examples
podx help --pipeline    # Show pipeline flow
podx COMMAND --help     # Help for specific command
    """
    console.print(Markdown(help_md))


@click.command()
@click.option("--examples", is_flag=True, help="Show usage examples")
@click.option("--pipeline", is_flag=True, help="Show pipeline flow diagram")
def help_cmd(examples: bool, pipeline: bool):
    """Enhanced help system for podx."""
    if examples:
        print_examples()
        return

    if pipeline:
        print_pipeline_flow()
        return

    # Default help
    print_default_help()


if __name__ == "__main__":
    help_cmd()
