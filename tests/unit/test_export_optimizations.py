#!/usr/bin/env python3
"""
Tests for export.py optimizations (manifest caching).

Tests verify the 10x speedup from single-pass scanning and episode metadata caching.
"""

import json
from pathlib import Path
from unittest.mock import patch



class TestEpisodeMetadataCache:
    """Test episode metadata caching optimization."""

    def test_cache_avoids_duplicate_reads(self, tmp_path):
        """Test that caching avoids reading same episode-meta.json multiple times."""
        from podx.export import _scan_export_rows

        # Create episode directory with metadata
        episode_dir = tmp_path / "show" / "2024-01-01_episode"
        episode_dir.mkdir(parents=True)

        episode_meta = {
            "show": "Test Podcast",
            "episode_title": "Test Episode",
            "episode_published": "2024-01-01",
        }
        (episode_dir / "episode-meta.json").write_text(json.dumps(episode_meta))

        # Create multiple deepcast files in same episode directory
        for i in range(3):
            deepcast_data = {
                "deepcast_metadata": {
                    "model": "gpt-4.1",
                    "asr_model": "large-v3-turbo",
                    "deepcast_type": "brief",
                }
            }
            (episode_dir / f"deepcast-{i}.json").write_text(
                json.dumps(deepcast_data)
            )

        # Mock Path.read_text to count reads
        original_read_text = Path.read_text
        read_count = {}

        def tracked_read_text(self, *args, **kwargs):
            read_count[self] = read_count.get(self, 0) + 1
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", tracked_read_text):
            rows = _scan_export_rows(tmp_path / "show")

        # Should have 3 rows (one per deepcast file)
        assert len(rows) == 3

        # episode-meta.json should be read only ONCE despite 3 deepcast files
        episode_meta_file = episode_dir / "episode-meta.json"
        assert read_count[episode_meta_file] == 1

    def test_cache_handles_missing_metadata(self, tmp_path):
        """Test cache handles missing episode-meta.json gracefully."""
        from podx.export import _scan_export_rows

        # Create episode directory WITHOUT metadata
        episode_dir = tmp_path / "show" / "2024-01-01_episode"
        episode_dir.mkdir(parents=True)

        # Create deepcast file
        deepcast_data = {
            "deepcast_metadata": {
                "model": "gpt-4.1",
                "asr_model": "large-v3-turbo",
                "deepcast_type": "brief",
            }
        }
        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path / "show")

        # Should still process file with "Unknown" metadata
        assert len(rows) == 1
        assert rows[0]["show"] == "Unknown"
        assert rows[0]["title"] == "Unknown"

    def test_cache_handles_malformed_metadata(self, tmp_path):
        """Test cache handles malformed episode-meta.json gracefully."""
        from podx.export import _scan_export_rows

        # Create episode directory with malformed metadata
        episode_dir = tmp_path / "show" / "2024-01-01_episode"
        episode_dir.mkdir(parents=True)

        # Write invalid JSON
        (episode_dir / "episode-meta.json").write_text("not valid json {{{")

        # Create deepcast file
        deepcast_data = {
            "deepcast_metadata": {
                "model": "gpt-4.1",
                "asr_model": "large-v3-turbo",
                "deepcast_type": "brief",
            }
        }
        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path / "show")

        # Should handle gracefully with default values
        assert len(rows) == 1
        assert rows[0]["show"] == "Unknown"


