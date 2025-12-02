"""Interactive episode selection UI - v4.0 simplified."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from rich.console import Console

console = Console()

ITEMS_PER_PAGE = 10

# Required artifact types for filtering
RequiredArtifact = Literal["transcript", "diarized", "analyzed", "audio", None]


def scan_episode_status(root: Path) -> List[Dict[str, Any]]:
    """Scan directory for episode metadata and processing status.

    Args:
        root: Directory to scan for episode-meta.json files

    Returns:
        List of episode dictionaries with metadata and processing status
    """
    episodes = []
    for meta_path in root.rglob("episode-meta.json"):
        try:
            em = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        ep_dir = meta_path.parent
        show_val = em.get("show", "Unknown")
        date_val = em.get("episode_published", "")

        # Format date YYYY-MM-DD when possible
        if date_val:
            try:
                from dateutil import parser as dtparse

                parsed = dtparse.parse(date_val)
                date_fmt = parsed.strftime("%Y-%m-%d")
            except Exception:
                date_fmt = date_val[:10] if len(date_val) >= 10 else date_val
        else:
            date_fmt = ep_dir.name

        title_val = em.get("episode_title", "Unknown")

        # Check for v4 file naming (transcript.json, analysis.json)
        transcript_path = ep_dir / "transcript.json"
        analysis_path = ep_dir / "analysis.json"

        has_transcript = transcript_path.exists()
        has_diarized = False
        has_cleaned = False
        has_analyzed = analysis_path.exists()

        # Check transcript state flags
        if has_transcript:
            try:
                t = json.loads(transcript_path.read_text())
                has_diarized = t.get("diarized", False)
                has_cleaned = t.get("cleaned", False)
            except Exception:
                pass

        # Also check legacy patterns
        if not has_transcript:
            has_transcript = bool(list(ep_dir.glob("transcript-*.json")))
        if not has_diarized:
            has_diarized = bool(
                list(ep_dir.glob("transcript-diarized-*.json"))
                or list(ep_dir.glob("diarized-transcript-*.json"))
            )
        if not has_analyzed:
            has_analyzed = bool(list(ep_dir.glob("deepcast-*.json")))

        episodes.append(
            {
                "meta_path": meta_path,
                "directory": ep_dir,
                "show": show_val,
                "date": date_fmt,
                "title": title_val,
                "transcribed": has_transcript,
                "diarized": has_diarized,
                "cleaned": has_cleaned,
                "analyzed": has_analyzed,
            }
        )

    return episodes


def _format_episode(ep: Dict[str, Any], max_width: int = 80) -> str:
    """Format an episode for display with status indicators.

    Tries to fit on one line: "Show (date) - Title (status)"
    Wraps to multiple lines only if needed.

    Args:
        ep: Episode dictionary with show, date, title, and status fields
        max_width: Maximum width for text wrapping

    Returns:
        Formatted string (may contain newlines if content is too long)
    """
    show = ep.get("show", "Unknown")
    date = ep.get("date", "")
    title = ep.get("title", "Unknown")

    # Build status indicators
    status_parts = []
    if ep.get("transcribed"):
        status_parts.append("transcribed")
    if ep.get("diarized"):
        status_parts.append("diarized")
    if ep.get("cleaned"):
        status_parts.append("cleaned")
    if ep.get("analyzed"):
        status_parts.append("analyzed")

    status_str = f" [dim]({', '.join(status_parts)})[/dim]" if status_parts else ""

    # Calculate available width (account for line number prefix "  123  ")
    content_width = max_width - 7

    # Try single line format: "Show (date) - Title (status)"
    if date:
        single_line = f"{show} [dim]({date})[/dim] - {title}{status_str}"
        # Check length without markup
        plain_len = (
            len(show)
            + len(date)
            + 3
            + 3
            + len(title)
            + sum(len(s) for s in status_parts)
            + 4
        )
    else:
        single_line = f"{show} - {title}{status_str}"
        plain_len = len(show) + 3 + len(title) + sum(len(s) for s in status_parts) + 4

    if plain_len <= content_width:
        return single_line

    # Need to wrap - use two lines
    # Line 1: Show (date) (status)
    line1 = f"{show} [dim]({date})[/dim]{status_str}" if date else f"{show}{status_str}"

    # Truncate title if needed for line 2
    available_for_title = content_width - 7  # Account for indent
    if len(title) > available_for_title:
        title = title[: available_for_title - 3] + "..."
    line2 = f"       {title}"

    return f"{line1}\n{line2}"


def select_episode_interactive(
    scan_dir: str,
    show_filter: Optional[str] = None,
    console: Optional[Console] = None,
    run_passthrough_fn: Any = None,  # Unused, kept for compatibility
    require: RequiredArtifact = None,
    title: str = "Select an episode",
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Interactively select an episode from scanned directory.

    Args:
        scan_dir: Directory to scan for episodes
        show_filter: Optional show name filter
        console: Rich console instance (optional)
        run_passthrough_fn: Unused, kept for compatibility
        require: Only show episodes with this artifact:
                 - "transcript": must have transcript.json
                 - "diarized": must have diarized transcript
                 - "analyzed": must have analysis.json
                 - "audio": must have audio file (for transcribe)
                 - None: show all episodes
        title: Title to display above the list

    Returns:
        Tuple of (selected_episode, episode_metadata) or (None, None) if cancelled
    """
    if console is None:
        console = Console()

    # Scan episodes
    eps = scan_episode_status(Path(scan_dir))

    # Optional filter by show
    if show_filter:
        s_l = show_filter.lower()
        eps = [e for e in eps if s_l in (e.get("show", "").lower())]

    # Filter by required artifact
    if require == "transcript":
        eps = [e for e in eps if e.get("transcribed")]
    elif require == "diarized":
        eps = [e for e in eps if e.get("diarized")]
    elif require == "analyzed":
        eps = [e for e in eps if e.get("analyzed")]
    elif require == "audio":
        # For transcribe - only show episodes that have audio but NOT transcript
        eps = [e for e in eps if not e.get("transcribed")]

    if not eps:
        if require:
            requirement_msg = {
                "transcript": "with transcripts",
                "diarized": "with diarized transcripts",
                "analyzed": "with analysis",
                "audio": "ready for transcription",
            }.get(require, "matching criteria")
            console.print(f"[yellow]No episodes found {requirement_msg}[/yellow]")
            if require == "transcript":
                console.print("[dim]Run 'podx transcribe' first[/dim]")
            elif require == "audio":
                console.print("[dim]All episodes are already transcribed[/dim]")
        elif show_filter:
            console.print(f"[yellow]No episodes found for '{show_filter}'[/yellow]")
        else:
            console.print(f"[yellow]No episodes found in {scan_dir}[/yellow]")
            console.print("[dim]Run 'podx fetch' to download episodes[/dim]")
        return None, None

    # Sort newest first
    eps_sorted = sorted(eps, key=lambda x: (x["date"], x["show"]), reverse=True)
    page = 0
    total_pages = max(1, (len(eps_sorted) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    # Get terminal width for formatting
    term_width = shutil.get_terminal_size().columns

    while True:
        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, len(eps_sorted))

        console.print(
            f"\n[bold cyan]{title}[/bold cyan] (page {page + 1}/{total_pages})\n"
        )

        for idx, ep in enumerate(eps_sorted[start:end], start=start + 1):
            formatted = _format_episode(ep, max_width=term_width)
            console.print(f"  [bold]{idx:3}[/bold]  {formatted}")

        console.print()
        console.print("[dim]Enter number to select • n next • p prev • q quit[/dim]")

        try:
            choice = input("\n> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None, None

        if choice in ("q", "quit"):
            return None, None

        if choice == "n" and page < total_pages - 1:
            page += 1
            continue

        if choice == "p" and page > 0:
            page -= 1
            continue

        try:
            sel = int(choice)
            if 1 <= sel <= len(eps_sorted):
                selected = eps_sorted[sel - 1]
                meta = json.loads(selected["meta_path"].read_text(encoding="utf-8"))
                return selected, meta
            console.print("[red]Invalid number[/red]")
        except ValueError:
            console.print("[red]Invalid input[/red]")
