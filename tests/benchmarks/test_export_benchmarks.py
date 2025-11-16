"""Benchmarks for transcript export operations."""

import pytest

from podx.core.export import ExportEngine


@pytest.fixture
def exporter():
    """Create an export engine instance."""
    return ExportEngine()


@pytest.fixture
def transcript_segments():
    """Standard transcript segments for export benchmarks."""
    return [
        {
            "start": i * 5.0,
            "end": (i + 1) * 5.0,
            "text": f"This is segment {i} of the transcript.",
            "speaker": f"Speaker {i % 3}",
        }
        for i in range(100)
    ]


def test_export_to_txt(benchmark, exporter, transcript_segments):
    """Benchmark plain text export."""
    result = benchmark(exporter.to_txt, transcript_segments)
    assert len(result) > 0
    assert isinstance(result, str)


def test_export_to_md(benchmark, exporter, transcript_segments):
    """Benchmark markdown export."""
    result = benchmark(exporter.to_md, transcript_segments)
    assert len(result) > 0
    assert isinstance(result, str)


def test_export_to_srt(benchmark, exporter, transcript_segments):
    """Benchmark SRT subtitle export."""
    result = benchmark(exporter.to_srt, transcript_segments)
    assert len(result) > 0
    assert isinstance(result, str)


def test_export_to_vtt(benchmark, exporter, transcript_segments):
    """Benchmark VTT subtitle export."""
    result = benchmark(exporter.to_vtt, transcript_segments)
    assert len(result) > 0
    assert isinstance(result, str)
