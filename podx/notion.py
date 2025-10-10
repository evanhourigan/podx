#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import requests

# Optional rich UI (similar feel to podx-browse)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _HAS_RICH = True
    _console = Console()
except Exception:  # pragma: no cover
    _HAS_RICH = False
    _console = None  # type: ignore

from .cli_shared import read_stdin_json
from .info import get_episode_workdir
from .yaml_config import get_yaml_config_manager
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
    from notion_client import Client
except ImportError:
    Client = None  # type: ignore


# utils
def notion_client_from_env() -> Client:
    if Client is None:
        raise SystemExit("Install notion-client: pip install notion-client")

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise SystemExit("Set NOTION_TOKEN environment variable")

    return Client(auth=token)


def chunk_rich_text(s: str, chunk: int = 1800) -> List[Dict[str, Any]]:
    # Notion has limits on rich_text length; be safe.
    for i in range(0, len(s), chunk):
        yield {"type": "text", "text": {"content": s[i : i + chunk]}}


def rt(s: str) -> List[Dict[str, Any]]:
    return [{"type": "text", "text": {"content": s}}]


def parse_inline_markdown(text: str) -> List[Dict[str, Any]]:
    """Parse inline markdown formatting (bold, italic, code) into Notion rich text objects."""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]

    rich_text = []
    i = 0

    while i < len(text):
        # Handle bold text: **text**
        if text[i : i + 2] == "**" and i + 2 < len(text):
            end_bold = text.find("**", i + 2)
            if end_bold != -1:
                rich_text.append(
                    {
                        "type": "text",
                        "text": {"content": text[i + 2 : end_bold]},
                        "annotations": {"bold": True},
                    }
                )
                i = end_bold + 2
                continue

        # Handle italic text: *text* (but not **)
        elif text[i] == "*" and i + 1 < len(text) and text[i : i + 2] != "**":
            end_italic = text.find("*", i + 1)
            # Make sure we don't match ** inside
            while (
                end_italic != -1
                and end_italic + 1 < len(text)
                and text[end_italic + 1] == "*"
            ):
                end_italic = text.find("*", end_italic + 2)
            if end_italic != -1:
                rich_text.append(
                    {
                        "type": "text",
                        "text": {"content": text[i + 1 : end_italic]},
                        "annotations": {"italic": True},
                    }
                )
                i = end_italic + 1
                continue

        # Handle code: `text`
        elif text[i] == "`" and i + 1 < len(text):
            end_code = text.find("`", i + 1)
            if end_code != -1:
                rich_text.append(
                    {
                        "type": "text",
                        "text": {"content": text[i + 1 : end_code]},
                        "annotations": {"code": True},
                    }
                )
                i = end_code + 1
                continue

        # Regular text - find next special character
        else:
            # Find the next special character
            next_special = len(text)
            for special in ["**", "*", "`"]:
                pos = text.find(special, i)
                if pos != -1 and pos < next_special:
                    next_special = pos

            if next_special == len(text):
                # No more special characters, add remaining text
                remaining_text = text[i:]
                if remaining_text:
                    rich_text.append(
                        {"type": "text", "text": {"content": remaining_text}}
                    )
                break
            else:
                # Add text up to next special character
                text_before_special = text[i:next_special]
                if text_before_special:
                    rich_text.append(
                        {"type": "text", "text": {"content": text_before_special}}
                    )
                i = next_special

    # If no rich text was created, return the original text
    if not rich_text:
        return [{"type": "text", "text": {"content": text}}]

    return rich_text


