"""Interactive episode selection UI."""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..domain.constants import (COLUMN_WIDTH_ASR, COLUMN_WIDTH_DATE,
                                COLUMN_WIDTH_DEEP, COLUMN_WIDTH_DIAR,
                                COLUMN_WIDTH_EPISODE_NUM,
                                COLUMN_WIDTH_LAST_RUN, COLUMN_WIDTH_PROC,
                                COLUMN_WIDTH_SHOW, EPISODES_PER_PAGE,
                                MIN_TITLE_COLUMN_WIDTH, TABLE_BORDER_PADDING)

try:
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


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

        # Scan for artifacts
        audio_meta = (ep_dir / "audio-meta.json").exists()
        transcripts = list(ep_dir.glob("transcript-*.json"))
        diarized = list(ep_dir.glob("transcript-diarized-*.json")) or list(
            ep_dir.glob("diarized-transcript-*.json")
        )
        deepcasts = list(ep_dir.glob("deepcast-*.json"))
        notion_out = (ep_dir / "notion.out.json").exists()

        # Newest file time as last run
        try:
            all_files = transcripts + diarized + deepcasts
            newest = max(
                [p.stat().st_mtime for p in all_files] or [meta_path.stat().st_mtime]
            )
            last_run = time.strftime("%Y-%m-%d %H:%M", time.localtime(newest))
        except Exception:
            last_run = ""

        # Build processing flags summary from artifacts (P=preprocess, D=diarize)
        proc_flags = []
        if list(ep_dir.glob("transcript-preprocessed-*.json")):
            proc_flags.append("P")
        if diarized:
            proc_flags.append("D")

        # Try to get duration from transcript files
        duration = None
        if transcripts:
            try:
                # Read first transcript to get duration
                transcript_data = json.loads(transcripts[0].read_text(encoding="utf-8"))
                duration = transcript_data.get("duration")
            except Exception:
                pass

        episodes.append(
            {
                "meta_path": meta_path,
                "directory": ep_dir,
                "show": show_val,
                "date": date_fmt,
                "title": title_val,
                "audio_meta": audio_meta,
                "transcripts": transcripts,
                "diarized": diarized,
                "deepcasts": deepcasts,
                "notion": notion_out,
                "last_run": last_run,
                "processing_flags": "".join(proc_flags),
                "duration": duration,
            }
        )

    return episodes


