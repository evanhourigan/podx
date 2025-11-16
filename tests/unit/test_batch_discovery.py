#!/usr/bin/env python3
"""Tests for batch episode discovery."""

import json
import tempfile
from pathlib import Path


from podx.batch.discovery import EpisodeDiscovery, EpisodeFilter


class TestEpisodeDiscovery:
    """Test episode discovery functionality."""

    def test_discover_by_metadata_files(self):
        """Test discovering episodes from episode-meta.json files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create episode directories with metadata
            for i in range(3):
                episode_dir = tmpdir_path / f"episode-{i}"
                episode_dir.mkdir()

                # Create metadata
                metadata = {
                    "title": f"Episode {i}",
                    "show": "Test Podcast",
                    "date": "2024-01-01",
                }
                (episode_dir / "episode-meta.json").write_text(json.dumps(metadata))

                # Create audio file
                (episode_dir / "audio.mp3").touch()

            # Discover
            discovery = EpisodeDiscovery(base_dir=tmpdir_path)
            episodes = discovery.discover_episodes(auto_detect=True)

            assert len(episodes) == 3
            assert all(ep.get("title").startswith("Episode") for ep in episodes)

    def test_discover_audio_without_metadata(self):
        """Test discovering audio files without metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create audio files without metadata
            (tmpdir_path / "podcast1.mp3").touch()
            (tmpdir_path / "podcast2.wav").touch()
            (tmpdir_path / "podcast3.m4a").touch()

            # Discover
            discovery = EpisodeDiscovery(base_dir=tmpdir_path)
            episodes = discovery.discover_episodes(auto_detect=True)

            assert len(episodes) == 3
            assert all(ep.get("discovered") is True for ep in episodes)

    def test_discover_by_pattern(self):
        """Test discovering episodes by glob pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create episodes
            for i in range(3):
                episode_dir = tmpdir_path / f"episode-{i}"
                episode_dir.mkdir()
                (episode_dir / "audio.mp3").touch()

            # Create metadata in some episodes
            metadata = {"title": "Episode 0", "show": "Test"}
            (tmpdir_path / "episode-0" / "episode-meta.json").write_text(
                json.dumps(metadata)
            )

            # Discover with pattern
            filters = EpisodeFilter(pattern="*/episode-meta.json")
            discovery = EpisodeDiscovery(base_dir=tmpdir_path)
            episodes = discovery.discover_episodes(filters=filters)

            # Should only find episode with metadata
            assert len(episodes) == 1
            assert episodes[0]["title"] == "Episode 0"

    def test_filter_by_show(self):
        """Test filtering episodes by show name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create episodes with different shows
            shows = ["Lex Fridman", "Joe Rogan", "Lex Fridman"]
            for i, show in enumerate(shows):
                episode_dir = tmpdir_path / f"episode-{i}"
                episode_dir.mkdir()

                metadata = {"title": f"Episode {i}", "show": show}
                (episode_dir / "episode-meta.json").write_text(json.dumps(metadata))
                (episode_dir / "audio.mp3").touch()

            # Discover with show filter
            filters = EpisodeFilter(show="Lex Fridman")
            discovery = EpisodeDiscovery(base_dir=tmpdir_path)
            episodes = discovery.discover_episodes(auto_detect=True, filters=filters)

            assert len(episodes) == 2
            assert all(ep["show"] == "Lex Fridman" for ep in episodes)

    def test_filter_by_date_range(self):
        """Test filtering episodes by date range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create episodes with different dates
            dates = ["2024-01-01", "2024-06-01", "2024-12-01"]
            for i, date in enumerate(dates):
                episode_dir = tmpdir_path / f"episode-{i}"
                episode_dir.mkdir()

                metadata = {"title": f"Episode {i}", "date": date}
                (episode_dir / "episode-meta.json").write_text(json.dumps(metadata))
                (episode_dir / "audio.mp3").touch()

            # Filter by date range
            filters = EpisodeFilter(date_range=("2024-01-01", "2024-06-30"))
            discovery = EpisodeDiscovery(base_dir=tmpdir_path)
            episodes = discovery.discover_episodes(auto_detect=True, filters=filters)

            assert len(episodes) == 2  # Only Jan and Jun

    def test_filter_by_duration(self):
        """Test filtering episodes by duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create episodes with different durations
            durations = [1800, 3600, 7200]  # 30min, 1h, 2h
            for i, duration in enumerate(durations):
                episode_dir = tmpdir_path / f"episode-{i}"
                episode_dir.mkdir()

                metadata = {"title": f"Episode {i}", "duration": duration}
                (episode_dir / "episode-meta.json").write_text(json.dumps(metadata))
                (episode_dir / "audio.mp3").touch()

            # Filter by min duration (1 hour)
            filters = EpisodeFilter(min_duration=3600)
            discovery = EpisodeDiscovery(base_dir=tmpdir_path)
            episodes = discovery.discover_episodes(auto_detect=True, filters=filters)

            assert len(episodes) == 2  # 1h and 2h episodes

    def test_filter_by_audio_path(self):
        """Test filtering episodes by valid audio paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create episodes
            episodes = [
                {
                    "title": "Valid Episode",
                    "audio_path": str(tmpdir_path / "valid.mp3"),
                },
                {
                    "title": "Invalid Episode",
                    "audio_path": str(tmpdir_path / "missing.mp3"),
                },
            ]

            # Create only one audio file
            (tmpdir_path / "valid.mp3").touch()

            # Filter
            discovery = EpisodeDiscovery(base_dir=tmpdir_path)
            filtered = discovery.filter_by_audio_path(episodes)

            assert len(filtered) == 1
            assert filtered[0]["title"] == "Valid Episode"

    def test_get_episode_status_new(self):
        """Test detecting new episode status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            episode = {"directory": str(tmpdir_path)}

            discovery = EpisodeDiscovery()
            status = discovery._get_episode_status(episode)

            assert status == "new"

    def test_get_episode_status_partial(self):
        """Test detecting partial episode status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create transcript (partial processing)
            (tmpdir_path / "transcript.json").touch()

            episode = {"directory": str(tmpdir_path)}

            discovery = EpisodeDiscovery()
            status = discovery._get_episode_status(episode)

            assert status == "partial"

    def test_get_episode_status_complete(self):
        """Test detecting complete episode status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create all files (complete processing)
            (tmpdir_path / "transcript.json").touch()
            (tmpdir_path / "diarized-transcript.json").touch()
            (tmpdir_path / "deepcast-notes.md").touch()

            episode = {"directory": str(tmpdir_path)}

            discovery = EpisodeDiscovery()
            status = discovery._get_episode_status(episode)

            assert status == "complete"

    def test_find_audio_file(self):
        """Test finding audio files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create audio file
            (tmpdir_path / "podcast.mp3").touch()

            discovery = EpisodeDiscovery()
            audio_file = discovery._find_audio_file(tmpdir_path)

            assert audio_file is not None
            assert audio_file.name == "podcast.mp3"

    def test_find_audio_file_none(self):
        """Test finding audio files when none exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create non-audio file
            (tmpdir_path / "readme.txt").touch()

            discovery = EpisodeDiscovery()
            audio_file = discovery._find_audio_file(tmpdir_path)

            assert audio_file is None


class TestEpisodeFilter:
    """Test episode filter dataclass."""

    def test_filter_creation(self):
        """Test creating episode filter."""
        filters = EpisodeFilter(
            show="Test Show",
            since="2024-01-01",
            min_duration=3600,
            max_duration=7200,
        )

        assert filters.show == "Test Show"
        assert filters.since == "2024-01-01"
        assert filters.min_duration == 3600
        assert filters.max_duration == 7200

    def test_filter_optional_fields(self):
        """Test filter with optional fields."""
        filters = EpisodeFilter()

        assert filters.show is None
        assert filters.since is None
        assert filters.pattern is None