def _split_blocks_for_notion(
    blocks: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Split blocks into chunks that respect content boundaries and stay under 100 blocks."""
    if len(blocks) <= 100:
        return [blocks]

    chunks = []
    current_chunk = []

    for i, block in enumerate(blocks):
        current_chunk.append(block)

        # Check if we need to split
        if len(current_chunk) >= 100:
            # Find optimal split point
            optimal_split = _find_optimal_split_point(
                blocks, i - len(current_chunk) + 1, i + 1
            )

            # Split at the optimal point
            if optimal_split < len(current_chunk):
                # Create chunk up to optimal split point
                chunk = current_chunk[:optimal_split]
                chunks.append(chunk)

                # Start new chunk from optimal split point
                current_chunk = current_chunk[optimal_split:]
            else:
                # No good split point found, use current chunk
                chunks.append(current_chunk)
                current_chunk = []

    # Add any remaining blocks
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _find_optimal_split_point(
    blocks: List[Dict[str, Any]], start_pos: int, target_end: int
) -> int:
    """Find the optimal split point that keeps content together."""
    # Start from the target end and work backwards to find the best split
    best_split_pos = min(target_end, len(blocks))

    # Look within a reasonable range around the target
    search_start = max(start_pos, target_end - 50)  # Look back up to 50 blocks
    search_end = min(len(blocks), target_end + 10)  # Look forward up to 10 blocks

    for pos in range(search_start, search_end):
        if pos <= start_pos:
            continue

        # Check if this is a good split point
        if _is_optimal_split_point(blocks, pos):
            # Update best_split_pos only if this position is closer to target_end
            if abs(pos - target_end) < abs(best_split_pos - target_end):
                best_split_pos = pos

    return best_split_pos


def _is_optimal_split_point(blocks: List[Dict[str, Any]], pos: int) -> bool:
    """Check if a position is an optimal split point."""
    if pos >= len(blocks):
        return False

    current_block = blocks[pos]

    # If this is a heading, it's a great split point
    if current_block.get("type", "").startswith("heading"):
        return True

    # If this is a paragraph, analyze the content
    if current_block.get("type") == "paragraph":
        rich_text = current_block.get("paragraph", {}).get("rich_text", [])
        if rich_text and len(rich_text) > 0:
            content = rich_text[0].get("text", {}).get("content", "")

            # Check if this looks like a speaker label or section break
            is_section_break = any(
                marker in content.upper()
                for marker in ["##", "###", "SPEAKER", ":", "---"]
            )

            if is_section_break:
                return True

    return False


# -------------------------
# Interactive helpers (MVP)
# -------------------------


def _detect_shows(root: Path) -> List[str]:
    """Detect shows that already have deepcast analyses (actionable for Notion)."""
    shows: List[str] = []
    try:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            actionable = False
            for p in entry.iterdir():
                if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name):
                    # Check for both new and legacy deepcast formats
                    if list((entry / p.name).glob("deepcast-*.json")):
                        actionable = True
                        break
            if actionable:
                shows.append(entry.name)
    except FileNotFoundError:
        pass
    return sorted(shows, key=lambda s: s.lower())


def _list_episode_dates(root: Path, show: str) -> List[str]:
    """List episode dates for a show that have deepcast analyses, sorted desc."""
    dates: List[str] = []
    show_dir = root / show
    if not show_dir.exists():
        return dates
    for entry in show_dir.iterdir():
        if entry.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", entry.name):
            # Check for both new and legacy deepcast formats
            if list(entry.glob("deepcast-*.json")):
                dates.append(entry.name)
    # Newest first
    return sorted(dates, reverse=True)


def _list_deepcast_models(workdir: Path) -> List[str]:
    """List available deepcast models for an episode workdir based on filenames."""
    models: List[str] = []
    # Check for both new and legacy deepcast formats
    files = list(workdir.glob("deepcast-*.json"))
    for f in files:
        # Try to extract AI model from filename
        # New format: deepcast-{asr}-{ai}-{type}.json -> extract {ai}
        # Legacy format: deepcast-{ai}.json or deepcast-brief-{ai}.json -> extract {ai}
        stem = f.stem
        if stem.startswith("deepcast-brief-"):
            # Legacy: deepcast-brief-{ai}
            suffix = stem[len("deepcast-brief-"):].replace("_", ".")
            models.append(suffix)
        elif stem.count("-") >= 3:
            # New format: deepcast-{asr}-{ai}-{type}
            parts = stem.split("-")
            if len(parts) >= 3:
                ai_model = parts[2].replace("_", ".")
                if ai_model not in models:
                    models.append(ai_model)
        elif stem.startswith("deepcast-"):
            # Legacy: deepcast-{ai}
            suffix = stem[len("deepcast-"):].replace("_", ".")
            if suffix not in models:
                models.append(suffix)
    # Deduplicate and return unique models
    return list(dict.fromkeys(models))  # Preserve order while deduplicating


def _prompt_numbered_choice(title: str, items: List[str]) -> Optional[str]:
    """Prompt user to choose one item by number; supports q to quit and /filter.

    Uses Rich tables if available for a nicer UI similar to podx-browse.
    """
    current = list(items)
    filter_note = ""
    while True:
        # Clear screen before re-render to keep UI anchored
        try:
            if _HAS_RICH and _console is not None:
                _console.clear()
            else:
                click.clear()
        except Exception:
            pass

        if _HAS_RICH and _console is not None:
            tbl = Table(show_header=True, header_style="bold cyan", box=None)
            tbl.add_column("#", style="cyan dim", width=4)
            tbl.add_column(title + (f" {filter_note}" if filter_note else ""), style="white")
            for idx, item in enumerate(current, start=1):
                tbl.add_row(str(idx), item)
            _console.print(tbl)
            _console.print(
                Panel.fit("1-9 select  •  /text filter  •  q quit", style="dim")
            )
        else:
            click.echo("")
            click.echo(title + (f" {filter_note}" if filter_note else ""))
            for idx, item in enumerate(current, start=1):
                click.echo(f"  {idx}. {item}")
            click.echo("\nHelp: 1-9 select • /text filter • q quit")

        choice = click.prompt("Select", default="q", show_default=False)
        if isinstance(choice, str):
            s = choice.strip()
            if s.lower() == "q":
                return None
            if s.startswith("/"):
                term = s[1:].strip()
                if not term:
                    term = click.prompt(
                        "Filter contains", default="", show_default=False
                    )
                term_l = term.lower()
                current = [it for it in items if term_l in it.lower()]
                filter_note = f"(filtered: '{term}')" if term else ""
                if not current:
                    click.echo("No matches. Clearing filter.")
                    current = list(items)
                    filter_note = ""
                continue
        try:
            num = int(choice)
            if 1 <= num <= len(current):
                return current[num - 1]
        except (ValueError, TypeError):
            pass
        click.echo("Invalid selection. Try again.")


def _scan_notion_rows(scan_dir: Path) -> List[Dict[str, Any]]:
    """Scan for deepcast/consensus JSONs and build table rows: one per analysis file.

    Adds a 'type' field indicating consensus, precision, recall, or deepcast type.
    """
    def _format_date_ymd(s: Optional[str]) -> str:
        if not isinstance(s, str) or not s.strip():
            return "Unknown"
        # Try robust parsing first
        try:
            from dateutil import parser as dtparse  # type: ignore

            return dtparse.parse(s).date().isoformat()
        except Exception:
            pass
        # Fallback: extract first YYYY-MM-DD pattern
        m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            return m.group(1)
        # Last resort: take last 10 chars if they look like a date-ish token
        t = s.strip()
        return t[-10:] if len(t) >= 10 else t
    rows: List[Dict[str, Any]] = []
    # Helper to push a row from paths and metadata
    def add_row(episode_dir: Path, analysis_path: Path, ai: str, asr: str, kind: str, track: str):
        show = "Unknown"; title = "Unknown"; date = "Unknown"
        em = episode_dir / "episode-meta.json"
        if em.exists():
            try:
                emd = json.loads(em.read_text(encoding="utf-8"))
                show = emd.get("show", show)
                title = emd.get("episode_title", title)
                dval = emd.get("episode_published") or emd.get("date")
                date = _format_date_ymd(dval)
            except Exception:
                pass
        notion_done = (episode_dir / "notion.out.json").exists()
        rows.append({
            "path": analysis_path,
            "dir": episode_dir,
            "show": show,
            "date": date,
            "title": title,
            "ai": ai,
            "asr": asr,
            "type": kind,
            "track": track,
            "notion": notion_done,
        })

    # Deepcast analyses
    for analysis_file in scan_dir.rglob("deepcast-*.json"):
        try:
            data = json.loads(analysis_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = data.get("deepcast_metadata", {})
        ai = meta.get("model", "unknown")
        asr = meta.get("asr_model", "unknown")
        # Determine kind: deepcast type or precision/recall from filename suffix
        kind = meta.get("deepcast_type") or ""
        stem = analysis_file.stem
        track = "S"  # Single by default
        if stem.endswith("-precision"):
            track = "P"
        elif stem.endswith("-recall"):
            track = "R"
        if not kind:
            kind = "general"
        add_row(analysis_file.parent, analysis_file, ai, asr, kind, track)

    # Consensus analyses
    for analysis_file in scan_dir.rglob("consensus-*.json"):
        try:
            data = json.loads(analysis_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = data.get("consensus_metadata", {})
        ai = meta.get("ai_model", "unknown")
        asr = meta.get("asr_model", "unknown")
        dc_type = meta.get("deepcast_type") or "general"
        add_row(analysis_file.parent, analysis_file, ai, asr, dc_type, "C")

    # Sort newest first by directory date and file mtime
    rows.sort(key=lambda r: (r["date"], r["path"].stat().st_mtime), reverse=True)
    return rows


def _interactive_table_flow(db_id: Optional[str], scan_dir: Path) -> Optional[Dict[str, Any]]:
    console = make_console()
    rows = _scan_notion_rows(scan_dir)
    # Promote consensus rows to the top order within same episode (show+date+title)
    rows.sort(key=lambda r: (r["show"], r["date"], r["title"], 0 if r.get("type") == "consensus" else 1, r["path"].stat().st_mtime), reverse=True)
    if not rows:
        console.print(f"[red]No deepcast files found in {scan_dir}[/red]")
        return None

    # Column widths with flexible Title
    term_width = console.size.width
    fixed = {"num": 4, "show": 20, "date": 12, "ai": 14, "asr": 14, "type": 18, "trk": 6, "rec": 4, "notion": 8}
    borders = 20
    title_w = max(30, term_width - sum(fixed.values()) - borders)

    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        title="🪄 Select an analysis to upload to Notion",
        expand=False,
        border_style=TABLE_BORDER_STYLE,
    )
    table.add_column("#", style=TABLE_NUM_STYLE, width=fixed["num"], justify="right", no_wrap=True)
    table.add_column("Show", style=TABLE_SHOW_STYLE, width=fixed["show"], no_wrap=True, overflow="ellipsis")
    table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed["date"], no_wrap=True)
    table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_w, no_wrap=True, overflow="ellipsis")
    table.add_column("AI", style="green", width=fixed["ai"], no_wrap=True, overflow="ellipsis")
    table.add_column("ASR", style="yellow", width=fixed["asr"], no_wrap=True, overflow="ellipsis")
    table.add_column("Type", style="white", width=fixed["type"], no_wrap=True, overflow="ellipsis")
    table.add_column("Trk", style="white", width=fixed["trk"], no_wrap=True)
    table.add_column("Rec", style="white", width=fixed["rec"], no_wrap=True)
    table.add_column("Notion", style="white", width=fixed["notion"], no_wrap=True)

    # Sort to prefer consensus at top for the same episode
    for idx, r in enumerate(rows, start=1):
        table.add_row(
            str(idx), r["show"], r["date"], r["title"], r["ai"], r["asr"], r.get("type", ""), r.get("track", ""), ("✓" if r.get("track") == "C" else "-"), "✓" if r["notion"] else "-",
        )
    console.print(table)
    console.print("\n[dim]Enter selection number, or Q to cancel.[/dim]")
    ans = input(f"👉 1-{len(rows)}: ").strip().upper()
    if ans in {"Q", "QUIT", "EXIT"}:
        return None
    try:
        i = int(ans)
        if not (1 <= i <= len(rows)):
            raise ValueError
    except Exception:
        console.print("[red]Invalid selection[/red]")
        return None

    chosen = rows[i - 1]

    # DB prompt with YAML presets if available
    default_db = db_id or os.getenv("NOTION_DB_ID", "")
    preset_db = None
    try:
        mgr = get_yaml_config_manager()
        dbs = mgr.list_notion_databases()
    except Exception:
        dbs = {}
    if dbs:
        names = list(dbs.keys())
        console.print("\n[bold]Select Notion database:[/bold]")
        for i, name in enumerate(names, start=1):
            console.print(f"  {i}. {name}")
        console.print(f"  0. Enter ID manually{' (default)' if default_db else ''}")
        sel = input("Choice [0-{}]: ".format(len(names))).strip()
        if sel.isdigit() and int(sel) in range(1, len(names) + 1):
            preset = dbs[names[int(sel) - 1]]
            db_val = preset.database_id
        else:
            manual = input(f"Notion DB ID [{default_db}]: ").strip()
            db_val = manual or default_db
    else:
        db_val = input(f"Notion DB ID [{default_db}]: ").strip() if _HAS_RICH else click.prompt("Notion DB ID", default=default_db, show_default=bool(default_db))
        if not db_val:
            db_val = default_db
    if not db_val:
        console.print("[red]Database ID required[/red]")
        return None

    # Dry run toggle
    dry = input("Dry-run first? (y/N): ").strip().lower() if _HAS_RICH else click.prompt("Dry-run first? (y/N)", default="N")
    dry_run = str(dry).lower() in {"y", "yes"}

    # Cover image toggle
    cov = input("Set cover image if available? (y/N): ").strip().lower()
    cover = cov in {"y", "yes"}

    return {"db_id": db_val, "input_path": chosen["path"], "meta_path": chosen["dir"] / "episode-meta.json", "dry_run": dry_run, "cover": cover}


def md_to_blocks(md: str) -> List[Dict[str, Any]]:
    """
    Very small, block-level Markdown → Notion converter:
    - # ## ### headings
    - - * + bullets
    - 1. numbered lists
    - > quote
    - ``` code fences
    - --- divider
    - paragraphs

    Inline bold/italic are left as plain text (keeps this simple & robust).
    """
    lines = md.replace("\r\n", "\n").split("\n")
    blocks: List[Dict[str, Any]] = []
    in_code = False
    code_buf: List[str] = []

    def flush_code():
        nonlocal code_buf
        if code_buf:
            code_text = "\n".join(code_buf)
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": list(chunk_rich_text(code_text)),
                    },
                }
            )
            code_buf = []

    for raw in lines:
        line = raw.rstrip()

        # Code fence
        if line.strip().startswith("```"):
            if in_code:
                in_code = False
                flush_code()
            else:
                in_code = True
                code_buf = []
            continue

        if in_code:
            code_buf.append(line)
            continue

        # Divider
        if re.match(r"^\s*[-*_]{3,}\s*$", line):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            continue

        # Headings
        m = re.match(r"^(\#{1,3})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_1",
                        "heading_1": {"rich_text": parse_inline_markdown(text)},
                    }
                )
            elif level == 2:
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {"rich_text": parse_inline_markdown(text)},
                    }
                )
            else:
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {"rich_text": parse_inline_markdown(text)},
                    }
                )
            continue

        # Quote
        qm = re.match(r"^\s*>\s*(.+)$", line)
        if qm:
            blocks.append(
                {
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": parse_inline_markdown(qm.group(1))},
                }
            )
            continue

        # Bulleted list
        bm = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if bm:
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": parse_inline_markdown(bm.group(1))
                    },
                }
            )
            continue

        # Numbered list
        nm = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
        if nm:
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": parse_inline_markdown(nm.group(2))
                    },
                }
            )
            continue

        # Paragraph / blank
        if not line.strip():
            blocks.append(
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}
            )
        else:
            # Parse inline formatting and handle long text
            rich_text = parse_inline_markdown(line)
            # If text is very long, we might need to chunk it
            # For now, just use the parsed rich text directly
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text},
                }
            )

    if in_code:
        flush_code()

    return blocks


