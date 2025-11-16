#!/usr/bin/env python3
"""Tests for PDF export formatter."""

import tempfile
from pathlib import Path

import pytest

from podx.core.export import PDFFormatter


class TestPDFFormatter:
    """Test PDF export functionality."""

    @pytest.fixture
    def sample_segments(self):
        """Sample transcript segments for testing."""
        return [
            {
                "start": 0.0,
                "end": 3.5,
                "text": "Welcome to the test transcript.",
                "speaker": "Host",
            },
            {
                "start": 3.5,
                "end": 8.2,
                "text": "This is a test of PDF export.",
                "speaker": "Host",
            },
            {
                "start": 8.2,
                "end": 12.0,
                "text": "Testing speaker labels.",
                "speaker": "Guest",
            },
            {
                "start": 12.0,
                "end": 15.5,
                "text": "And timestamps too.",
                "speaker": "Host",
            },
        ]

    def test_formatter_properties(self):
        """Test formatter basic properties."""
        formatter = PDFFormatter()
        assert formatter.extension == "pdf"
        assert formatter.name == "PDF Document"

    def test_write_pdf_creates_file(self, sample_segments):
        """Test that write_pdf creates a PDF file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.pdf"
            formatter = PDFFormatter()

            formatter.write_pdf(
                segments=sample_segments,
                output_path=str(output_path),
                title="Test Transcript",
            )

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_write_pdf_with_metadata(self, sample_segments):
        """Test PDF generation with metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.pdf"
            formatter = PDFFormatter()

            metadata = {
                "show": "Test Podcast",
                "date": "2024-01-01",
                "duration": 15.5,
                "speakers": ["Host", "Guest"],
            }

            formatter.write_pdf(
                segments=sample_segments,
                output_path=str(output_path),
                title="Test Transcript",
                metadata=metadata,
            )

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_write_pdf_handles_string_duration(self, sample_segments):
        """Test that string durations are handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.pdf"
            formatter = PDFFormatter()

            metadata = {
                "duration": "15.5s",  # String duration
                "speakers": 2,  # Integer speaker count
            }

            formatter.write_pdf(
                segments=sample_segments,
                output_path=str(output_path),
                title="Test Transcript",
                metadata=metadata,
            )

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_write_pdf_empty_segments(self):
        """Test PDF generation with empty segments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.pdf"
            formatter = PDFFormatter()

            formatter.write_pdf(
                segments=[],
                output_path=str(output_path),
                title="Empty Transcript",
            )

            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_write_pdf_no_metadata(self, sample_segments):
        """Test PDF generation without metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.pdf"
            formatter = PDFFormatter()

            formatter.write_pdf(
                segments=sample_segments,
                output_path=str(output_path),
                title="Test Transcript",
                metadata=None,
            )

            assert output_path.exists()
            assert output_path.stat().st_size > 0
