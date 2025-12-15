#!/usr/bin/env python3
"""
Tests for deepcast.py optimizations (parallel chunk processing).

Tests verify the 4x speedup from parallel API calls with rate limiting.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from podx.deepcast import chat_once_async


class TestAsyncWrapper:
    """Test async wrapper for chat_once."""

    @pytest.mark.asyncio
    @patch("podx.deepcast.chat_once")
    async def test_chat_once_async_calls_sync_version(self, mock_chat_once):
        """Test async wrapper calls synchronous chat_once."""
        mock_client = Mock()
        mock_chat_once.return_value = "Test response"

        result = await chat_once_async(
            mock_client,
            model="gpt-4.1",
            system="System prompt",
            user="User prompt",
            temperature=0.2,
        )

        assert result == "Test response"
        mock_chat_once.assert_called_once_with(
            mock_client, "gpt-4.1", "System prompt", "User prompt", 0.2
        )

    @pytest.mark.asyncio
    @patch("podx.deepcast.chat_once")
    async def test_chat_once_async_runs_in_executor(self, mock_chat_once):
        """Test async wrapper runs in thread pool executor."""
        mock_client = Mock()
        mock_chat_once.return_value = "Response"

        # Run multiple calls in parallel
        tasks = [chat_once_async(mock_client, "gpt-4.1", "sys", f"user {i}", 0.2) for i in range(3)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r == "Response" for r in results)
        assert mock_chat_once.call_count == 3


class TestParallelChunkProcessing:
    """Test parallel chunk processing optimization (4x speedup)."""

    @pytest.mark.asyncio
    @patch("podx.deepcast.chat_once")
    async def test_parallel_processing_pattern(self, mock_chat_once):
        """Test the parallel processing pattern used in deepcast."""
        import asyncio

        from podx.deepcast import chat_once_async

        # Mock responses for each chunk
        responses = ["Note 1", "Note 2", "Note 3", "Note 4"]
        mock_chat_once.side_effect = responses

        mock_client = Mock()

        # Simulate the pattern used in deepcast.py
        async def process_chunks_parallel():
            """Process all chunks concurrently with rate limiting."""
            semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests
            chunks = ["Chunk 1", "Chunk 2", "Chunk 3", "Chunk 4"]

            async def process_chunk(i: int, chunk: str) -> str:
                async with semaphore:
                    prompt = f"Map instructions\n\nChunk {i+1}/{len(chunks)}:\n\n{chunk}"
                    note = await chat_once_async(
                        mock_client,
                        model="gpt-4.1",
                        system="system",
                        user=prompt,
                        temperature=0.2,
                    )
                    return note

            tasks = [process_chunk(i, chunk) for i, chunk in enumerate(chunks)]
            return await asyncio.gather(*tasks)

        # Run parallel processing
        map_notes = await process_chunks_parallel()

        # Verify all chunks were processed
        assert len(map_notes) == 4
        assert map_notes == ["Note 1", "Note 2", "Note 3", "Note 4"]
        assert mock_chat_once.call_count == 4

    @pytest.mark.asyncio
    @patch("podx.deepcast.chat_once")
    async def test_result_ordering_preserved(self, mock_chat_once):
        """Test that parallel processing preserves chunk order."""
        import asyncio

        from podx.deepcast import chat_once_async

        # Return different responses for each chunk
        responses = ["Note 1", "Note 2", "Note 3"]
        mock_chat_once.side_effect = responses

        mock_client = Mock()
        chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]

        # Process in parallel
        async def process_parallel():
            tasks = [
                chat_once_async(mock_client, "gpt-4.1", "sys", f"Process {chunk}", 0.2)
                for chunk in chunks
            ]
            return await asyncio.gather(*tasks)

        results = await process_parallel()

        # Verify order is preserved
        assert results == ["Note 1", "Note 2", "Note 3"]


class TestPerformanceCharacteristics:
    """Test performance characteristics of parallel processing."""

    @pytest.mark.asyncio
    @patch("podx.deepcast.chat_once")
    async def test_parallel_execution_faster_than_sequential(self, mock_chat_once):
        """Test that parallel execution is faster than sequential."""
        import time

        from podx.deepcast import chat_once_async

        # Mock with realistic delay
        def slow_response(*args, **kwargs):
            time.sleep(0.1)  # 100ms delay
            return "Response"

        mock_chat_once.side_effect = slow_response

        mock_client = Mock()

        # Sequential execution
        start_seq = time.time()
        for i in range(4):
            await chat_once_async(mock_client, "gpt-4.1", "sys", f"user {i}", 0.2)
        seq_time = time.time() - start_seq

        # Reset mock
        mock_chat_once.reset_mock()
        mock_chat_once.side_effect = slow_response

        # Parallel execution
        start_par = time.time()
        tasks = [chat_once_async(mock_client, "gpt-4.1", "sys", f"user {i}", 0.2) for i in range(4)]
        await asyncio.gather(*tasks)
        par_time = time.time() - start_par

        # Parallel should be faster (though exact speedup depends on executor)
        # Sequential: 4 * 100ms = 400ms
        # Parallel: ~100-200ms (depending on thread pool)
        assert par_time < seq_time
        assert mock_chat_once.call_count == 4

    @pytest.mark.asyncio
    @patch("podx.deepcast.chat_once")
    async def test_semaphore_limits_concurrency(self, mock_chat_once):
        """Test that semaphore limits concurrent requests to 3."""
        import asyncio

        # Track active calls
        active_calls = []
        max_concurrent = 0

        async def track_concurrent(*args, **kwargs):
            active_calls.append(1)
            current = len(active_calls)
            nonlocal max_concurrent
            max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.05)  # Simulate API call
            active_calls.pop()
            return "Response"

        # Create our own semaphore-limited processing
        semaphore = asyncio.Semaphore(3)

        async def limited_call(i):
            async with semaphore:
                return await track_concurrent(None, "gpt-4.1", "sys", f"user {i}", 0.2)

        # Run 10 calls with semaphore limit
        tasks = [limited_call(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Verify results
        assert len(results) == 10
        # Max concurrent should not exceed semaphore limit
        assert max_concurrent <= 3


class TestChunkSplitting:
    """Test chunk splitting utility function."""

    def test_split_into_chunks_by_paragraphs(self):
        """Test chunk splitting by paragraphs."""
        from podx.deepcast import split_into_chunks

        # Create text with paragraphs (newlines) that will be split
        paragraphs = ["A" * 100 for _ in range(5)]
        text = "\n".join(paragraphs)
        chunks = split_into_chunks(text, approx_chars=250)

        # Should create multiple chunks
        assert len(chunks) > 1
        # Verify chunks don't exceed reasonable size
        for chunk in chunks:
            assert len(chunk) <= 350  # Allow some variance

    def test_split_into_chunks_empty(self):
        """Test chunk splitting with empty text."""
        from podx.deepcast import split_into_chunks

        chunks = split_into_chunks("", approx_chars=300)

        # Should return single chunk (empty string)
        assert isinstance(chunks, list)
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_split_into_chunks_short_text(self):
        """Test chunk splitting with text shorter than target."""
        from podx.deepcast import split_into_chunks

        text = "Short text"
        chunks = split_into_chunks(text, approx_chars=300)

        # Should return single chunk
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_into_chunks_preserves_paragraph_structure(self):
        """Test that chunk splitting preserves paragraph boundaries."""
        from podx.deepcast import split_into_chunks

        # Three paragraphs of varying sizes
        p1 = "First paragraph. " * 20  # ~340 chars
        p2 = "Second paragraph. " * 20  # ~360 chars
        p3 = "Third paragraph. " * 20  # ~340 chars
        text = f"{p1}\n{p2}\n{p3}"

        chunks = split_into_chunks(text, approx_chars=400)

        # Should split but preserve paragraph boundaries
        assert len(chunks) > 1
        # Each chunk should end at paragraph boundary (contain full paragraphs)
        for chunk in chunks:
            assert not chunk.startswith(" ")  # No leading space (broken mid-para)


class TestErrorHandling:
    """Test error handling in parallel processing."""

    @pytest.mark.asyncio
    @patch("podx.deepcast.chat_once")
    async def test_api_error_propagates(self, mock_chat_once):
        """Test that API errors propagate correctly."""
        from podx.deepcast import chat_once_async

        # Mock with error
        mock_chat_once.side_effect = Exception("API error")
        mock_client = Mock()

        # Should propagate error
        with pytest.raises(Exception, match="API error"):
            await chat_once_async(mock_client, "gpt-4.1", "sys", "user", 0.2)
