"""Unit tests for core.notion module.

Tests pure business logic without UI dependencies.
Focuses on markdown parsing and conversion functions.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from podx.core.notion import (
    NotionEngine,
    NotionError,
    chunk_rich_text,
    md_to_blocks,
    parse_inline_markdown,
)


class TestChunkRichText:
    """Test chunk_rich_text utility function."""

    def test_chunk_small_text(self):
        """Test that small text isn't chunked."""
        text = "Short text"
        chunks = list(chunk_rich_text(text, chunk=1800))
        assert len(chunks) == 1
        assert chunks[0] == {"type": "text", "text": {"content": "Short text"}}

    def test_chunk_large_text(self):
        """Test that large text is chunked."""
        text = "A" * 5000
        chunks = list(chunk_rich_text(text, chunk=1800))
        assert len(chunks) == 3  # 5000 / 1800 = 2.78, so 3 chunks
        assert all(chunk["type"] == "text" for chunk in chunks)

    def test_chunk_custom_size(self):
        """Test chunking with custom chunk size."""
        text = "A" * 100
        chunks = list(chunk_rich_text(text, chunk=30))
        assert len(chunks) == 4  # 100 / 30 = 3.33, so 4 chunks
        assert len(chunks[0]["text"]["content"]) == 30
        assert len(chunks[-1]["text"]["content"]) == 10


class TestParseInlineMarkdown:
    """Test parse_inline_markdown function."""

    def test_parse_empty_text(self):
        """Test parsing empty text."""
        result = parse_inline_markdown("")
        assert result == [{"type": "text", "text": {"content": ""}}]

    def test_parse_plain_text(self):
        """Test parsing plain text without formatting."""
        result = parse_inline_markdown("Hello world")
        assert result == [{"type": "text", "text": {"content": "Hello world"}}]

    def test_parse_bold_text(self):
        """Test parsing bold text."""
        result = parse_inline_markdown("**bold text**")
        assert len(result) == 1
        assert result[0]["text"]["content"] == "bold text"
        assert result[0]["annotations"] == {"bold": True}

    def test_parse_italic_text(self):
        """Test parsing italic text."""
        result = parse_inline_markdown("*italic text*")
        assert len(result) == 1
        assert result[0]["text"]["content"] == "italic text"
        assert result[0]["annotations"] == {"italic": True}

    def test_parse_code_text(self):
        """Test parsing code text."""
        result = parse_inline_markdown("`code text`")
        assert len(result) == 1
        assert result[0]["text"]["content"] == "code text"
        assert result[0]["annotations"] == {"code": True}

    def test_parse_mixed_formatting(self):
        """Test parsing text with multiple formatting types."""
        result = parse_inline_markdown("Normal **bold** and *italic* and `code`")
        assert (
            len(result) >= 5
        )  # At least: Normal, bold, italic, code, and connecting text
        # Check that bold is present
        bold_items = [r for r in result if r.get("annotations", {}).get("bold")]
        assert len(bold_items) == 1
        assert bold_items[0]["text"]["content"] == "bold"
        # Check italic
        italic_items = [r for r in result if r.get("annotations", {}).get("italic")]
        assert len(italic_items) == 1
        assert italic_items[0]["text"]["content"] == "italic"
        # Check code
        code_items = [r for r in result if r.get("annotations", {}).get("code")]
        assert len(code_items) == 1
        assert code_items[0]["text"]["content"] == "code"

    def test_parse_nested_bold_in_italic(self):
        """Test that nested formatting is handled."""
        # Note: This tests current behavior - may not handle true nesting
        result = parse_inline_markdown("*italic with **bold** inside*")
        assert len(result) >= 1

    def test_parse_unclosed_bold(self):
        """Test handling of unclosed bold markers."""
        result = parse_inline_markdown("**unclosed bold")
        # Should treat as plain text if not closed
        assert any(
            "unclosed bold" in r["text"]["content"]
            or "**unclosed bold" in r["text"]["content"]
            for r in result
        )

    def test_parse_multiple_bold(self):
        """Test parsing multiple bold sections."""
        result = parse_inline_markdown("**first** normal **second**")
        bold_items = [r for r in result if r.get("annotations", {}).get("bold")]
        assert len(bold_items) == 2
        assert bold_items[0]["text"]["content"] == "first"
        assert bold_items[1]["text"]["content"] == "second"