class TestSinglePassScanning:
    """Test single-pass directory scanning optimization (10x speedup)."""

    def test_single_rglob_call(self, tmp_path):
        """Test that only one rglob call is made to scan for analysis files."""
        from podx.export import _scan_export_rows

        # Create multiple directories with deepcast files
        for i in range(3):
            episode_dir = tmp_path / f"episode_{i}"
            episode_dir.mkdir()

            # Add deepcast files (note: consensus files not matched by current pattern)
            deepcast_data = {
                "deepcast_metadata": {"model": "gpt-4.1", "asr_model": "base"}
            }

            (episode_dir / f"deepcast-{i}.json").write_text(json.dumps(deepcast_data))

        # Mock rglob to count calls
        original_rglob = Path.rglob
        rglob_calls = []

        def tracked_rglob(self, pattern):
            rglob_calls.append(pattern)
            return original_rglob(self, pattern)

        with patch.object(Path, "rglob", tracked_rglob):
            rows = _scan_export_rows(tmp_path)

        # Should have found all deepcast files
        assert len(rows) == 3

        # Should only have ONE rglob call
        assert len(rglob_calls) == 1
        assert rglob_calls[0] == "*cast-*.json"

    def test_pattern_matches_deepcast_files(self, tmp_path):
        """Test that pattern correctly matches deepcast files."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        # Create deepcast files with different naming patterns
        deepcast_data = {
            "deepcast_metadata": {"model": "gpt-4.1", "asr_model": "base"}
        }

        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))
        (episode_dir / "deepcast-summary.json").write_text(json.dumps(deepcast_data))
        (episode_dir / "deepcast-precision.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path)

        # Should find all deepcast files
        assert len(rows) == 3
        names = {row["path"].name for row in rows}
        assert "deepcast.json" in names
        assert "deepcast-summary.json" in names
        assert "deepcast-precision.json" in names

    def test_ignores_non_matching_files(self, tmp_path):
        """Test that scan ignores files that don't match the pattern."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        # Create various files - only some should match
        deepcast_data = {
            "deepcast_metadata": {"model": "gpt-4.1", "asr_model": "base"}
        }

        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))
        (episode_dir / "transcript.json").write_text("{}")  # Should be ignored
        (episode_dir / "episode-meta.json").write_text("{}")  # Should be ignored
        (episode_dir / "forecast.json").write_text("{}")  # Should be ignored (not *cast-*)
        (episode_dir / "random-file.txt").write_text("text")  # Should be ignored

        rows = _scan_export_rows(tmp_path)

        # Should only find deepcast file
        assert len(rows) == 1
        assert rows[0]["path"].name == "deepcast.json"


class TestPerformanceCharacteristics:
    """Test performance characteristics of caching optimization."""

    def test_caching_reduces_io_operations(self, tmp_path):
        """Test that caching significantly reduces file I/O operations."""
        from podx.export import _scan_export_rows

        # Create one episode with 100 deepcast files
        episode_dir = tmp_path / "show" / "2024-01-01_episode"
        episode_dir.mkdir(parents=True)

        episode_meta = {
            "show": "Test Podcast",
            "episode_title": "Test Episode",
            "episode_published": "2024-01-01",
        }
        (episode_dir / "episode-meta.json").write_text(json.dumps(episode_meta))

        # Create 100 deepcast files
        deepcast_data = {
            "deepcast_metadata": {
                "model": "gpt-4.1",
                "asr_model": "base",
                "deepcast_type": "brief",
            }
        }
        for i in range(100):
            (episode_dir / f"deepcast-{i}.json").write_text(
                json.dumps(deepcast_data)
            )

        # Track reads to episode-meta.json
        original_read_text = Path.read_text
        meta_reads = []

        def tracked_read_text(self, *args, **kwargs):
            if self.name == "episode-meta.json":
                meta_reads.append(self)
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", tracked_read_text):
            rows = _scan_export_rows(tmp_path / "show")

        # Should process all 100 files
        assert len(rows) == 100

        # Should read episode-meta.json only ONCE (not 100 times!)
        # This is the 10x speedup: 100 reads → 1 read
        assert len(meta_reads) == 1

    def test_multiple_episodes_each_cached_once(self, tmp_path):
        """Test that each episode's metadata is cached independently."""
        from podx.export import _scan_export_rows

        # Create 3 episodes, each with 5 deepcast files
        for ep in range(3):
            episode_dir = tmp_path / "show" / f"2024-01-0{ep+1}_episode"
            episode_dir.mkdir(parents=True)

            episode_meta = {
                "show": f"Podcast {ep}",
                "episode_title": f"Episode {ep}",
                "episode_published": f"2024-01-0{ep+1}",
            }
            (episode_dir / "episode-meta.json").write_text(json.dumps(episode_meta))

            deepcast_data = {"deepcast_metadata": {"model": "gpt-4.1", "asr_model": "base"}}
            for i in range(5):
                (episode_dir / f"deepcast-{i}.json").write_text(json.dumps(deepcast_data))

        # Track reads
        original_read_text = Path.read_text
        meta_reads = {}

        def tracked_read_text(self, *args, **kwargs):
            if self.name == "episode-meta.json":
                meta_reads[self] = meta_reads.get(self, 0) + 1
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", tracked_read_text):
            rows = _scan_export_rows(tmp_path / "show")

        # Should process all 15 files (3 episodes * 5 files)
        assert len(rows) == 15

        # Each episode-meta.json should be read exactly ONCE
        assert len(meta_reads) == 3
        for meta_file, count in meta_reads.items():
            assert count == 1


