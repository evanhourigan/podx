"""Benchmarks for deepcast utility operations."""
import pytest

from podx.core.deepcast import hhmmss, segments_to_plain_text, split_into_chunks


class TestTimestampFormattingBenchmarks:
    """Benchmark timestamp formatting utilities."""

    @pytest.fixture
    def various_timestamps(self):
        """Various timestamp values to benchmark."""
        return [
            0.0,  # Zero
            5.5,  # Seconds only
            65.25,  # Minutes
            3665.75,  # Hours
            86400.0,  # 24 hours
            123456.789,  # Large value with subseconds
        ]

    def test_hhmmss_seconds(self, benchmark):
        """Benchmark formatting seconds-only timestamp."""
        result = benchmark(hhmmss, 5.5)
        assert result == "00:00:05"

    def test_hhmmss_minutes(self, benchmark):
        """Benchmark formatting minutes timestamp."""
        result = benchmark(hhmmss, 65.25)
        assert result == "00:01:05"

    def test_hhmmss_hours(self, benchmark):
        """Benchmark formatting hours timestamp."""
        result = benchmark(hhmmss, 3665.75)
        assert result == "01:01:05"

    def test_hhmmss_batch(self, benchmark, various_timestamps):
        """Benchmark formatting batch of timestamps."""

        def format_batch():
            return [hhmmss(ts) for ts in various_timestamps]

        results = benchmark(format_batch)
        assert len(results) == len(various_timestamps)


class TestTextProcessingBenchmarks:
    """Benchmark text processing utilities."""

    @pytest.fixture
    def small_segments(self):
        """Small transcript (10 segments)."""
        return [
            {
                "start": i * 5.0,
                "end": (i + 1) * 5.0,
                "text": f"This is segment {i} with some text.",
                "speaker": f"Speaker {i % 2}",
            }
            for i in range(10)
        ]

    @pytest.fixture
    def medium_segments(self):
        """Medium transcript (100 segments)."""
        return [
            {
                "start": i * 5.0,
                "end": (i + 1) * 5.0,
                "text": f"This is segment {i} with some text to process.",
                "speaker": f"Speaker {i % 3}",
            }
            for i in range(100)
        ]

    @pytest.fixture
    def large_segments(self):
        """Large transcript (1000 segments)."""
        return [
            {
                "start": i * 5.0,
                "end": (i + 1) * 5.0,
                "text": f"This is segment {i} with some text to process.",
                "speaker": f"Speaker {i % 3}",
            }
            for i in range(1000)
        ]

    @pytest.fixture
    def long_text(self):
        """Long text for chunking tests."""
        return " ".join([f"This is sentence {i}." for i in range(1000)])

    def test_segments_to_plain_text_small(self, benchmark, small_segments):
        """Benchmark converting small transcript to plain text."""
        result = benchmark(segments_to_plain_text, small_segments, True, True)
        assert len(result) > 0

    def test_segments_to_plain_text_medium(self, benchmark, medium_segments):
        """Benchmark converting medium transcript to plain text."""
        result = benchmark(segments_to_plain_text, medium_segments, True, True)
        assert len(result) > 0

    def test_segments_to_plain_text_large(self, benchmark, large_segments):
        """Benchmark converting large transcript to plain text."""
        result = benchmark(segments_to_plain_text, large_segments, True, True)
        assert len(result) > 0

    def test_split_into_chunks_small(self, benchmark):
        """Benchmark splitting short text into chunks."""
        text = "This is a short text that needs to be chunked."
        result = benchmark(split_into_chunks, text, 20)
        assert len(result) > 0

    def test_split_into_chunks_medium(self, benchmark):
        """Benchmark splitting medium text into chunks."""
        text = " ".join([f"This is sentence {i}." for i in range(100)])
        result = benchmark(split_into_chunks, text, 500)
        assert len(result) > 0

    def test_split_into_chunks_large(self, benchmark, long_text):
        """Benchmark splitting long text into chunks."""
        result = benchmark(split_into_chunks, long_text, 1000)
        assert len(result) > 0

    def test_split_into_chunks_various_sizes(self, benchmark, long_text):
        """Benchmark splitting with various chunk sizes."""

        def split_various():
            results = []
            for chunk_size in [500, 1000, 2000, 5000]:
                results.append(split_into_chunks(long_text, chunk_size))
            return results

        results = benchmark(split_various)
        assert len(results) == 4