def _list_children_all(client: Client, page_id: str) -> List[Dict[str, Any]]:
    """List all children of a page, handling pagination."""
    all_children = []
    start_cursor = None

    while True:
        resp = client.blocks.children.list(
            block_id=page_id, start_cursor=start_cursor, page_size=100
        )
        all_children.extend(resp.get("results", []))

        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")

    return all_children


def _clear_children(client: Client, page_id: str) -> None:
    """Archive all existing children of a page."""
    children = _list_children_all(client, page_id)

    for child in children:
        try:
            client.blocks.update(block_id=child["id"], archived=True)
        except Exception:
            # Continue on non-fatal errors
            pass


def _download_cover_image(image_url: str, workdir: Path) -> Optional[str]:
    """Download cover image and return the local file path."""
    if not image_url:
        return None

    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # Determine file extension from content type or URL
        content_type = response.headers.get("content-type", "")
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        else:
            # Fallback to URL extension
            ext = Path(image_url).suffix or ".jpg"

        cover_path = workdir / f"cover{ext}"
        cover_path.write_bytes(response.content)
        return str(cover_path)
    except Exception:
        # If download fails, continue without cover
        return None


def _set_page_cover(client: Client, page_id: str, cover_url: str) -> None:
    """Set the cover image for a Notion page using external URL."""
    try:
        client.pages.update(
            page_id=page_id, cover={"type": "external", "external": {"url": cover_url}}
        )
    except Exception:
        # If cover setting fails, continue without cover
        pass