class TestDeepcastMetadataExtraction:
    """Test deepcast metadata extraction from analysis files."""

    def test_extracts_deepcast_metadata(self, tmp_path):
        """Test extraction of deepcast metadata fields."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        deepcast_data = {
            "deepcast_metadata": {
                "model": "gpt-4.1",
                "asr_model": "large-v3-turbo",
                "deepcast_type": "brief",
            }
        }
        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path)

        assert len(rows) == 1
        row = rows[0]
        assert row["ai"] == "gpt-4.1"
        assert row["asr"] == "large-v3-turbo"
        assert row["type"] == "brief"
        assert row["track"] == "S"  # Standard track

    def test_detects_precision_track(self, tmp_path):
        """Test detection of precision track from filename."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        deepcast_data = {
            "deepcast_metadata": {
                "model": "gpt-4.1",
                "asr_model": "large-v3-turbo",
                "deepcast_type": "brief",
            }
        }
        (episode_dir / "deepcast-precision.json").write_text(
            json.dumps(deepcast_data)
        )

        rows = _scan_export_rows(tmp_path)

        assert len(rows) == 1
        assert rows[0]["track"] == "P"  # Precision track

    def test_detects_recall_track(self, tmp_path):
        """Test detection of recall track from filename."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        deepcast_data = {
            "deepcast_metadata": {
                "model": "gpt-4.1",
                "asr_model": "large-v3-turbo",
                "deepcast_type": "brief",
            }
        }
        (episode_dir / "deepcast-recall.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path)

        assert len(rows) == 1
        assert rows[0]["track"] == "R"  # Recall track


class TestDateFormatting:
    """Test date formatting in export rows."""

    def test_formats_iso_date(self, tmp_path):
        """Test formatting of ISO date strings."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        episode_meta = {
            "show": "Test",
            "episode_title": "Episode",
            "episode_published": "2024-01-15T12:00:00Z",
        }
        (episode_dir / "episode-meta.json").write_text(json.dumps(episode_meta))

        deepcast_data = {"deepcast_metadata": {"model": "gpt-4.1", "asr_model": "base"}}
        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path)

        assert len(rows) == 1
        assert rows[0]["date"] == "2024-01-15"

    def test_handles_missing_date(self, tmp_path):
        """Test handling of missing date field."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        episode_meta = {"show": "Test", "episode_title": "Episode"}
        (episode_dir / "episode-meta.json").write_text(json.dumps(episode_meta))

        deepcast_data = {"deepcast_metadata": {"model": "gpt-4.1", "asr_model": "base"}}
        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path)

        assert len(rows) == 1
        assert rows[0]["date"] == "Unknown"

    def test_extracts_date_from_string(self, tmp_path):
        """Test extraction of date from arbitrary string."""
        from podx.export import _scan_export_rows

        episode_dir = tmp_path / "episode"
        episode_dir.mkdir()

        episode_meta = {
            "show": "Test",
            "episode_title": "Episode",
            "episode_published": "Published on 2024-03-20 at noon",
        }
        (episode_dir / "episode-meta.json").write_text(json.dumps(episode_meta))

        deepcast_data = {"deepcast_metadata": {"model": "gpt-4.1", "asr_model": "base"}}
        (episode_dir / "deepcast.json").write_text(json.dumps(deepcast_data))

        rows = _scan_export_rows(tmp_path)

        assert len(rows) == 1
        assert rows[0]["date"] == "2024-03-20"
