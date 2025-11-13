"""Benchmark fixtures and configuration."""
import json

import pytest


@pytest.fixture
def sample_audio_metadata():
    """Sample audio metadata for benchmarks."""
    return {
        "show": "Test Podcast",
        "title": "Test Episode",
        "date": "2025-01-01",
        "duration": 3600.0,
        "format": "mp3",
    }


@pytest.fixture
def sample_transcript():
    """Sample transcript for benchmarks."""
    return {
        "segments": [
            {
                "start": i * 10.0,
                "end": (i + 1) * 10.0,
                "text": f"This is segment {i} of the transcript.",
            }
            for i in range(100)
        ]
    }


@pytest.fixture
def temp_workdir(tmp_path):
    """Create a temporary working directory with standard structure."""
    workdir = tmp_path / "test_show" / "2025-01-01-test-episode"
    workdir.mkdir(parents=True)
    return workdir


@pytest.fixture
def sample_transcript_file(temp_workdir, sample_transcript):
    """Create a sample transcript JSON file."""
    transcript_path = temp_workdir / "transcript.json"
    with open(transcript_path, "w") as f:
        json.dump(sample_transcript, f)
    return transcript_path