def select_episode_interactive(
    scan_dir: str,
    show_filter: Optional[str] = None,
    console=None,
    run_passthrough_fn=None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Interactively select an episode from scanned directory.

    Args:
        scan_dir: Directory to scan for episodes
        show_filter: Optional show name filter
        console: Rich console instance
        run_passthrough_fn: Function to run fetch in passthrough mode

    Returns:
        Tuple of (selected_episode, episode_metadata)

    Raises:
        SystemExit: If user cancels or no episodes found
    """
    if not RICH_AVAILABLE:
        raise SystemExit(
            "Interactive select requires rich. Install with: pip install rich"
        )

    from .formatters import clean_cell

    if console is None:
        from ..ui_styles import make_console

        console = make_console()

    # Scan episodes
    eps = scan_episode_status(Path(scan_dir))

    # Optional filter by --show if provided
    if show_filter:
        s_l = show_filter.lower()
        eps = [e for e in eps if s_l in (e.get("show", "").lower())]

    if not eps:
        if show_filter:
            console.print(
                f"[red]❌ No episodes found for show '{show_filter}' in {scan_dir}[/red]"
            )
            console.print(
                "[dim]Tip: run 'podx-fetch --interactive' to download episodes first.[/dim]"
            )
        else:
            console.print(f"[red]❌ No episodes found in {scan_dir}[/red]")
        raise SystemExit(1)

    # Sort newest first
    eps_sorted = sorted(eps, key=lambda x: (x["date"], x["show"]), reverse=True)
    page = 0
    per_page = EPISODES_PER_PAGE
    total_pages = max(1, (len(eps_sorted) + per_page - 1) // per_page)
    selected = None

    while True:
        console.clear()
        start = page * per_page
        end = min(start + per_page, len(eps_sorted))

        # Compute dynamic width for Title column
        try:
            console_width = console.size.width
        except Exception:
            console_width = 120

        # Sum of fixed columns widths
        fixed_cols = (
            COLUMN_WIDTH_EPISODE_NUM
            + COLUMN_WIDTH_SHOW
            + COLUMN_WIDTH_DATE
            + COLUMN_WIDTH_ASR
            + COLUMN_WIDTH_DIAR
            + COLUMN_WIDTH_DEEP
            + COLUMN_WIDTH_PROC
            + COLUMN_WIDTH_LAST_RUN
        )

        # Extra allowance for table borders/padding/separators
        borders_allowance = TABLE_BORDER_PADDING

        # Let Title shrink further on small terminals
        title_width = max(
            MIN_TITLE_COLUMN_WIDTH, console_width - fixed_cols - borders_allowance
        )

        # Create table
        from ..ui_styles import (TABLE_BORDER_STYLE, TABLE_HEADER_STYLE,
                                 TABLE_NUM_STYLE)

        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            title=f"🎙️ Episodes (Page {page+1}/{total_pages})",
            expand=True,
            border_style=TABLE_BORDER_STYLE,
            pad_edge=False,
        )

        table.add_column(
            "#",
            style=TABLE_NUM_STYLE,
            width=COLUMN_WIDTH_EPISODE_NUM,
            justify="right",
            no_wrap=True,
        )
        table.add_column("Show", style="green", width=COLUMN_WIDTH_SHOW, no_wrap=True)
        table.add_column(
            "Date",
            style="blue",
            width=COLUMN_WIDTH_DATE,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            "Title", style="white", width=title_width, no_wrap=True, overflow="ellipsis"
        )
        table.add_column(
            "ASR", style="yellow", width=COLUMN_WIDTH_ASR, no_wrap=True, justify="right"
        )
        table.add_column(
            "Diar",
            style="yellow",
            width=COLUMN_WIDTH_DIAR,
            no_wrap=True,
            justify="center",
        )
        table.add_column(
            "Deep",
            style="yellow",
            width=COLUMN_WIDTH_DEEP,
            no_wrap=True,
            justify="right",
        )
        table.add_column("Proc", style="yellow", width=COLUMN_WIDTH_PROC, no_wrap=True)
        table.add_column(
            "Last Run", style="white", width=COLUMN_WIDTH_LAST_RUN, no_wrap=True
        )

        # Add rows
        for idx, e in enumerate(eps_sorted[start:end], start=start + 1):
            asr_count_val = len(e["transcripts"]) if e["transcripts"] else 0
            asr_count = "-" if asr_count_val == 0 else str(asr_count_val)
            diar_ok = "✓" if e["diarized"] else "○"
            dc_count_val = len(e["deepcasts"]) if e["deepcasts"] else 0
            dc_count = "[dim]-[/dim]" if dc_count_val == 0 else str(dc_count_val)
            proc = e.get("processing_flags", "")

            # Sanitize problematic characters
            title_cell = clean_cell(e["title"] or "")
            show_cell = clean_cell(e["show"]) if e.get("show") else ""

            table.add_row(
                str(idx),
                show_cell,
                e["date"],
                title_cell,
                asr_count,
                diar_ok,
                dc_count,
                proc,
                e["last_run"],
            )

        console.print(table)
        extra = " • F fetch new" if show_filter else ""
        total = len(eps_sorted)
        footer = f"[dim]Enter 1-{end} of {total} to select • N next • P prev • Q quit{extra}[/dim]"
        console.print(footer)

        choice = input("\n👉 Select: ").strip().upper()

        if choice in ["Q", "QUIT", "EXIT"]:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)

        if choice == "F" and show_filter and run_passthrough_fn:
            # Open fetch browser to add episodes, then re-scan
            console.print(
                f"[dim]Opening fetch browser for show '{show_filter}'...[/dim]"
            )
            try:
                rc = run_passthrough_fn(
                    ["podx-fetch", "--show", show_filter, "--interactive"]
                )
                if rc != 0:
                    console.print("[red]❌ Fetch cancelled or failed[/red]")
            except Exception:
                console.print("[red]❌ Fetch cancelled or failed[/red]")

            # Re-scan and continue
            eps = scan_episode_status(Path(scan_dir))
            if show_filter:
                s_l = show_filter.lower()
                eps = [e for e in eps if s_l in (e.get("show", "").lower())]
            eps_sorted = sorted(eps, key=lambda x: (x["date"], x["show"]), reverse=True)
            total_pages = max(1, (len(eps_sorted) + per_page - 1) // per_page)
            page = min(page, total_pages - 1)
            continue

        if choice == "N" and page < total_pages - 1:
            page += 1
            continue

        if choice == "P" and page > 0:
            page -= 1
            continue

        try:
            sel = int(choice)
            if not (start + 1) <= sel <= end:
                raise ValueError
            selected = eps_sorted[sel - 1]
            break
        except Exception:
            console.print("[red]❌ Invalid selection[/red]")
            input("Press Enter to continue...")

    # Load metadata
    meta = json.loads(selected["meta_path"].read_text(encoding="utf-8"))

    return selected, meta
