#!/usr/bin/env python3
"""Tests for batch status tracking."""

import tempfile
from pathlib import Path


from podx.batch.status import BatchStatus, EpisodeStatus, ProcessingState


class TestBatchStatus:
    """Test batch status tracking."""

    def test_add_episode(self):
        """Test adding episode to tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            batch_status = BatchStatus(status_file=status_file)

            episode = {"title": "Test Episode", "show": "Test Show"}
            key = batch_status.add_episode(episode)

            assert key in batch_status.episodes
            assert batch_status.episodes[key].title == "Test Episode"
            assert batch_status.episodes[key].show == "Test Show"

    def test_update_episode_status(self):
        """Test updating episode processing status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            batch_status = BatchStatus(status_file=status_file)

            episode = {"title": "Test Episode"}
            key = batch_status.add_episode(episode)

            # Update transcribe status
            batch_status.update_episode(key, "transcribe", ProcessingState.IN_PROGRESS)
            assert batch_status.episodes[key].transcribe == ProcessingState.IN_PROGRESS

            # Complete transcribe
            batch_status.update_episode(key, "transcribe", ProcessingState.COMPLETED)
            assert batch_status.episodes[key].transcribe == ProcessingState.COMPLETED

    def test_update_episode_with_error(self):
        """Test updating episode with error message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            batch_status = BatchStatus(status_file=status_file)

            episode = {"title": "Test Episode"}
            key = batch_status.add_episode(episode)

            # Mark as failed with error
            batch_status.update_episode(
                key, "transcribe", ProcessingState.FAILED, "API error"
            )

            assert batch_status.episodes[key].transcribe == ProcessingState.FAILED
            assert batch_status.episodes[key].error_message == "API error"

    def test_get_status(self):
        """Test getting episode status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            batch_status = BatchStatus(status_file=status_file)

            episode = {"title": "Test Episode"}
            key = batch_status.add_episode(episode)

            status = batch_status.get_status(key)
            assert status is not None
            assert status.title == "Test Episode"

    def test_get_status_nonexistent(self):
        """Test getting status for nonexistent episode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            batch_status = BatchStatus(status_file=status_file)

            status = batch_status.get_status("nonexistent")
            assert status is None

    def test_persistence(self):
        """Test status persistence to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"

            # Create and populate status
            batch_status1 = BatchStatus(status_file=status_file)
            episode = {"title": "Test Episode"}
            key = batch_status1.add_episode(episode)
            batch_status1.update_episode(key, "transcribe", ProcessingState.COMPLETED)

            # Load from disk
            batch_status2 = BatchStatus(status_file=status_file)

            assert key in batch_status2.episodes
            assert batch_status2.episodes[key].title == "Test Episode"
            assert batch_status2.episodes[key].transcribe == ProcessingState.COMPLETED

    def test_export_json(self):
        """Test exporting status to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            output_file = Path(tmpdir) / "export.json"

            batch_status = BatchStatus(status_file=status_file)
            episode = {"title": "Test Episode"}
            key = batch_status.add_episode(episode)
            batch_status.update_episode(key, "transcribe", ProcessingState.COMPLETED)

            # Export
            batch_status.export_json(output_file)

            assert output_file.exists()

            # Verify content
            import json

            with open(output_file) as f:
                data = json.load(f)

            assert key in data
            assert data[key]["title"] == "Test Episode"

    def test_export_csv(self):
        """Test exporting status to CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            output_file = Path(tmpdir) / "export.csv"

            batch_status = BatchStatus(status_file=status_file)
            episode = {"title": "Test Episode", "show": "Test Show"}
            key = batch_status.add_episode(episode)
            batch_status.update_episode(key, "transcribe", ProcessingState.COMPLETED)

            # Export
            batch_status.export_csv(output_file)

            assert output_file.exists()

            # Verify content
            import csv

            with open(output_file) as f:
                reader = csv.reader(f)
                rows = list(reader)

            assert len(rows) == 2  # Header + 1 episode
            assert rows[0][0] == "Episode"
            assert rows[1][0] == "Test Episode"

    def test_clear_completed(self):
        """Test clearing completed episodes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            batch_status = BatchStatus(status_file=status_file)

            # Add completed episode
            episode1 = {"title": "Completed Episode"}
            key1 = batch_status.add_episode(episode1)
            batch_status.update_episode(key1, "export", ProcessingState.COMPLETED)

            # Add incomplete episode
            episode2 = {"title": "Incomplete Episode"}
            key2 = batch_status.add_episode(episode2)
            batch_status.update_episode(key2, "transcribe", ProcessingState.COMPLETED)

            # Clear completed
            cleared = batch_status.clear_completed()

            assert cleared == 1
            assert key1 not in batch_status.episodes
            assert key2 in batch_status.episodes

    def test_state_icon(self):
        """Test state icon generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "status.json"
            batch_status = BatchStatus(status_file=status_file)

            assert batch_status._state_icon(ProcessingState.NOT_STARTED) == "○"
            assert batch_status._state_icon(ProcessingState.IN_PROGRESS) == "⏳"
            assert batch_status._state_icon(ProcessingState.COMPLETED) == "✓"
            assert batch_status._state_icon(ProcessingState.FAILED) == "✗"


class TestEpisodeStatus:
    """Test episode status dataclass."""

    def test_episode_status_creation(self):
        """Test creating episode status."""
        status = EpisodeStatus(
            title="Test Episode",
            show="Test Show",
            directory="/path/to/episode",
        )

        assert status.title == "Test Episode"
        assert status.show == "Test Show"
        assert status.directory == "/path/to/episode"

        # All states should be NOT_STARTED by default
        assert status.fetch == ProcessingState.NOT_STARTED
        assert status.transcribe == ProcessingState.NOT_STARTED
        assert status.diarize == ProcessingState.NOT_STARTED

    def test_episode_status_update(self):
        """Test updating episode status fields."""
        status = EpisodeStatus(title="Test Episode")

        status.transcribe = ProcessingState.IN_PROGRESS
        assert status.transcribe == ProcessingState.IN_PROGRESS

        status.transcribe = ProcessingState.COMPLETED
        assert status.transcribe == ProcessingState.COMPLETED


class TestProcessingState:
    """Test processing state enum."""

    def test_processing_states(self):
        """Test all processing states exist."""
        states = [
            ProcessingState.NOT_STARTED,
            ProcessingState.IN_PROGRESS,
            ProcessingState.COMPLETED,
            ProcessingState.FAILED,
        ]

        # All states should have string values
        for state in states:
            assert isinstance(state.value, str)

    def test_processing_state_values(self):
        """Test processing state values."""
        assert ProcessingState.NOT_STARTED.value == "not_started"
        assert ProcessingState.IN_PROGRESS.value == "in_progress"
        assert ProcessingState.COMPLETED.value == "completed"
        assert ProcessingState.FAILED.value == "failed"
