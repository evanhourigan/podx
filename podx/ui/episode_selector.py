"""Interactive episode selection UI - v4.0 simplified."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

console = Console()

ITEMS_PER_PAGE = 10


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
        has_analyzed = analysis_path.exists()

        # Check if transcript is diarized
        if has_transcript:
            try:
                t = json.loads(transcript_path.read_text())
                has_diarized = t.get("diarized", False)
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
                "analyzed": has_analyzed,
            }
        )

    return episodes


def _format_episode(ep: Dict[str, Any]) -> str:
    """Format an episode for display with status indicators."""
    show = ep.get("show", "Unknown")[:20]
    date = ep.get("date", "")
    title = ep.get("title", "Unknown")[:40]

    # Build status indicators
    status = []
    if ep.get("transcribed"):
        status.append("transcribed")
    if ep.get("diarized"):
        status.append("diarized")
    if ep.get("analyzed"):
        status.append("analyzed")

    status_str = f" [dim][{', '.join(status)}][/dim]" if status else ""

    return f"{show}: {date} - {title}{status_str}"


def select_episode_interactive(
    scan_dir: str,
    show_filter: Optional[str] = None,
    console: Optional[Console] = None,
    run_passthrough_fn=None,  # Unused, kept for compatibility
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Interactively select an episode from scanned directory.

    Args:
        scan_dir: Directory to scan for episodes
        show_filter: Optional show name filter
        console: Rich console instance (optional)

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

    if not eps:
        if show_filter:
            console.print(f"[yellow]No episodes found for '{show_filter}'[/yellow]")
        else:
            console.print(f"[yellow]No episodes found in {scan_dir}[/yellow]")
        console.print("[dim]Run 'podx fetch' to download episodes[/dim]")
        return None, None

    # Sort newest first
    eps_sorted = sorted(eps, key=lambda x: (x["date"], x["show"]), reverse=True)
    page = 0
    total_pages = max(1, (len(eps_sorted) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    while True:
        start = page * ITEMS_PER_PAGE
        end = min(start + ITEMS_PER_PAGE, len(eps_sorted))

        console.print(f"\n[bold cyan]Select an episode[/bold cyan] (page {page + 1}/{total_pages})\n")

        for idx, ep in enumerate(eps_sorted[start:end], start=start + 1):
            formatted = _format_episode(ep)
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