def upsert_page(
    client: Client,
    db_id: str,
    podcast_name: str,
    episode_title: str,
    date_iso: Optional[str],
    podcast_prop: str = "Podcast",
    episode_prop: str = "Episode",
    date_prop: str = "Date",
    model_prop: str = "Model",
    asr_prop: str = "ASR Model",
    deepcast_model: Optional[str] = None,
    asr_model: Optional[str] = None,
    props_extra: Optional[Dict[str, Any]] = None,
    blocks: Optional[List[Dict[str, Any]]] = None,
    replace_content: bool = False,
) -> str:
    """
    Try to find an existing page (by podcast name, episode title and optionally date), else create.
    Returns the page ID.
    """
    # Query by episode title and model (to allow multiple analyses per episode)
    filt = {"and": [{"property": episode_prop, "rich_text": {"equals": episode_title}}]}

    if date_iso:
        filt["and"].append({"property": date_prop, "date": {"equals": date_iso}})

    # Include model in the filter to allow separate rows for different models
    if deepcast_model and model_prop:
        filt["and"].append(
            {"property": model_prop, "rich_text": {"equals": deepcast_model}}
        )

    q = client.databases.query(database_id=db_id, filter=filt)

    props = {
        podcast_prop: {"title": [{"type": "text", "text": {"content": podcast_name}}]},
        episode_prop: {
            "rich_text": [{"type": "text", "text": {"content": episode_title}}]
        },
    }
    if date_iso:
        props[date_prop] = {"date": {"start": date_iso}}

    if deepcast_model and model_prop:
        props[model_prop] = {
            "rich_text": [{"type": "text", "text": {"content": deepcast_model}}]
        }

    if asr_model and asr_prop:
        props[asr_prop] = {
            "rich_text": [{"type": "text", "text": {"content": asr_model}}]
        }

    if props_extra:
        props.update(props_extra)

    if q.get("results"):
        # Update existing page
        page_id = q["results"][0]["id"]
        client.pages.update(page_id=page_id, properties=props)

        if blocks is not None:
            if replace_content:
                _clear_children(client, page_id)

            # Handle chunking for large block lists
            if len(blocks) > 100:
                chunks = _split_blocks_for_notion(blocks)
                for chunk in chunks:
                    client.blocks.children.append(block_id=page_id, children=chunk)
            else:
                client.blocks.children.append(block_id=page_id, children=blocks)

        return page_id
    else:
        # Create new page
        if blocks and len(blocks) > 100:
            # Handle chunking for large block lists
            chunks = _split_blocks_for_notion(blocks)

            # Create page with first chunk
            resp = client.pages.create(
                parent={"database_id": db_id}, properties=props, children=chunks[0]
            )
            page_id = resp["id"]

            # Append remaining chunks
            for chunk in chunks[1:]:
                client.blocks.children.append(block_id=page_id, children=chunk)

            return page_id
        else:
            # Small content, create normally
            resp = client.pages.create(
                parent={"database_id": db_id}, properties=props, children=blocks or []
            )
            return resp["id"]


