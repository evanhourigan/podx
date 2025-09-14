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

from .cli_shared import read_stdin_json

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
    props_extra: Optional[Dict[str, Any]] = None,
    blocks: Optional[List[Dict[str, Any]]] = None,
    replace_content: bool = False,
) -> str:
    """
    Try to find an existing page (by podcast name, episode title and optionally date), else create.
    Returns the page ID.
    """
    # Query by episode title (Notion filter on Episode property)
    filt = {"and": [{"property": episode_prop, "rich_text": {"equals": episode_title}}]}

    if date_iso:
        filt["and"].append({"property": date_prop, "date": {"equals": date_iso}})

    q = client.databases.query(database_id=db_id, filter=filt)

    props = {
        podcast_prop: {"title": [{"type": "text", "text": {"content": podcast_name}}]},
        episode_prop: {
            "rich_text": [{"type": "text", "text": {"content": episode_title}}]
        },
    }
    if date_iso:
        props[date_prop] = {"date": {"start": date_iso}}

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
def main(
    db_id: Optional[str],
    title: Optional[str],
    date_iso: Optional[str],
    input: Optional[Path],
    md_path: Optional[Path],
    json_path: Optional[Path],
    meta_path: Optional[Path],
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    append_content: bool,
    cover_image: bool,
    dry_run: bool,
):
    """
    Create or update a Notion page from Markdown (+ optional JSON props).
    Upsert by Title (+ Date if provided).
    """
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

    if not date_iso:
        d = meta.get("episode_published") or meta.get("date")
        if isinstance(d, str):
            # Handle different date formats
            try:
                from datetime import datetime

                # Try parsing RFC 2822 format (e.g., "Sun, 17 Aug 2025 11:03:01 GMT")
                if "," in d and len(d) > 20:
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
        # You can map structured fields to Notion properties here if desired.
        # Example: add a multi-select "Tags" from key_points (top 3)
        key_points = (js.get("key_points") or [])[:3]
        if key_points:
            props_extra["Tags"] = {
                "multi_select": [
                    {"name": kp[:50]} for kp in key_points
                ]  # Notion name limit
            }

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