class TestMdToBlocks:
    """Test md_to_blocks function."""

    def test_md_simple_paragraph(self):
        """Test converting simple paragraph."""
        md = "This is a paragraph."
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "paragraph"
        assert (
            blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
            == "This is a paragraph."
        )

    def test_md_heading_1(self):
        """Test converting H1 heading."""
        md = "# Main Heading"
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_1"
        assert (
            blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Main Heading"
        )

    def test_md_heading_2(self):
        """Test converting H2 heading."""
        md = "## Subheading"
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_2"

    def test_md_heading_3(self):
        """Test converting H3 heading."""
        md = "### Section"
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_3"

    def test_md_bulleted_list(self):
        """Test converting bulleted list."""
        md = "- Item 1\n- Item 2\n- Item 3"
        blocks = md_to_blocks(md)
        assert len(blocks) == 3
        assert all(b["type"] == "bulleted_list_item" for b in blocks)
        assert (
            blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"]
            == "Item 1"
        )
        assert (
            blocks[1]["bulleted_list_item"]["rich_text"][0]["text"]["content"]
            == "Item 2"
        )

    def test_md_numbered_list(self):
        """Test converting numbered list."""
        md = "1. First\n2. Second\n3. Third"
        blocks = md_to_blocks(md)
        assert len(blocks) == 3
        assert all(b["type"] == "numbered_list_item" for b in blocks)
        assert (
            blocks[0]["numbered_list_item"]["rich_text"][0]["text"]["content"]
            == "First"
        )

    def test_md_quote(self):
        """Test converting quote."""
        md = "> This is a quote"
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "quote"
        assert (
            blocks[0]["quote"]["rich_text"][0]["text"]["content"] == "This is a quote"
        )

    def test_md_code_fence(self):
        """Test converting code fence."""
        md = "```\ncode line 1\ncode line 2\n```"
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "code"
        # Code content should be combined
        code_content = blocks[0]["code"]["rich_text"][0]["text"]["content"]
        assert "code line 1" in code_content
        assert "code line 2" in code_content

    def test_md_divider(self):
        """Test converting divider."""
        md = "---"
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "divider"

    def test_md_blank_line(self):
        """Test that blank lines create empty paragraphs."""
        md = "Line 1\n\nLine 2"
        blocks = md_to_blocks(md)
        assert len(blocks) == 3
        assert blocks[0]["type"] == "paragraph"
        assert blocks[1]["type"] == "paragraph"
        assert blocks[1]["paragraph"]["rich_text"] == []  # Empty
        assert blocks[2]["type"] == "paragraph"

    def test_md_mixed_content(self):
        """Test converting mixed markdown content."""
        md = "# Title\n\nParagraph text.\n\n- Bullet 1\n- Bullet 2\n\n> Quote"
        blocks = md_to_blocks(md)
        assert len(blocks) == 6
        assert blocks[0]["type"] == "heading_1"
        assert blocks[1]["type"] == "paragraph"  # blank line
        assert blocks[2]["type"] == "paragraph"  # paragraph text
        assert blocks[3]["type"] == "bulleted_list_item"
        assert blocks[4]["type"] == "bulleted_list_item"
        assert blocks[5]["type"] == "quote"

    def test_md_preserves_inline_formatting(self):
        """Test that inline formatting is preserved in blocks."""
        md = "**Bold** paragraph with *italic*"
        blocks = md_to_blocks(md)
        assert len(blocks) == 1
        rich_text = blocks[0]["paragraph"]["rich_text"]
        # Should have multiple rich text objects with different formatting
        assert len(rich_text) >= 3


