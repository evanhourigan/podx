"""Tests for transcript database search."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from podx.domain.models.transcript import DiarizedSegment, Transcript
from podx.search.database import TranscriptDatabase


@pytest.fixture
def temp_db() -> Path:
    """Create temporary database file."""
    temp_dir = tempfile.mkdtemp()
    return Path(temp_dir) / "test.db"


@pytest.fixture
def sample_transcript() -> Transcript:
    """Create sample transcript."""
    segments = [
        DiarizedSegment(
            start=0.0,
            end=5.0,
            text="This is about artificial intelligence and machine learning",
            speaker="Alice",
        ),
        DiarizedSegment(
            start=5.0,
            end=10.0,
            text="Quantum computing is a fascinating topic",
            speaker="Bob",
        ),
        DiarizedSegment(
            start=10.0,
            end=15.0,
            text="AI will change the world",
            speaker="Alice",
        ),
    ]
    return Transcript(segments=segments)


def test_database_init(temp_db: Path) -> None:
    """Test database initialization."""
    db = TranscriptDatabase(db_path=temp_db)
    assert temp_db.exists()

    stats = db.get_stats()
    assert stats["episodes"] == 0
    assert stats["segments"] == 0


def test_index_transcript(temp_db: Path, sample_transcript: Transcript) -> None:
    """Test indexing a transcript."""
    db = TranscriptDatabase(db_path=temp_db)

    metadata = {"title": "Test Episode", "show_name": "Test Show", "date": "2024-01-01"}

    db.index_transcript("ep001", sample_transcript, metadata)

    stats = db.get_stats()
    assert stats["episodes"] == 1
    assert stats["segments"] == 3


def test_search_basic(temp_db: Path, sample_transcript: Transcript) -> None:
    """Test basic keyword search."""
    db = TranscriptDatabase(db_path=temp_db)
    db.index_transcript("ep001", sample_transcript)

    results = db.search("artificial intelligence")
    assert len(results) >= 1
    assert "artificial intelligence" in results[0]["text"].lower()


def test_search_filters(temp_db: Path, sample_transcript: Transcript) -> None:
    """Test search with filters."""
    db = TranscriptDatabase(db_path=temp_db)
    db.index_transcript("ep001", sample_transcript)

    # Filter by speaker
    results = db.search("AI", speaker_filter="Alice")
    assert len(results) >= 1
    assert all(r["speaker"] == "Alice" for r in results)


def test_get_episode_info(temp_db: Path, sample_transcript: Transcript) -> None:
    """Test retrieving episode info."""
    db = TranscriptDatabase(db_path=temp_db)

    metadata = {"title": "Test Episode", "show_name": "Test Show"}
    db.index_transcript("ep001", sample_transcript, metadata)

    info = db.get_episode_info("ep001")
    assert info is not None
    assert info["episode_id"] == "ep001"
    assert info["title"] == "Test Episode"


def test_list_episodes(temp_db: Path, sample_transcript: Transcript) -> None:
    """Test listing episodes."""
    db = TranscriptDatabase(db_path=temp_db)

    db.index_transcript("ep001", sample_transcript, {"title": "Episode 1"})
    db.index_transcript("ep002", sample_transcript, {"title": "Episode 2"})

    episodes = db.list_episodes()
    assert len(episodes) == 2


def test_delete_episode(temp_db: Path, sample_transcript: Transcript) -> None:
    """Test deleting an episode."""
    db = TranscriptDatabase(db_path=temp_db)

    db.index_transcript("ep001", sample_transcript)
    stats = db.get_stats()
    assert stats["episodes"] == 1

    db.delete_episode("ep001")
    stats = db.get_stats()
    assert stats["episodes"] == 0


def test_reindex_episode(temp_db: Path, sample_transcript: Transcript) -> None:
    """Test re-indexing the same episode."""
    db = TranscriptDatabase(db_path=temp_db)

    db.index_transcript("ep001", sample_transcript)
    stats1 = db.get_stats()

    # Re-index with same episode ID
    db.index_transcript("ep001", sample_transcript)
    stats2 = db.get_stats()

    # Should not duplicate
    assert stats1 == stats2
