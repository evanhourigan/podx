"""Tests for the --show-prompt feature in deepcast."""

from podx.deepcast import deepcast
from podx.prompt_templates import PodcastType


def test_show_prompt_all_mode():
    """Test that show_prompt_only='all' returns all prompts without calling API."""
    # Create a minimal transcript
    transcript = {
        "show": "Test Podcast",
        "episode_title": "Test Episode",
        "episode_published": "2025-01-01",
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Hello, welcome to the show.",
                "speaker": "HOST",
            },
            {
                "start": 5.0,
                "end": 10.0,
                "text": "Thanks for having me.",
                "speaker": "GUEST",
            },
        ],
    }

    # Call deepcast with show_prompt_only="all"
    # This should not make any API calls
    prompt_display, json_data = deepcast(
        transcript=transcript,
        model="gpt-4.1-mini",
        temperature=0.2,
        max_chars_per_chunk=1000,
        want_json=True,
        podcast_type=PodcastType.INTERVIEW,
        show_prompt_only="all",
    )

    # Verify we got a string output (the formatted prompts)
    assert isinstance(prompt_display, str)
    assert len(prompt_display) > 0

    # Verify json_data is None (no actual analysis was done)
    assert json_data is None

    # Verify the prompt display contains expected sections
    assert "SYSTEM PROMPT" in prompt_display
    assert "MAP PHASE PROMPTS" in prompt_display
    assert "REDUCE PHASE PROMPT" in prompt_display
    assert "JSON SCHEMA REQUEST" in prompt_display
    assert "END OF PROMPTS" in prompt_display

    # Verify it contains the actual transcript text
    assert "Hello, welcome to the show" in prompt_display
    assert "Thanks for having me" in prompt_display


def test_show_prompt_system_only_mode():
    """Test that show_prompt_only='system_only' returns only the system prompt."""
    # Create a minimal transcript
    transcript = {
        "show": "Test Podcast",
        "episode_title": "Test Episode",
        "episode_published": "2025-01-01",
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Hello, welcome to the show.",
                "speaker": "HOST",
            },
            {
                "start": 5.0,
                "end": 10.0,
                "text": "Thanks for having me.",
                "speaker": "GUEST",
            },
        ],
    }

    # Call deepcast with show_prompt_only="system_only"
    prompt_display, json_data = deepcast(
        transcript=transcript,
        model="gpt-4.1-mini",
        temperature=0.2,
        max_chars_per_chunk=1000,
        want_json=True,
        podcast_type=PodcastType.INTERVIEW,
        show_prompt_only="system_only",
    )

    # Verify we got a string output
    assert isinstance(prompt_display, str)
    assert len(prompt_display) > 0

    # Verify json_data is None
    assert json_data is None

    # Verify the prompt display contains ONLY the system prompt section
    assert "SYSTEM PROMPT" in prompt_display
    assert "END OF PROMPTS" in prompt_display

    # Verify it does NOT contain the other sections
    assert "MAP PHASE PROMPTS" not in prompt_display
    assert "REDUCE PHASE PROMPT" not in prompt_display
    assert "JSON SCHEMA REQUEST" not in prompt_display

    # Verify it does NOT contain the actual transcript text
    assert "Hello, welcome to the show" not in prompt_display
    assert "Thanks for having me" not in prompt_display


def test_show_prompt_with_longer_transcript():
    """Test show_prompt with multiple chunks."""
    # Create a longer transcript that will be split into multiple chunks
    segments = []
    for i in range(100):
        segments.append(
            {
                "start": float(i * 10),
                "end": float(i * 10 + 10),
                "text": f"This is segment {i}. " * 20,  # Make it longer
                "speaker": f"SPEAKER_{i % 3}",
            }
        )

    transcript = {
        "show": "Test Podcast",
        "episode_title": "Long Episode",
        "segments": segments,
    }

    # Use a small chunk size to force multiple chunks
    prompt_display, json_data = deepcast(
        transcript=transcript,
        model="gpt-4.1-mini",
        temperature=0.2,
        max_chars_per_chunk=1000,  # Small chunks to test multi-chunk handling
        want_json=True,
        podcast_type=PodcastType.GENERAL,
        show_prompt_only="all",
    )

    assert isinstance(prompt_display, str)
    assert json_data is None

    # Should have multiple chunks
    assert "Chunk 1/" in prompt_display
    assert "MAP PROMPT" in prompt_display

    # Verify chunks are numbered
    chunk_count = prompt_display.count("MAP PROMPT")
    assert chunk_count > 1  # Should have multiple chunks
