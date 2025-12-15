"""Tests for quote extraction."""

from __future__ import annotations

import pytest

from podx.domain.models.transcript import DiarizedSegment, Transcript
from podx.search.quotes import QuoteExtractor


@pytest.fixture
def sample_transcript() -> Transcript:
    """Create sample transcript with quotable content."""
    segments = [
        DiarizedSegment(
            start=0.0,
            end=5.0,
            text="I think the key to success is hard work and dedication.",
            speaker="Alice",
        ),
        DiarizedSegment(
            start=5.0,
            end=8.0,
            text="um yeah like you know",
            speaker="Bob",
        ),
        DiarizedSegment(
            start=8.0,
            end=12.0,
            text="The truth is that innovation requires taking risks and learning from failures.",
            speaker="Alice",
        ),
        DiarizedSegment(
            start=12.0,
            end=14.0,
            text="What time is it?",
            speaker="Bob",
        ),
        DiarizedSegment(
            start=14.0,
            end=18.0,
            text="Remember that every challenge is an opportunity to grow stronger.",
            speaker="Alice",
        ),
    ]
    return Transcript(segments=segments)


def test_extract_quotes_basic(sample_transcript: Transcript) -> None:
    """Test basic quote extraction."""
    extractor = QuoteExtractor(min_words=5, max_words=100)
    quotes = extractor.extract_quotes(sample_transcript, max_quotes=10)

    assert len(quotes) > 0
    assert all(q["word_count"] >= 5 for q in quotes)


def test_quote_scoring(sample_transcript: Transcript) -> None:
    """Test quote quality scoring."""
    extractor = QuoteExtractor()
    quotes = extractor.extract_quotes(sample_transcript, max_quotes=10)

    # Should exclude filler text
    assert not any("um yeah like" in q["text"] for q in quotes)

    # Should include quotable content
    quotable_texts = [q["text"] for q in quotes]
    assert any("key to success" in text for text in quotable_texts)


def test_speaker_filter(sample_transcript: Transcript) -> None:
    """Test filtering by speaker."""
    extractor = QuoteExtractor()
    quotes = extractor.extract_quotes(sample_transcript, max_quotes=10, speaker_filter="Alice")

    assert len(quotes) > 0
    assert all(q["speaker"] == "Alice" for q in quotes)


def test_extract_by_speaker(sample_transcript: Transcript) -> None:
    """Test grouping quotes by speaker."""
    extractor = QuoteExtractor()
    results = extractor.extract_by_speaker(sample_transcript, top_n=3)

    assert "Alice" in results
    assert len(results["Alice"]) > 0


def test_find_highlights(sample_transcript: Transcript) -> None:
    """Test finding highlight moments."""
    extractor = QuoteExtractor()
    highlights = extractor.find_highlights(sample_transcript, duration_threshold=30.0)

    # Should find at least one highlight
    assert len(highlights) > 0

    for highlight in highlights:
        assert highlight["quote_count"] >= 2
        # Duration should be positive (end - start)
        assert highlight["end"] >= highlight["start"]


def test_word_count_limits() -> None:
    """Test word count filtering."""
    segments = [
        DiarizedSegment(start=0.0, end=2.0, text="Too short", speaker="Alice"),
        DiarizedSegment(
            start=2.0,
            end=5.0,
            text="This is a good length for a quote with meaningful content",
            speaker="Alice",
        ),
        DiarizedSegment(
            start=5.0,
            end=10.0,
            text=" ".join(["word"] * 120),  # Too long
            speaker="Alice",
        ),
    ]
    transcript = Transcript(segments=segments)

    extractor = QuoteExtractor(min_words=5, max_words=100)
    quotes = extractor.extract_quotes(transcript, max_quotes=10)

    # Should only get the middle one
    assert len(quotes) == 1
    assert 5 <= quotes[0]["word_count"] <= 100


def test_score_range() -> None:
    """Test that scores are in valid range."""
    segments = [
        DiarizedSegment(
            start=0.0,
            end=5.0,
            text="I think this is a meaningful statement about something important.",
            speaker="Alice",
        ),
    ]
    transcript = Transcript(segments=segments)

    extractor = QuoteExtractor()
    quotes = extractor.extract_quotes(transcript, max_quotes=10)

    for quote in quotes:
        assert 0.0 <= quote["score"] <= 1.0
