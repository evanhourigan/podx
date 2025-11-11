"""Core Notion integration engine - pure business logic.

No UI dependencies, no CLI concerns. Just Notion API operations for publishing content.
"""

import os
import re
from typing import Any, Callable, Dict, List, Optional

from ..logging import get_logger

logger = get_logger(__name__)


class NotionError(Exception):
    """Raised when Notion operations fail."""

    pass


def chunk_rich_text(s: str, chunk: int = 1800) -> List[Dict[str, Any]]:
    """Chunk rich text to respect Notion's size limits."""
    for i in range(0, len(s), chunk):
        yield {"type": "text", "text": {"content": s[i : i + chunk]}}


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

        # Regular text
        else:
            next_special = len(text)
            for special in ["**", "*", "`"]:
                pos = text.find(special, i)
                if pos != -1 and pos < next_special:
                    next_special = pos

            if next_special == len(text):
                remaining_text = text[i:]
                if remaining_text:
                    rich_text.append(
                        {"type": "text", "text": {"content": remaining_text}}
                    )
                break
            else:
                text_before_special = text[i:next_special]
                if text_before_special:
                    rich_text.append(
                        {"type": "text", "text": {"content": text_before_special}}
                    )
                i = next_special

    if not rich_text:
        return [{"type": "text", "text": {"content": text}}]

    return rich_text


def md_to_blocks(md: str) -> List[Dict[str, Any]]:
    """Convert markdown to Notion blocks.

    Supports:
    - # ## ### headings
    - - * + bullets
    - 1. numbered lists
    - > quote
    - ``` code fences
    - --- divider
    - paragraphs
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
            heading_type = f"heading_{level}"
            blocks.append(
                {
                    "object": "block",
                    "type": heading_type,
                    heading_type: {"rich_text": parse_inline_markdown(text)},
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
            rich_text = parse_inline_markdown(line)
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


class NotionEngine:
    """Pure Notion API integration logic with no UI dependencies.

    Handles page creation, updates, markdown conversion, and content publishing.
    Can be used by CLI, TUI studio, web API, or any other interface.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize Notion engine.

        Args:
            api_token: Notion API token (defaults to NOTION_TOKEN env var)
            progress_callback: Optional callback for progress updates
        """
        self.api_token = api_token or os.getenv("NOTION_TOKEN")
        self.progress_callback = progress_callback

        if not self.api_token:
            raise NotionError(
                "Notion API token not found. Set NOTION_TOKEN environment variable."
            )

    def _report_progress(self, message: str):
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(message)

    def _get_client(self):
        """Get Notion client instance."""
        try:
            from notion_client import Client
        except ImportError:
            raise NotionError(
                "notion-client library not installed. Install with: pip install notion-client"
            )

        return Client(auth=self.api_token)

    def upsert_page(
        self,
        database_id: str,
        properties: Dict[str, Any],
        blocks: Optional[List[Dict[str, Any]]] = None,
        replace_content: bool = False,
        filter_properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create or update a Notion page.

        Args:
            database_id: Target Notion database ID
            properties: Page properties (title, date, etc.)
            blocks: Optional blocks to add to page body
            replace_content: If True, replace existing content; if False, append
            filter_properties: Properties to filter for existing pages

        Returns:
            Page ID of created/updated page

        Raises:
            NotionError: If operation fails
        """
        client = self._get_client()

        # Try to find existing page
        existing_page_id = None
        if filter_properties:
            try:
                self._report_progress("Searching for existing page")
                filters = filter_properties.get("filters", [])
                if filters:
                    q = client.databases.query(
                        database_id=database_id, filter={"and": filters}
                    )
                    if q.get("results"):
                        existing_page_id = q["results"][0]["id"]
            except Exception as e:
                logger.warning("Failed to query existing pages", error=str(e))

        if existing_page_id:
            # Update existing page
            self._report_progress("Updating existing page")
            try:
                client.pages.update(page_id=existing_page_id, properties=properties)
            except Exception as e:
                raise NotionError(f"Failed to update page properties: {e}") from e

            if blocks:
                try:
                    if replace_content:
                        self._clear_children(client, existing_page_id)

                    self._append_blocks(client, existing_page_id, blocks)
                except Exception as e:
                    raise NotionError(f"Failed to update page content: {e}") from e

            return existing_page_id
        else:
            # Create new page
            self._report_progress("Creating new page")
            try:
                if blocks and len(blocks) > 100:
                    # Handle chunking for large content
                    chunks = self._split_blocks(blocks)
                    resp = client.pages.create(
                        parent={"database_id": database_id},
                        properties=properties,
                        children=chunks[0],
                    )
                    page_id = resp["id"]

                    # Append remaining chunks
                    for chunk in chunks[1:]:
                        client.blocks.children.append(block_id=page_id, children=chunk)

                    return page_id
                else:
                    resp = client.pages.create(
                        parent={"database_id": database_id},
                        properties=properties,
                        children=blocks or [],
                    )
                    return resp["id"]
            except Exception as e:
                raise NotionError(f"Failed to create page: {e}") from e

    def _list_children_all(self, client, page_id: str) -> List[Dict[str, Any]]:
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

    def _clear_children(self, client, page_id: str) -> None:
        """Archive all existing children of a page."""
        children = self._list_children_all(client, page_id)

        for child in children:
            try:
                client.blocks.update(block_id=child["id"], archived=True)
            except Exception:
                pass

    def _append_blocks(self, client, page_id: str, blocks: List[Dict[str, Any]]):
        """Append blocks to a page, handling chunking."""
        if len(blocks) > 100:
            chunks = self._split_blocks(blocks)
            for chunk in chunks:
                client.blocks.children.append(block_id=page_id, children=chunk)
        else:
            client.blocks.children.append(block_id=page_id, children=blocks)

    def _split_blocks(self, blocks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split blocks into chunks that respect Notion's 100-block limit."""
        if len(blocks) <= 100:
            return [blocks]

        chunks = []
        current_chunk = []

        for block in blocks:
            current_chunk.append(block)

            if len(current_chunk) >= 100:
                chunks.append(current_chunk)
                current_chunk = []

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def set_page_cover(self, page_id: str, cover_url: str) -> None:
        """Set cover image for a Notion page.

        Args:
            page_id: Page ID to update
            cover_url: External image URL

        Raises:
            NotionError: If operation fails
        """
        client = self._get_client()

        try:
            client.pages.update(
                page_id=page_id,
                cover={"type": "external", "external": {"url": cover_url}},
            )
        except Exception as e:
            raise NotionError(f"Failed to set page cover: {e}") from e


# Convenience functions for direct use
def publish_to_notion(
    database_id: str,
    markdown: str,
    properties: Dict[str, Any],
    replace_content: bool = False,
    cover_url: Optional[str] = None,
    api_token: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Publish markdown content to Notion.

    Args:
        database_id: Target Notion database ID
        markdown: Markdown content to publish
        properties: Page properties (title, date, etc.)
        replace_content: Replace existing content vs append
        cover_url: Optional cover image URL
        api_token: Optional Notion API token
        progress_callback: Optional progress callback

    Returns:
        Page ID of created/updated page
    """
    engine = NotionEngine(api_token=api_token, progress_callback=progress_callback)

    # Convert markdown to blocks
    blocks = md_to_blocks(markdown)

    # Create/update page
    page_id = engine.upsert_page(
        database_id=database_id,
        properties=properties,
        blocks=blocks,
        replace_content=replace_content,
    )

    # Set cover if provided
    if cover_url:
        engine.set_page_cover(page_id, cover_url)

    return page_id
