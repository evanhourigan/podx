#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

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
                        "heading_1": {"rich_text": rt(text)},
                    }
                )
            elif level == 2:
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {"rich_text": rt(text)},
                    }
                )
            else:
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {"rich_text": rt(text)},
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
                    "quote": {"rich_text": rt(qm.group(1))},
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
                    "bulleted_list_item": {"rich_text": rt(bm.group(1))},
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
                    "numbered_list_item": {"rich_text": rt(nm.group(2))},
                }
            )
            continue

        # Paragraph / blank
        if not line.strip():
            blocks.append(
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}
            )
        else:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": list(chunk_rich_text(line))},
                }
            )

    if in_code:
        flush_code()

    return blocks


def upsert_page(
    client: Client,
    db_id: str,
    title: str,
    date_iso: Optional[str],
    title_prop: str = "Name",
    date_prop: str = "Date",
    props_extra: Optional[Dict[str, Any]] = None,
    blocks: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Try to find an existing page (by exact title and optionally date), else create.
    Returns the page ID.
    """
    # Query by title (Notion filter on Title property)
    filt = {"and": [{"property": title_prop, "title": {"equals": title}}]}

    if date_iso:
        filt["and"].append({"property": date_prop, "date": {"equals": date_iso}})

    q = client.databases.query(database_id=db_id, filter=filt)

    props = {title_prop: {"title": [{"type": "text", "text": {"content": title}}]}}
    if date_iso:
        props[date_prop] = {"date": {"start": date_iso}}

    if props_extra:
        props.update(props_extra)

    if q.get("results"):
        # Update existing page
        page_id = q["results"][0]["id"]
        client.pages.update(page_id=page_id, properties=props)

        if blocks is not None:
            # Notion doesn't support clearing children directly; we append for simplicity/safety
            # Could add a --replace flag that archives existing children first
            client.blocks.children.append(block_id=page_id, children=blocks)

        return page_id
    else:
        # Create new page
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
@click.option("--title", help="Page title (or derive from --meta)")
@click.option(
    "--date", "date_iso", help="ISO date (YYYY-MM-DD) (or derive from --meta)"
)
@click.option(
    "--markdown",
    "md_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Markdown file",
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
    "--title-prop",
    default=lambda: os.getenv("NOTION_TITLE_PROP", "Name"),
    help="Notion property name for title",
)
@click.option(
    "--date-prop",
    default=lambda: os.getenv("NOTION_DATE_PROP", "Date"),
    help="Notion property name for date",
)
@click.option(
    "--dry-run", is_flag=True, help="Parse and print Notion payload (don't write)"
)
def main(
    db_id: Optional[str],
    title: Optional[str],
    date_iso: Optional[str],
    md_path: Path,
    json_path: Optional[Path],
    meta_path: Optional[Path],
    title_prop: str,
    date_prop: str,
    dry_run: bool,
):
    """
    Create or update a Notion page from Markdown (+ optional JSON props).
    Upsert by Title (+ Date if provided).
    """
    if not db_id:
        raise SystemExit("Please pass --db or set NOTION_DB_ID environment variable")

    # Prefer explicit CLI title/date, else derive from meta JSON
    meta = {}
    if meta_path:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if not title:
        title = meta.get("episode_title") or meta.get("title") or "Podcast Notes"

    if not date_iso:
        d = meta.get("episode_published") or meta.get("date")
        if isinstance(d, str) and len(d) >= 10:
            date_iso = d[:10]  # YYYY-MM-DD from ISO datetime

    md = md_path.read_text(encoding="utf-8")
    blocks = md_to_blocks(md)

    # Extra Notion properties from JSON
    props_extra: Dict[str, Any] = {}
    if json_path:
        js = json.loads(json_path.read_text(encoding="utf-8"))
        # You can map structured fields to Notion properties here if desired.
        # Example: add a multi-select "Tags" from key_points (top 3)
        key_points = (js.get("key_points") or [])[:3]
        if key_points:
            props_extra["Tags"] = {
                "multi_select": [
                    {"name": kp[:50]} for kp in key_points
                ]  # Notion name limit
            }

    if dry_run:
        payload = {
            "db_id": db_id,
            "title_prop": title_prop,
            "date_prop": date_prop,
            "title": title,
            "date_iso": date_iso,
            "props_extra": props_extra,
            "blocks_preview": blocks[:3],  # First 3 blocks
            "blocks_count": len(blocks),
        }
        print(json.dumps(payload, indent=2))
        return

    client = notion_client_from_env()
    page_id = upsert_page(
        client=client,
        db_id=db_id,
        title=title,
        date_iso=date_iso,
        title_prop=title_prop,
        date_prop=date_prop,
        props_extra=props_extra,
        blocks=blocks,
    )

    print(json.dumps({"ok": True, "page_id": page_id}, indent=2))


if __name__ == "__main__":
    main()
