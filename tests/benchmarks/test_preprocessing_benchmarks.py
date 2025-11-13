"""Benchmarks for transcript preprocessing operations."""
import pytest

from podx.core.preprocess import TranscriptPreprocessor


@pytest.fixture
def preprocessor():
    """Create a preprocessor instance."""
    return TranscriptPreprocessor(merge=True, normalize=True, max_gap=2.0)


@pytest.fixture
def small_segments():
    """Small transcript (10 segments) for quick benchmarks."""
    return [
        {
            "start": i * 5.0,
            "end": (i + 1) * 5.0,
            "text": f"This is segment {i} with some text to process.",
        }
        for i in range(10)
    ]


@pytest.fixture
def medium_segments():
    """Medium transcript (100 segments) for typical benchmarks."""
    return [
        {
            "start": i * 5.0,
            "end": (i + 1) * 5.0,
            "text": f"This is segment {i} with some text to process.",
        }
        for i in range(100)
    ]


@pytest.fixture
def large_segments():
    """Large transcript (1000 segments) for stress testing."""
    return [
        {
            "start": i * 5.0,
            "end": (i + 1) * 5.0,
            "text": f"This is segment {i} with some text to process.",
        }
        for i in range(1000)
    ]


def test_merge_segments_small(benchmark, preprocessor, small_segments):
    """Benchmark merge_segments with small transcript."""
    result = benchmark(preprocessor.merge_segments, small_segments)
    assert len(result) > 0


def test_merge_segments_medium(benchmark, preprocessor, medium_segments):
    """Benchmark merge_segments with medium transcript."""
    result = benchmark(preprocessor.merge_segments, medium_segments)
    assert len(result) > 0


def test_merge_segments_large(benchmark, preprocessor, large_segments):
    """Benchmark merge_segments with large transcript."""
    result = benchmark(preprocessor.merge_segments, large_segments)
    assert len(result) > 0


def test_normalize_text_small(benchmark, preprocessor, small_segments):
    """Benchmark normalize_text with small transcript."""
    text = " ".join(s["text"] for s in small_segments)
    result = benchmark(preprocessor.normalize_text, text)
    assert len(result) > 0


def test_normalize_text_medium(benchmark, preprocessor, medium_segments):
    """Benchmark normalize_text with medium transcript."""
    text = " ".join(s["text"] for s in medium_segments)
    result = benchmark(preprocessor.normalize_text, text)
    assert len(result) > 0


def test_normalize_text_large(benchmark, preprocessor, large_segments):
    """Benchmark normalize_text with large transcript."""
    text = " ".join(s["text"] for s in large_segments)
    result = benchmark(preprocessor.normalize_text, text)
    assert len(result) > 0


def test_normalize_segments_small(benchmark, preprocessor, small_segments):
    """Benchmark normalize_segments with small transcript."""
    result = benchmark(preprocessor.normalize_segments, small_segments)
    assert len(result) > 0


def test_normalize_segments_medium(benchmark, preprocessor, medium_segments):
    """Benchmark normalize_segments with medium transcript."""
    result = benchmark(preprocessor.normalize_segments, medium_segments)
    assert len(result) > 0


def test_normalize_segments_large(benchmark, preprocessor, large_segments):
    """Benchmark normalize_segments with large transcript."""
    result = benchmark(preprocessor.normalize_segments, large_segments)
    assert len(result) > 0
