"""CLI command for post-analysis Q&A on episode transcripts."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown

from podx.core.ask import append_qa_to_notion, ask_transcript
from podx.core.backfill import NOTION_DB_ID, find_transcript
from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.ui import select_episode_interactive

logger = get_logger(__name__)
console = Console()


@click.command(context_settings={"max_content_width": 120})
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--question", "-q", required=True, help="Question to ask about the episode")
@click.option("--model", default="gpt-5.1", show_default=True, help="LLM model for answering")
@click.option("--notion", is_flag=True, help="Append Q&A to the episode's Notion page")
def main(
    path: Optional[Path],
    question: str,
    model: str,
    notion: bool,
) -> None:
    """Ask a question about an episode transcript.

    Sends the full transcript to an LLM with your question and
    returns a detailed answer citing speakers and timestamps.

    \b
    Examples:
      podx ask ./episode/ -q "What was the main argument?"
      podx ask ./episode/ -q "How does this relate to consulting?" --notion
      podx ask ./episode/ -q "Summarize the guest's background" --model gpt-5.1
    """
    # Resolve episode directory
    if path:
        episode_dir = path if path.is_dir() else path.parent
    else:
        episode_dir = select_episode_interactive()
        if not episode_dir:
            sys.exit(0)

    # Find and load transcript
    transcript_path = find_transcript(episode_dir)
    if not transcript_path:
        console.print(f"[red]Error:[/red] No transcript found in {episode_dir}")
        console.print("[dim]Run 'podx transcribe' first[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))

    # Load episode metadata
    meta_path = episode_dir / "episode-meta.json"
    episode_meta = None
    if meta_path.exists():
        episode_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Show context
    if episode_meta:
        show = episode_meta.get("show", "")
        title = episode_meta.get("episode_title", "")
        if show or title:
            console.print(f"[cyan]{show}[/cyan] — {title}")

    console.print(f"[dim]Model: {model}[/dim]")
    console.print(f"[dim]Question: {question}[/dim]\n")

    # Ask the question
    try:
        answer = ask_transcript(
            transcript=transcript,
            question=question,
            model=model,
            episode_meta=episode_meta,
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)

    # Display answer
    console.print(Markdown(answer))

    # Optionally append to Notion
    if notion:
        episode_title = ""
        if episode_meta:
            episode_title = episode_meta.get("episode_title", "")

        if not episode_title:
            console.print("\n[yellow]Warning:[/yellow] No episode title found, skipping Notion")
        else:
            try:
                append_qa_to_notion(
                    episode_title=episode_title,
                    question=question,
                    answer=answer,
                    db_id=NOTION_DB_ID,
                )
                console.print("\n[green]Q&A appended to Notion page[/green]")
            except Exception as e:
                console.print(f"\n[red]Notion append failed:[/red] {e}")

    sys.exit(ExitCode.SUCCESS)
