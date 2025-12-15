#!/usr/bin/env python3
"""Tests for batch processor."""

import time

from podx.batch.processor import BatchProcessor, BatchResult
from podx.domain.exit_codes import ExitCode


class TestBatchProcessor:
    """Test batch processor functionality."""

    def test_process_batch_success(self):
        """Test successful batch processing."""
        episodes = [
            {"title": "Episode 1"},
            {"title": "Episode 2"},
            {"title": "Episode 3"},
        ]

        def process_fn(episode):
            return {"processed": True, "title": episode["title"]}

        processor = BatchProcessor(parallel_workers=2)
        results = processor.process_batch(episodes, process_fn, "Test Processing")

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.result["processed"] for r in results)

    def test_process_batch_with_failures(self):
        """Test batch processing with some failures."""
        episodes = [
            {"title": "Episode 1", "should_fail": False},
            {"title": "Episode 2", "should_fail": True},
            {"title": "Episode 3", "should_fail": False},
        ]

        def process_fn(episode):
            if episode.get("should_fail"):
                raise ValueError("Intentional failure")
            return {"processed": True}

        processor = BatchProcessor(parallel_workers=2, continue_on_error=True)
        results = processor.process_batch(episodes, process_fn, "Test Processing")

        assert len(results) == 3
        assert sum(1 for r in results if r.success) == 2
        assert sum(1 for r in results if not r.success) == 1

    def test_process_batch_stop_on_error(self):
        """Test batch processing stops on first error."""
        episodes = [
            {"title": "Episode 1", "should_fail": False},
            {"title": "Episode 2", "should_fail": True},
            {"title": "Episode 3", "should_fail": False},
        ]

        def process_fn(episode):
            if episode.get("should_fail"):
                raise ValueError("Intentional failure")
            return {"processed": True}

        processor = BatchProcessor(parallel_workers=1, continue_on_error=False)
        results = processor.process_batch(episodes, process_fn, "Test Processing")

        # Should process until error
        assert len(results) >= 1
        assert any(not r.success for r in results)

    def test_process_batch_with_retries(self):
        """Test batch processing with retry logic."""

        class FailCounter:
            def __init__(self):
                self.attempt = 0

            def process(self, episode):
                self.attempt += 1
                if self.attempt < 2:
                    raise ValueError("First attempt fails")
                return {"processed": True, "attempts": self.attempt}

        counter = FailCounter()
        episodes = [{"title": "Episode 1"}]

        processor = BatchProcessor(parallel_workers=1, max_retries=2, retry_delay=0)
        results = processor.process_batch(episodes, counter.process, "Test Processing")

        assert len(results) == 1
        assert results[0].success
        assert results[0].retries == 1  # One retry needed

    def test_process_batch_retry_exhausted(self):
        """Test batch processing when retries are exhausted."""

        def always_fail(episode):
            raise ValueError("Always fails")

        episodes = [{"title": "Episode 1"}]

        processor = BatchProcessor(parallel_workers=1, max_retries=2, retry_delay=0)
        results = processor.process_batch(episodes, always_fail, "Test Processing")

        assert len(results) == 1
        assert not results[0].success
        assert results[0].retries == 3  # Initial + 2 retries

    def test_process_batch_parallel(self):
        """Test parallel batch processing."""
        episodes = [{"title": f"Episode {i}"} for i in range(10)]

        def slow_process(episode):
            time.sleep(0.05)  # Simulate work (longer to dominate thread overhead)
            return {"processed": True}

        # Process serially
        start_serial = time.time()
        processor_serial = BatchProcessor(parallel_workers=1)
        processor_serial.process_batch(episodes, slow_process, "Serial")
        serial_time = time.time() - start_serial

        # Process in parallel
        start_parallel = time.time()
        processor_parallel = BatchProcessor(parallel_workers=4)
        processor_parallel.process_batch(episodes, slow_process, "Parallel")
        parallel_time = time.time() - start_parallel

        # Parallel should be faster (relaxed tolerance for Windows thread overhead)
        assert parallel_time < serial_time * 1.0

    def test_process_batch_empty(self):
        """Test processing empty batch."""

        def process_fn(episode):
            return {"processed": True}

        processor = BatchProcessor()
        results = processor.process_batch([], process_fn, "Empty Batch")

        assert len(results) == 0

    def test_get_exit_code_success(self):
        """Test exit code for all successful results."""
        results = [
            BatchResult(episode={}, success=True),
            BatchResult(episode={}, success=True),
        ]

        processor = BatchProcessor()
        exit_code = processor.get_exit_code(results)

        assert exit_code == ExitCode.SUCCESS

    def test_get_exit_code_partial(self):
        """Test exit code for partial success."""
        results = [
            BatchResult(episode={}, success=True),
            BatchResult(episode={}, success=False, error="Failed"),
        ]

        processor = BatchProcessor()
        exit_code = processor.get_exit_code(results)

        # Partial success should return PROCESSING_ERROR
        assert exit_code == ExitCode.PROCESSING_ERROR

    def test_get_exit_code_all_failed(self):
        """Test exit code for all failures."""
        results = [
            BatchResult(episode={}, success=False, error="Failed"),
            BatchResult(episode={}, success=False, error="Failed"),
        ]

        processor = BatchProcessor()
        exit_code = processor.get_exit_code(results)

        assert exit_code == ExitCode.PROCESSING_ERROR

    def test_get_exit_code_empty(self):
        """Test exit code for empty results."""
        processor = BatchProcessor()
        exit_code = processor.get_exit_code([])

        assert exit_code == ExitCode.USER_ERROR

    def test_batch_result_creation(self):
        """Test creating batch result."""
        episode = {"title": "Test Episode"}

        result = BatchResult(
            episode=episode,
            success=True,
            result={"data": "test"},
            duration=1.5,
        )

        assert result.episode == episode
        assert result.success is True
        assert result.result == {"data": "test"}
        assert result.duration == 1.5
        assert result.retries == 0

    def test_batch_result_with_error(self):
        """Test batch result with error."""
        episode = {"title": "Test Episode"}

        result = BatchResult(episode=episode, success=False, error="Something failed", retries=2)

        assert result.success is False
        assert result.error == "Something failed"
        assert result.retries == 2
