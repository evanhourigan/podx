#!/usr/bin/env python3
"""Tests for HTML export formatter."""

import pytest

from podx.core.export import HTMLFormatter


class TestHTMLFormatter:
    """Test HTML export functionality."""

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
                "text": "This is a test of HTML export.",
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
        formatter = HTMLFormatter()
        assert formatter.extension == "html"
        assert formatter.name == "Interactive HTML"

    def test_format_returns_string(self, sample_segments):
        """Test that format returns a string."""
        formatter = HTMLFormatter()
        result = formatter.format(sample_segments)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_contains_html_structure(self, sample_segments):
        """Test that formatted output contains valid HTML structure."""
        formatter = HTMLFormatter()
        html = formatter.format(sample_segments)

        # Check for basic HTML structure
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</html>" in html

    def test_format_contains_dark_mode_toggle(self, sample_segments):
        """Test that HTML includes dark mode toggle functionality."""
        formatter = HTMLFormatter()
        html = formatter.format(sample_segments)

        assert "dark-mode" in html
        assert "theme-toggle" in html or "themeToggle" in html

    def test_format_contains_search_functionality(self, sample_segments):
        """Test that HTML includes search functionality."""
        formatter = HTMLFormatter()
        html = formatter.format(sample_segments)

        assert "search" in html.lower()
        assert "searchBox" in html or "search-box" in html

    def test_format_contains_speaker_legend(self, sample_segments):
        """Test that HTML includes speaker legend."""
        formatter = HTMLFormatter()
        html = formatter.format(sample_segments)

        assert "speaker-legend" in html or "Speaker Legend" in html
        assert "Host" in html
        assert "Guest" in html

    def test_format_contains_timestamps(self, sample_segments):
        """Test that HTML includes timestamps."""
        formatter = HTMLFormatter()
        html = formatter.format(sample_segments)

        assert "timestamp" in html
        # Check for at least one timestamp format
        assert "00:00:00" in html or "0:00" in html

    def test_format_contains_segment_text(self, sample_segments):
        """Test that all segment text is included."""
        formatter = HTMLFormatter()
        html = formatter.format(sample_segments)

        for segment in sample_segments:
            assert segment["text"] in html

    def test_format_empty_segments(self):
        """Test HTML generation with empty segments."""
        formatter = HTMLFormatter()
        html = formatter.format([])

        assert isinstance(html, str)
        assert len(html) > 0
        assert "<!DOCTYPE html>" in html

    def test_format_single_speaker(self):
        """Test HTML generation with single speaker."""
        formatter = HTMLFormatter()
        segments = [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Test message.",
                "speaker": "Solo",
            }
        ]
        html = formatter.format(segments)

        assert "Solo" in html
        assert "speaker-legend" in html or "Speaker Legend" in html

    def test_format_no_speaker_field(self):
        """Test HTML generation with segments missing speaker field."""
        formatter = HTMLFormatter()
        segments = [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Test message without speaker.",
            }
        ]
        html = formatter.format(segments)

        assert isinstance(html, str)
        assert "Test message without speaker." in html
        # Should use "Unknown" or similar default
        assert "Unknown" in html or "Speaker" in html
