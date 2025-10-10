#!/usr/bin/env python3
"""podx-list: Interactive episode list and status browser.

Shows Show, Date, Title with compact status counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import click

from .deepcast import scan_deepcastable_episodes
from .ui import (
    make_console,
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    TABLE_SHOW_STYLE,
    TABLE_DATE_STYLE,
    TABLE_TITLE_COL_STYLE,
)

try:
    from rich.table import Table
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False


def _collect_status(ep: Dict) -> Dict[str, int]:
    asr_count = len(ep.get("asr_models", {}))
    deepcasts_total = 0
    for v in ep.get("asr_models", {}).values():
        deepcasts_total += sum(len(t) for t in v.get("deepcasts", {}).values())
    # Notion marker
    notion = 1 if (Path(ep["directory"]) / "notion.out.json").exists() else 0
    return {"asr": asr_count, "deep": deepcasts_total, "notion": notion}


@click.command()
@click.option("--scan-dir", type=click.Path(exists=True, path_type=Path), default=".", help="Directory to scan (defaults to cwd)")
@click.option("--show", type=str, help="Filter by show name substring")
@click.option("--interactive", is_flag=True, help="Interactive table (TTY only)")
def main(scan_dir: Path, show: Optional[str], interactive: bool):
    console = make_console()
    episodes = scan_deepcastable_episodes(scan_dir)
    if show:
        episodes = [e for e in episodes if show.lower() in e.get("show", "").lower()]
    if not episodes:
        console.print(f"[red]No episodes found in {scan_dir}[/red]")
        raise SystemExit(1)

    # Build rows
    rows: List[Dict[str, str]] = []
    for ep in episodes:
        st = _collect_status(ep)
        rows.append(
            {
                "show": ep.get("show", ""),
                "date": ep.get("date", ""),
                "title": ep.get("title", ""),
                "asr": str(st["asr"]) if st["asr"] else "-",
                "deep": str(st["deep"]) if st["deep"] else "-",
                "notion": "✓" if st["notion"] else "-",
            }
        )

    # Render table
    term_width = console.size.width
    fixed = {"num": 4, "show": 20, "date": 12, "asr": 6, "deep": 6, "notion": 6}
    borders = 18
    title_w = max(30, term_width - sum(fixed.values()) - borders)

    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        title="🎙️ Episodes",
        expand=False,
        border_style=TABLE_BORDER_STYLE,
    )
    table.add_column("#", style=TABLE_NUM_STYLE, width=fixed["num"], justify="right", no_wrap=True)
    table.add_column("Show", style=TABLE_SHOW_STYLE, width=fixed["show"], no_wrap=True, overflow="ellipsis")
    table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed["date"], no_wrap=True)
    table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_w, no_wrap=True, overflow="ellipsis")
    table.add_column("ASR", style="white", width=fixed["asr"], no_wrap=True)
    table.add_column("Deep", style="white", width=fixed["deep"], no_wrap=True)
    table.add_column("Notion", style="white", width=fixed["notion"], no_wrap=True)

    for idx, r in enumerate(rows, start=1):
        table.add_row(str(idx), r["show"], r["date"], r["title"], r["asr"], r["deep"], r["notion"])
    console.print(table)


if __name__ == "__main__":
    main()