@click.command()
@click.option(
    "--db",
    "db_id",
    default=lambda: os.getenv("NOTION_DB_ID"),
    help="Target Notion database ID",
)
@click.option(
    "--show", help="Podcast show name (auto-detect workdir, files, and models)"
)
@click.option(
    "--episode-date",
    help="Episode date YYYY-MM-DD (auto-detect workdir, files, and models)",
)
@click.option(
    "--select-model",
    help="If multiple deepcast models exist, specify which to use (e.g., 'gpt-4.1')",
)
@click.option("--title", help="Page title (or derive from --meta)")
@click.option(
    "--date", "date_iso", help="ISO date (YYYY-MM-DD) (or derive from --meta)"
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read DeepcastBrief JSON from file instead of stdin",
)
@click.option(
    "--markdown",
    "md_path",
    type=click.Path(exists=True, path_type=Path),
    help="Markdown file (alternative to --input)",
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(exists=True, path_type=Path),
    help="Structured JSON for extra Notion properties",
)
@click.option(
    "--meta",
    "meta_path",
    type=click.Path(exists=True, path_type=Path),
    help="Episode metadata JSON (to derive title/date)",
)
@click.option(
    "--podcast-prop",
    default=lambda: os.getenv("NOTION_PODCAST_PROP", "Podcast"),
    help="Notion property name for podcast name",
)
@click.option(
    "--date-prop",
    default=lambda: os.getenv("NOTION_DATE_PROP", "Date"),
    help="Notion property name for date",
)
@click.option(
    "--episode-prop",
    default=lambda: os.getenv("NOTION_EPISODE_PROP", "Episode"),
    help="Notion property name for episode title",
)
@click.option(
    "--model-prop",
    default="Model",
    help="Notion property name for deepcast model",
)
@click.option(
    "--asr-prop",
    default="ASR Model",
    help="Notion property name for ASR model",
)
@click.option(
    "--deepcast-model",
    help="Deepcast model name to store in Notion",
)
@click.option(
    "--asr-model",
    help="ASR model name to store in Notion",
)
@click.option(
    "--append-content",
    is_flag=True,
    help="Append to page body in Notion instead of replacing (default: replace)",
)
@click.option(
    "--cover-image",
    is_flag=True,
    help="Set podcast artwork as page cover (requires image_url in meta)",
)
@click.option(
    "--dry-run", is_flag=True, help="Parse and print Notion payload (don't write)"
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive selection flow (show → date → model → run)",
)
def main(
    db_id: Optional[str],
    show: Optional[str],
    episode_date: Optional[str],
    select_model: Optional[str],
    title: Optional[str],
    date_iso: Optional[str],
    input: Optional[Path],
    md_path: Optional[Path],
    json_path: Optional[Path],
    meta_path: Optional[Path],
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    model_prop: str,
    asr_prop: str,
    deepcast_model: Optional[str],
    asr_model: Optional[str],
    append_content: bool,
    cover_image: bool,
    dry_run: bool,
    interactive: bool,
):
    """
    Create or update a Notion page from Markdown (+ optional JSON props).
    Upsert by Title (+ Date if provided).
    """

    # Interactive table flow
    if interactive:
        params = _interactive_table_flow(db_id, Path.cwd())
        if not params:
            return

        # Inject selected parameters
        db_id = params["db_id"]
        input = params["input_path"]
        meta_path = params.get("meta_path")
        dry_run = params["dry_run"]
        cover_image = params.get("cover", cover_image)

    # Auto-detect workdir and files if --show and --episode-date provided
    if show and episode_date:
        workdir = get_episode_workdir(show, episode_date)
        if not workdir.exists():
            raise SystemExit(f"Episode directory not found: {workdir}")

        # Auto-detect the most recent deepcast analysis if not specified
        if not input and not md_path:
            # Check for both new and legacy deepcast formats
            deepcast_files = list(workdir.glob("deepcast-*.json"))
            if deepcast_files:
                if select_model:
                    # Filter for specific model
                    model_suffix = select_model.replace(".", "_").replace("-", "_")
                    matching_files = [
                        f for f in deepcast_files if f.stem.endswith(f"-{model_suffix}")
                    ]
                    if matching_files:
                        # Sort by modification time, newest first
                        input = max(matching_files, key=lambda p: p.stat().st_mtime)
                        click.echo(
                            f"📄 Selected deepcast file for {select_model}: {input.name}"
                        )
                    else:
                        available_models = [
                            f.stem.split("-")[-1].replace("_", ".")
                            for f in deepcast_files
                        ]
                        raise SystemExit(
                            f"No deepcast analysis found for model '{select_model}'. Available: {', '.join(set(available_models))}"
                        )
                else:
                    # Sort by modification time, newest first
                    input = max(deepcast_files, key=lambda p: p.stat().st_mtime)
                    model_from_filename = input.stem.split("-")[-1].replace("_", ".")
                    click.echo(
                        f"📄 Auto-detected deepcast file: {input.name} (model: {model_from_filename})"
                    )
                    if len(deepcast_files) > 1:
                        available_models = [
                            f.stem.split("-")[-1].replace("_", ".")
                            for f in deepcast_files
                        ]
                        click.echo(
                            f"💡 Multiple models available: {', '.join(set(available_models))}. Use --select-model to choose."
                        )
            else:
                raise SystemExit(f"No deepcast analysis found in {workdir}")

        # Auto-detect meta file if not specified
        if not meta_path:
            episode_meta = workdir / "episode-meta.json"
            if episode_meta.exists():
                meta_path = episode_meta
                click.echo(f"📋 Auto-detected metadata: {episode_meta.name}")

        # Auto-detect models from files if not specified
        if input and not deepcast_model:
            try:
                deepcast_data = json.loads(input.read_text())
                auto_deepcast_model = deepcast_data.get("deepcast_metadata", {}).get(
                    "model"
                )
                if auto_deepcast_model:
                    deepcast_model = auto_deepcast_model
                    click.echo(f"🤖 Auto-detected deepcast model: {deepcast_model}")
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        if not asr_model:
            transcript_file = workdir / "transcript.json"
            if transcript_file.exists():
                try:
                    transcript_data = json.loads(transcript_file.read_text())
                    auto_asr_model = transcript_data.get("asr_model")
                    if auto_asr_model:
                        asr_model = auto_asr_model
                        click.echo(f"🎤 Auto-detected ASR model: {asr_model}")
                except (json.JSONDecodeError, FileNotFoundError):
                    pass

    if not db_id:
        raise SystemExit("Please pass --db or set NOTION_DB_ID environment variable")

    # Handle input modes: --input (from stdin/file) vs separate files
    if input:
        # Read DeepcastBrief JSON from file
        deepcast_data = json.loads(input.read_text(encoding="utf-8"))
    elif not md_path:
        # Read DeepcastBrief JSON from stdin
        deepcast_data = read_stdin_json()
    else:
        # Traditional separate files mode
        deepcast_data = None

    if deepcast_data:
        # Extract data from DeepcastBrief JSON
        md = deepcast_data.get("markdown", "")
        if not md:
            raise SystemExit("DeepcastBrief JSON must contain 'markdown' field")

        # Extract metadata if available
        meta = deepcast_data.get("metadata", {})

        # Merge episode metadata if available (from smart detection)
        if meta_path and meta_path.exists():
            episode_meta = json.loads(meta_path.read_text())
            # Merge episode metadata with transcript metadata, episode takes priority
            meta = {**meta, **episode_meta}

        # Extract structured data for Notion properties
        js = deepcast_data  # The whole deepcast output
    else:
        # Traditional mode: separate files
        if not md_path:
            raise SystemExit(
                "Either provide --input (for DeepcastBrief JSON) or --markdown (for separate files)"
            )

        # Prefer explicit CLI title/date, else derive from meta JSON
        meta = {}
        if meta_path:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        md = md_path.read_text(encoding="utf-8")

        # Extra Notion properties from JSON
        js = {}
        if json_path:
            js = json.loads(json_path.read_text(encoding="utf-8"))

    # Derive podcast name, episode title and date
    podcast_name = meta.get("show") or "Unknown Podcast"
    if not title:
        title = meta.get("episode_title") or meta.get("title") or "Podcast Notes"
    episode_title = title

    # Auto-detect deepcast model from available data if not provided via CLI
    if not deepcast_model:
        # Try to extract from deepcast metadata in meta (from unified JSON)
        if hasattr(meta, "get") and meta.get("deepcast_metadata"):
            auto_deepcast_model = meta["deepcast_metadata"].get("model")
            if auto_deepcast_model:
                deepcast_model = auto_deepcast_model
                click.echo(f"🤖 Auto-detected deepcast model: {deepcast_model}")
        # Try to extract from separate JSON properties file
        elif hasattr(js, "get") and js.get("deepcast_metadata"):
            auto_deepcast_model = js["deepcast_metadata"].get("model")
            if auto_deepcast_model:
                deepcast_model = auto_deepcast_model
                click.echo(f"🤖 Auto-detected deepcast model: {deepcast_model}")

    # Extract ASR model if not provided via CLI
    if not asr_model:
        # First try deepcast metadata (preferred source)
        if hasattr(js, "get") and js.get("deepcast_metadata"):
            auto_asr_model = js["deepcast_metadata"].get("asr_model")
            if auto_asr_model:
                asr_model = auto_asr_model
                click.echo(f"🎤 Auto-detected ASR model from deepcast: {asr_model}")

        # Fallback to original transcript metadata
        if not asr_model and hasattr(meta, "get"):
            asr_model = meta.get("asr_model")

        # Last resort: try loading transcript.json from same directory
        if not asr_model and meta_path:
            transcript_path = meta_path.parent / "transcript.json"
            if transcript_path.exists():
                try:
                    transcript_data = json.loads(transcript_path.read_text())
                    asr_model = transcript_data.get("asr_model")
                    if asr_model:
                        click.echo(
                            f"🎤 Auto-detected ASR model from transcript: {asr_model}"
                        )
                except (json.JSONDecodeError, FileNotFoundError):
                    pass

    if not date_iso:
        d = meta.get("episode_published") or meta.get("date")
        if isinstance(d, str):
            # Handle different date formats
            try:
                from datetime import datetime

                # Try parsing RFC 2822 format (e.g., "Wed, 11 Jun 2025 14:18:45 +0000")
                if "," in d and len(d) > 20:
                    # Try with UTC offset format first
                    try:
                        dt = datetime.strptime(d, "%a, %d %b %Y %H:%M:%S %z")
                        date_iso = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        # Fallback to timezone name format (e.g., GMT)
                        dt = datetime.strptime(d, "%a, %d %b %Y %H:%M:%S %Z")
                        date_iso = dt.strftime("%Y-%m-%d")
                # Try ISO format
                elif len(d) >= 10:
                    date_iso = d[:10]  # YYYY-MM-DD from ISO datetime
            except ValueError:
                # Fallback: try to extract YYYY-MM-DD pattern
                if len(d) >= 10:
                    date_iso = d[:10]

    blocks = md_to_blocks(md)

    # Extra Notion properties from JSON
    props_extra: Dict[str, Any] = {}
    if js:
        # Generate meaningful tags from episode metadata and analysis
        tags = []

        # Add model information as tags
        deepcast_meta = js.get("deepcast_metadata", {})
        if deepcast_meta.get("model"):
            tags.append(f"AI-{deepcast_meta['model']}")
        if deepcast_meta.get("asr_model"):
            tags.append(f"ASR-{deepcast_meta['asr_model']}")

        # Add podcast type if available
        podcast_type = deepcast_meta.get("podcast_type")
        if podcast_type and podcast_type != "general":
            tags.append(f"Type-{podcast_type}")

        # Extract technology/topic keywords from key points (limit to avoid clutter)
        key_points = (js.get("key_points") or [])[:5]
        tech_keywords = set()

        # Common technology terms to extract as tags
        tech_terms = [
            "AI",
            "machine learning",
            "ChatGPT",
            "Claude",
            "OpenAI",
            "agents",
            "automation",
            "engineering",
            "coding",
            "development",
            "API",
            "workflow",
            "productivity",
            "software",
            "platform",
            "tool",
            "framework",
            "algorithm",
            "model",
            "data",
            "Python",
            "JavaScript",
            "React",
            "Node",
            "Docker",
            "cloud",
            "AWS",
            "database",
        ]

        for kp in key_points:
            for term in tech_terms:
                if term.lower() in kp.lower() and len(tech_keywords) < 3:
                    tech_keywords.add(term)

        # Add technology tags
        for tech in tech_keywords:
            tags.append(tech)

        # Convert to Notion format
        if tags:
            cleaned_tags = []
            for tag in tags[:6]:  # Limit to 6 tags total
                clean_tag = (
                    tag.replace(",", "").replace(".", "").replace(";", "")[:50].strip()
                )
                if clean_tag:
                    cleaned_tags.append({"name": clean_tag})

            if cleaned_tags:
                props_extra["Tags"] = {"multi_select": cleaned_tags}

    # Handle cover image
    cover_url = None
    if cover_image and meta:
        cover_url = (
            meta.get("image_url") or meta.get("artwork_url") or meta.get("cover_url")
        )

    if dry_run:
        payload = {
            "db_id": db_id,
            "podcast_prop": podcast_prop,
            "episode_prop": episode_prop,
            "date_prop": date_prop,
            "podcast_name": podcast_name,
            "episode_title": episode_title,
            "date_iso": date_iso,
            "replace_content": not append_content,
            "cover_image": cover_url is not None,
            "cover_url": cover_url,
            "props_extra_keys": list(props_extra.keys()) if props_extra else [],
            "blocks_count": len(blocks),
        }
        print(json.dumps(payload, indent=2))
        return

    client = notion_client_from_env()
    page_id = upsert_page(
        client=client,
        db_id=db_id,
        podcast_name=podcast_name,
        episode_title=episode_title,
        date_iso=date_iso,
        podcast_prop=podcast_prop,
        episode_prop=episode_prop,
        date_prop=date_prop,
        model_prop=model_prop,
        asr_prop=asr_prop,
        deepcast_model=deepcast_model,
        asr_model=asr_model,
        props_extra=props_extra,
        blocks=blocks,
        replace_content=not append_content,
    )

    # Set cover image if requested and available
    if cover_url:
        _set_page_cover(client, page_id, cover_url)

    print(json.dumps({"ok": True, "page_id": page_id}, indent=2))


if __name__ == "__main__":
    main()
