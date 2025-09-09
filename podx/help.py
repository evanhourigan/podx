#!/usr/bin/env python3
"""
Enhanced help and documentation system for podx.
"""

from typing import Dict, List

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table


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
            "podx run --show 'The Podcast' --date 2024-01-15 --align --diarize --deepcast",
            "",
            "# Upload to Notion",
            "podx run --show 'The Podcast' --date 2024-01-15 --deepcast --notion",
        ],
        "Unix-style Piping": [
            "# Chain commands manually",
            "podx-fetch --show 'Radiolab' --date 2024-01-15 \\",
            "| podx-transcode --to wav16 \\",
            "| podx-transcribe \\",
            "| podx-export --formats txt,srt",
        ],
        "RSS Feeds": [
            "# Use direct RSS URL",
            "podx-fetch --rss-url 'https://feeds.example.com/podcast.xml' --date 2024-01-15",
            "",
            "# Private podcast with full pipeline",
            "podx run --rss-url 'https://private-feed.com/feed.xml' --date 2024-01-15 --deepcast",
        ],
    }


def print_examples():
    """Print formatted examples to console."""
    console = Console()
    examples = get_examples()

    console.print("\n[bold blue]📚 Podx Usage Examples[/bold blue]\n")

    for category, commands in examples.items():
        console.print(f"[bold cyan]💡 {category}[/bold cyan]")
        console.print()

        for command in commands:
            if command.startswith("#"):
                console.print(f"[italic green]{command}[/italic green]")
            elif command:
                console.print(f"[white]{command}[/white]")
            else:
                console.print()

        console.print()


def print_pipeline_flow():
    """Print visual pipeline flow diagram."""
    console = Console()

    table = Table(
        title="🎙️ Podx Pipeline Flow", show_header=True, header_style="bold magenta"
    )
    table.add_column("Step", style="cyan", width=12)
    table.add_column("Tool", style="yellow", width=15)
    table.add_column("Input", style="green", width=20)
    table.add_column("Output", style="blue", width=20)
    table.add_column("Optional", style="red", width=8)

    pipeline_steps = [
        ("1. Fetch", "podx-fetch", "Show name/RSS URL", "EpisodeMeta JSON", "No"),
        ("2. Transcode", "podx-transcode", "EpisodeMeta JSON", "AudioMeta JSON", "No"),
        ("3. Transcribe", "podx-transcribe", "AudioMeta JSON", "Transcript JSON", "No"),
        ("4. Align", "podx-align", "Transcript JSON", "Aligned JSON", "Yes"),
        ("5. Diarize", "podx-diarize", "Aligned JSON", "Diarized JSON", "Yes"),
        ("6. Export", "podx-export", "Any Transcript", "TXT/SRT/VTT files", "No"),
        ("7. Deepcast", "podx-deepcast", "Any Transcript", "AI Analysis", "Yes"),
        ("8. Notion", "podx-notion", "Deepcast output", "Notion page", "Yes"),
    ]

    for step, tool, input_type, output_type, optional in pipeline_steps:
        table.add_row(step, tool, input_type, output_type, optional)

    console.print(table)
    console.print()

    # Print flow diagram
    flow_md = """
## 🔄 Data Flow

```
📱 iTunes/RSS → 🎵 Audio File → 🎤 Transcript → 📝 Analysis → ☁️ Notion
    ↓              ↓              ↓              ↓             ↓
podx-fetch → podx-transcode → podx-transcribe → podx-deepcast → podx-notion
    ↓              ↓              ↓
 EpisodeMeta → AudioMeta → Transcript
```

**Key Points:**
- Each step outputs JSON to stdout for piping
- Optional steps can be skipped based on needs
- `podx run` orchestrates the full pipeline
- All intermediate files are saved for inspection
    """

    console.print(Markdown(flow_md))


@click.command()
@click.option("--examples", is_flag=True, help="Show usage examples")
@click.option("--pipeline", is_flag=True, help="Show pipeline flow diagram")
def help_cmd(examples: bool, pipeline: bool):
    """Enhanced help system for podx."""
    console = Console()

    if examples:
        print_examples()
        return

    if pipeline:
        print_pipeline_flow()
        return

    # Default help
    help_md = """
# 🎙️ Podx - Composable Podcast Pipeline

Podx is a modular toolkit for podcast processing that follows Unix philosophy:
each tool does one thing well and can be combined via pipes.

## 🚀 Quick Start

```bash
# Simple transcription
podx run --show "This American Life" --date 2024-01-15

# Full pipeline with AI analysis
podx run --show "Radio Lab" --date 2024-01-15 --align --diarize --deepcast --notion
```

## 🔧 Available Tools

- `podx-fetch` - Download episodes from iTunes or RSS
- `podx-transcode` - Convert audio formats
- `podx-transcribe` - Speech-to-text with Whisper
- `podx-align` - Word-level timing alignment
- `podx-diarize` - Speaker identification
- `podx-export` - Export to various formats
- `podx-deepcast` - AI-powered analysis
- `podx-notion` - Upload to Notion database
- `podx run` - Orchestrate full pipeline

## 📖 More Help

```bash
podx help --examples    # Show usage examples
podx help --pipeline    # Show pipeline flow
podx COMMAND --help     # Help for specific command
```

## 🌐 Documentation

Full documentation available at: https://github.com/your-repo/podx
    """

    console.print(Markdown(help_md))


if __name__ == "__main__":
    help_cmd()
