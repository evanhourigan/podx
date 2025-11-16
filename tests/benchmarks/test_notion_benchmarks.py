"""Benchmarks for Notion utility operations."""

import pytest

from podx.core.notion import chunk_rich_text, md_to_blocks, parse_inline_markdown


class TestRichTextChunkingBenchmarks:
    """Benchmark rich text chunking operations."""

    @pytest.fixture
    def short_text(self):
        """Short text under chunk limit."""
        return "This is a short text that fits in one chunk."

    @pytest.fixture
    def medium_text(self):
        """Medium text requiring 2-3 chunks."""
        return " ".join([f"Sentence {i}." for i in range(200)])

    @pytest.fixture
    def long_text(self):
        """Long text requiring many chunks."""
        return " ".join([f"Sentence {i}." for i in range(1000)])

    def test_chunk_rich_text_short(self, benchmark, short_text):
        """Benchmark chunking short text."""
        result = benchmark(lambda: list(chunk_rich_text(short_text)))
        assert len(result) >= 1

    def test_chunk_rich_text_medium(self, benchmark, medium_text):
        """Benchmark chunking medium text."""
        result = benchmark(lambda: list(chunk_rich_text(medium_text)))
        assert len(result) >= 1

    def test_chunk_rich_text_long(self, benchmark, long_text):
        """Benchmark chunking long text."""
        result = benchmark(lambda: list(chunk_rich_text(long_text)))
        assert len(result) >= 1

    def test_chunk_rich_text_various_sizes(self, benchmark):
        """Benchmark chunking with various chunk sizes."""

        def chunk_various():
            text = " ".join([f"Word {i}" for i in range(500)])
            results = []
            for size in [500, 1000, 1500, 2000]:
                results.append(list(chunk_rich_text(text, chunk=size)))
            return results

        results = benchmark(chunk_various)
        assert len(results) == 4


class TestMarkdownParsingBenchmarks:
    """Benchmark markdown parsing operations."""

    @pytest.fixture
    def simple_text(self):
        """Simple plain text without formatting."""
        return "This is simple text without any formatting."

    @pytest.fixture
    def formatted_text(self):
        """Text with inline formatting."""
        return "This is **bold** and this is *italic* and this is `code`."

    @pytest.fixture
    def mixed_text(self):
        """Text with mixed formatting."""
        return (
            "Normal text **bold text** more normal *italic* "
            "and `code snippet` with **bold *nested italic* text** end."
        )

    @pytest.fixture
    def simple_markdown(self):
        """Simple markdown document."""
        return """# Heading 1

This is a paragraph with **bold** and *italic* text.

## Heading 2

- List item 1
- List item 2
- List item 3

Another paragraph with `code`.
"""

    @pytest.fixture
    def complex_markdown(self):
        """Complex markdown document."""
        return """# Main Title

## Introduction

This is a paragraph with **bold**, *italic*, and `code` formatting.

### Subsection

1. Numbered item 1
2. Numbered item 2
3. Numbered item 3

More text here with **bold *nested italic* text**.

## Another Section

- Bullet point 1
- Bullet point 2 with `code`
- Bullet point 3 with **bold**

Final paragraph.
"""

    def test_parse_inline_markdown_simple(self, benchmark, simple_text):
        """Benchmark parsing simple text."""
        result = benchmark(parse_inline_markdown, simple_text)
        assert len(result) > 0

    def test_parse_inline_markdown_formatted(self, benchmark, formatted_text):
        """Benchmark parsing formatted text."""
        result = benchmark(parse_inline_markdown, formatted_text)
        assert len(result) > 0

    def test_parse_inline_markdown_mixed(self, benchmark, mixed_text):
        """Benchmark parsing mixed formatting."""
        result = benchmark(parse_inline_markdown, mixed_text)
        assert len(result) > 0

    def test_md_to_blocks_simple(self, benchmark, simple_markdown):
        """Benchmark converting simple markdown to Notion blocks."""
        result = benchmark(md_to_blocks, simple_markdown)
        assert len(result) > 0

    def test_md_to_blocks_complex(self, benchmark, complex_markdown):
        """Benchmark converting complex markdown to Notion blocks."""
        result = benchmark(md_to_blocks, complex_markdown)
        assert len(result) > 0

    def test_md_to_blocks_batch(self, benchmark):
        """Benchmark converting multiple markdown documents."""

        def convert_batch():
            docs = [
                "# Title 1\n\nParagraph 1",
                "# Title 2\n\n- Item 1\n- Item 2",
                "# Title 3\n\n**Bold** and *italic*",
            ]
            return [md_to_blocks(doc) for doc in docs]

        results = benchmark(convert_batch)
        assert len(results) == 3
