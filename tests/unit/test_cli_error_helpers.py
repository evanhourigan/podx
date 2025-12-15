#!/usr/bin/env python3
"""Tests for CLI error helpers."""

import tempfile
from pathlib import Path

from podx.cli.error_helpers import find_similar_files, format_error_message


class TestFormatErrorMessage:
    """Test error message formatting."""

    def test_basic_error_message(self):
        """Test basic error message."""
        message = format_error_message(
            title="Something went wrong", message="Details about the error"
        )

        assert "✗ Error:" in message
        assert "Something went wrong" in message
        assert "Details about the error" in message

    def test_error_with_suggestions(self):
        """Test error message with suggestions."""
        message = format_error_message(
            title="File not found",
            message="The file does not exist",
            suggestions=[
                "Check the file path",
                "Verify the file exists",
            ],
        )

        assert "Suggestions:" in message
        assert "Check the file path" in message
        assert "Verify the file exists" in message

    def test_error_with_similar_files(self):
        """Test error message with similar files."""
        similar_files = [Path("test1.txt"), Path("test2.txt")]

        message = format_error_message(
            title="File not found",
            message="Could not find file",
            similar_files=similar_files,
        )

        assert "Did you mean one of these?" in message
        assert "test1.txt" in message
        assert "test2.txt" in message

    def test_error_with_docs_link(self):
        """Test error message with documentation link."""
        message = format_error_message(
            title="Invalid model",
            message="Model not recognized",
            docs_link="https://docs.example.com/models",
        )

        assert "Documentation:" in message
        assert "https://docs.example.com/models" in message


class TestFindSimilarFiles:
    """Test similar file finding."""

    def test_find_similar_files_exact_match(self):
        """Test finding files with exact substring match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "podcast.mp3").touch()
            (tmpdir_path / "podcast-episode-1.mp3").touch()
            (tmpdir_path / "other.mp3").touch()

            # Search for similar files
            target = tmpdir_path / "podcast-missing.mp3"
            similar = find_similar_files(target, pattern="*.mp3")

            # Should find files with "podcast" in the name
            similar_names = [f.name for f in similar]
            assert "podcast.mp3" in similar_names
            assert "podcast-episode-1.mp3" in similar_names

    def test_find_similar_files_by_extension(self):
        """Test finding files by extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "file1.mp3").touch()
            (tmpdir_path / "file2.mp3").touch()
            (tmpdir_path / "file3.txt").touch()

            # Search for similar files
            target = tmpdir_path / "missing.mp3"
            similar = find_similar_files(target, pattern="*")

            # Should find mp3 files
            extensions = [f.suffix for f in similar]
            assert ".mp3" in extensions

    def test_find_similar_files_max_results(self):
        """Test limiting number of results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create many test files
            for i in range(10):
                (tmpdir_path / f"file{i}.mp3").touch()

            # Search with limit
            target = tmpdir_path / "missing.mp3"
            similar = find_similar_files(target, pattern="*.mp3", max_results=3)

            # Should return only 3 results
            assert len(similar) <= 3

    def test_find_similar_files_no_matches(self):
        """Test when no similar files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create unrelated files
            (tmpdir_path / "unrelated1.txt").touch()
            (tmpdir_path / "unrelated2.txt").touch()

            # Search for mp3 files
            target = tmpdir_path / "missing.mp3"
            similar = find_similar_files(target, pattern="*.mp3")

            # Should return empty list
            assert len(similar) == 0