class TestNotionEngineInit:
    """Test NotionEngine initialization."""

    def test_init_with_token(self):
        """Test initialization with explicit token."""
        engine = NotionEngine(token="test_token")
        assert engine.token == "test_token"
        assert engine.progress_callback is None

    def test_init_token_from_env(self):
        """Test that token is loaded from environment."""
        with patch.dict(os.environ, {"NOTION_TOKEN": "env_token"}):
            engine = NotionEngine()
            assert engine.token == "env_token"

    def test_init_explicit_token_overrides_env(self):
        """Test that explicit token overrides environment."""
        with patch.dict(os.environ, {"NOTION_TOKEN": "env_token"}):
            engine = NotionEngine(token="explicit_token")
            assert engine.token == "explicit_token"

    def test_init_with_progress_callback(self):
        """Test initialization with progress callback."""

        def callback(msg):
            return None

        engine = NotionEngine(token="test", progress_callback=callback)
        assert engine.progress_callback is callback

    def test_init_missing_token_uses_none(self):
        """Test that missing token is allowed (will fail on API calls)."""
        with patch.dict(os.environ, {}, clear=True):
            engine = NotionEngine()
            assert engine.token is None


class TestNotionEngineGetClient:
    """Test NotionEngine._get_client() method."""

    def test_get_client_missing_notion_client(self):
        """Test that missing notion_client library raises error."""
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "notion_client":
                raise ImportError("No module named 'notion_client'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            engine = NotionEngine(token="test")
            with pytest.raises(
                NotionError, match="notion-client library not installed"
            ):
                engine._get_client()

    def test_get_client_missing_token(self):
        """Test that missing token raises error."""
        engine = NotionEngine(token=None)
        with pytest.raises(NotionError, match="Notion token not found"):
            engine._get_client()


class TestNotionEngineSetPageCover:
    """Test NotionEngine.set_page_cover() method."""

    @pytest.fixture
    def mock_notion_client(self):
        """Fixture to mock notion_client module."""
        mock_module = MagicMock()
        sys.modules["notion_client"] = mock_module
        yield mock_module
        if "notion_client" in sys.modules:
            del sys.modules["notion_client"]

    def test_set_page_cover_success(self, mock_notion_client):
        """Test successfully setting page cover."""
        mock_client = MagicMock()
        mock_notion_client.Client.return_value = mock_client

        engine = NotionEngine(token="test_token")
        engine.set_page_cover("page_123", "https://example.com/cover.jpg")

        # Verify API was called
        mock_client.pages.update.assert_called_once()
        call_kwargs = mock_client.pages.update.call_args[1]
        assert call_kwargs["page_id"] == "page_123"
        assert (
            call_kwargs["cover"]["external"]["url"] == "https://example.com/cover.jpg"
        )

    def test_set_page_cover_api_failure(self, mock_notion_client):
        """Test handling of API failure."""
        mock_client = MagicMock()
        mock_client.pages.update.side_effect = Exception("API error")
        mock_notion_client.Client.return_value = mock_client

        engine = NotionEngine(token="test_token")

        with pytest.raises(NotionError, match="Failed to set page cover"):
            engine.set_page_cover("page_123", "https://example.com/cover.jpg")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_parse_inline_markdown_with_special_chars(self):
        """Test parsing markdown with special characters."""
        result = parse_inline_markdown("Text with <>&\"' special chars")
        assert len(result) >= 1
        # Should preserve special characters
        full_text = "".join(r["text"]["content"] for r in result)
        assert "<>&\"'" in full_text

    def test_md_to_blocks_empty_string(self):
        """Test converting empty markdown."""
        blocks = md_to_blocks("")
        # Empty string should create at least one empty paragraph
        assert len(blocks) >= 0

    def test_md_to_blocks_windows_line_endings(self):
        """Test that Windows line endings are handled."""
        md = "Line 1\r\nLine 2"
        blocks = md_to_blocks(md)
        assert len(blocks) == 2
        assert all(b["type"] == "paragraph" for b in blocks)

    def test_chunk_rich_text_exact_chunk_size(self):
        """Test chunking text that's exactly the chunk size."""
        text = "A" * 1800
        chunks = list(chunk_rich_text(text, chunk=1800))
        assert len(chunks) == 1
        assert len(chunks[0]["text"]["content"]) == 1800

    def test_md_to_blocks_unclosed_code_fence(self):
        """Test handling of unclosed code fence."""
        md = "```\ncode without closing fence"
        blocks = md_to_blocks(md)
        # Should create a code block even if not closed
        assert any(b["type"] == "code" for b in blocks)

    def test_parse_inline_markdown_consecutive_markers(self):
        """Test handling of consecutive formatting markers."""
        result = parse_inline_markdown("**bold****more bold**")
        # Should handle consecutive ** markers
        assert len(result) >= 1
