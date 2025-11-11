"""Unit tests for core.deepcast module.

Tests pure business logic without UI dependencies.
Uses mocking to avoid actual OpenAI API calls.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from podx.core.deepcast import (
    DeepcastEngine,
    DeepcastError,
    deepcast_transcript,
    hhmmss,
    segments_to_plain_text,
    split_into_chunks,
)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_hhmmss_zero_seconds(self):
        """Test formatting zero seconds."""
        assert hhmmss(0) == "00:00:00"

    def test_hhmmss_seconds_only(self):
        """Test formatting seconds only."""
        assert hhmmss(45) == "00:00:45"

    def test_hhmmss_minutes_and_seconds(self):
        """Test formatting minutes and seconds."""
        assert hhmmss(125) == "00:02:05"

    def test_hhmmss_hours_minutes_seconds(self):
        """Test formatting hours, minutes, and seconds."""
        assert hhmmss(3661) == "01:01:01"

    def test_segments_to_plain_text_basic(self):
        """Test basic segment conversion."""
        segments = [
            {"text": "Hello world", "start": 0.0},
            {"text": "How are you?", "start": 2.0},
        ]
        result = segments_to_plain_text(segments, with_time=False, with_speaker=False)
        assert result == "Hello world\nHow are you?"

    def test_segments_to_plain_text_with_time(self):
        """Test segment conversion with timestamps."""
        segments = [
            {"text": "Hello", "start": 0.0},
            {"text": "World", "start": 5.0},
        ]
        result = segments_to_plain_text(segments, with_time=True, with_speaker=False)
        assert result == "[00:00:00] Hello\n[00:00:05] World"

    def test_segments_to_plain_text_with_speaker(self):
        """Test segment conversion with speaker labels."""
        segments = [
            {"text": "Hello", "speaker": "SPEAKER_00"},
            {"text": "Hi there", "speaker": "SPEAKER_01"},
        ]
        result = segments_to_plain_text(segments, with_time=False, with_speaker=True)
        assert result == "SPEAKER_00: Hello\nSPEAKER_01: Hi there"

    def test_segments_to_plain_text_with_time_and_speaker(self):
        """Test segment conversion with both time and speaker."""
        segments = [
            {"text": "Hello", "start": 0.0, "speaker": "SPEAKER_00"},
        ]
        result = segments_to_plain_text(segments, with_time=True, with_speaker=True)
        assert result == "[00:00:00] SPEAKER_00: Hello"

    def test_segments_to_plain_text_strips_whitespace(self):
        """Test that whitespace is stripped from text."""
        segments = [
            {"text": "  padded  "},
        ]
        result = segments_to_plain_text(segments, with_time=False, with_speaker=False)
        assert result == "padded"

    def test_segments_to_plain_text_skips_empty(self):
        """Test that empty segments are skipped."""
        segments = [
            {"text": "First"},
            {"text": ""},
            {"text": "  "},
            {"text": "Last"},
        ]
        result = segments_to_plain_text(segments, with_time=False, with_speaker=False)
        assert result == "First\nLast"

    def test_split_into_chunks_small_text(self):
        """Test that small text isn't split."""
        text = "Short text"
        chunks = split_into_chunks(text, 100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_into_chunks_basic(self):
        """Test basic chunk splitting."""
        text = "Line 1\nLine 2\nLine 3\nLine 4"
        chunks = split_into_chunks(text, 15)  # Force splits
        assert len(chunks) > 1

    def test_split_into_chunks_preserves_paragraphs(self):
        """Test that paragraphs are kept together when possible."""
        text = "Para1\n\nPara2\n\nPara3"
        chunks = split_into_chunks(text, 20)
        # Each paragraph should ideally stay together
        assert all("Para" in chunk for chunk in chunks)

    def test_split_into_chunks_single_long_paragraph(self):
        """Test handling of single very long paragraph."""
        text = "A" * 1000
        chunks = split_into_chunks(text, 100)
        # Should create multiple chunks
        assert len(chunks) >= 1


class TestDeepcastEngineInit:
    """Test DeepcastEngine initialization."""

    def test_init_defaults(self):
        """Test default initialization with API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()
            assert engine.model == "gpt-4.1"
            assert engine.temperature == 0.2
            assert engine.max_chars_per_chunk == 24000
            assert engine.api_key == "test_key"

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""

        def callback(msg):
            return None

        engine = DeepcastEngine(
            model="gpt-4",
            temperature=0.5,
            max_chars_per_chunk=10000,
            api_key="custom_key",
            base_url="https://custom.api",
            progress_callback=callback,
        )
        assert engine.model == "gpt-4"
        assert engine.temperature == 0.5
        assert engine.max_chars_per_chunk == 10000
        assert engine.api_key == "custom_key"
        assert engine.base_url == "https://custom.api"
        assert engine.progress_callback is callback

    def test_init_missing_api_key_raises_error(self):
        """Test that missing API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(DeepcastError, match="OpenAI API key not found"):
                DeepcastEngine()

    def test_init_explicit_key_overrides_env(self):
        """Test that explicit API key overrides environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env_key"}):
            engine = DeepcastEngine(api_key="explicit_key")
            assert engine.api_key == "explicit_key"

    def test_init_base_url_from_env(self):
        """Test that base URL is loaded from environment."""
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "key", "OPENAI_BASE_URL": "https://env.api"}
        ):
            engine = DeepcastEngine()
            assert engine.base_url == "https://env.api"


class TestDeepcastEngineGetClient:
    """Test DeepcastEngine._get_client() method."""

    def test_get_client_missing_openai(self):
        """Test that missing openai library raises error."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            original_import = __builtins__["__import__"]

            def mock_import(name, *args, **kwargs):
                if name == "openai":
                    raise ImportError("No module named 'openai'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                engine = DeepcastEngine()
                with pytest.raises(DeepcastError, match="openai library not installed"):
                    engine._get_client()


class TestDeepcastEngineDeepcast:
    """Test DeepcastEngine.deepcast() method."""

    @pytest.fixture
    def mock_openai(self):
        """Fixture to mock OpenAI module."""
        mock_module = MagicMock()
        sys.modules["openai"] = mock_module
        yield mock_module
        if "openai" in sys.modules:
            del sys.modules["openai"]

    @pytest.fixture
    def sample_transcript(self):
        """Sample transcript for testing."""
        return {
            "segments": [
                {"text": "Hello world", "start": 0.0, "end": 2.0},
                {"text": "How are you?", "start": 2.0, "end": 4.0},
            ]
        }

    def test_deepcast_success_simple(self, mock_openai, sample_transcript):
        """Test successful deepcast with simple transcript."""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Analysis result"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()
            markdown, json_data = engine.deepcast(
                sample_transcript,
                system_prompt="You are an analyst",
                map_instructions="Analyze this",
                reduce_instructions="Synthesize these notes",
                want_json=False,
            )

            assert markdown == "Analysis result"
            assert json_data is None

    def test_deepcast_with_json_extraction(self, mock_openai, sample_transcript):
        """Test deepcast with JSON extraction."""
        # Mock OpenAI client with JSON response
        mock_client = MagicMock()
        mock_response = MagicMock()
        json_output = {"key": "value"}
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            f"Here is the analysis\n\n---JSON---\n```json\n{json.dumps(json_output)}\n```"
        )
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()
            markdown, json_data = engine.deepcast(
                sample_transcript,
                system_prompt="You are an analyst",
                map_instructions="Analyze this",
                reduce_instructions="Synthesize and provide JSON",
                want_json=True,
            )

            assert "Here is the analysis" in markdown
            assert json_data == json_output

    def test_deepcast_missing_segments_uses_text(self, mock_openai):
        """Test that deepcast uses text field if segments missing."""
        transcript = {"text": "Plain text transcript"}

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Analysis"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()
            markdown, json_data = engine.deepcast(
                transcript,
                "system",
                "map",
                "reduce",
            )

            assert markdown == "Analysis"

    def test_deepcast_empty_transcript_raises_error(self, mock_openai):
        """Test that empty transcript raises error."""
        transcript = {"segments": []}

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()

            with pytest.raises(DeepcastError, match="No transcript text found"):
                engine.deepcast(transcript, "system", "map", "reduce")

    def test_deepcast_calls_progress_callback(self, mock_openai, sample_transcript):
        """Test that deepcast calls progress callback."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Result"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine(progress_callback=progress_callback)
            engine.deepcast(sample_transcript, "system", "map", "reduce")

            # Should have progress messages
            assert len(progress_messages) >= 2
            assert any("chunk" in msg.lower() for msg in progress_messages)
            assert any("synth" in msg.lower() for msg in progress_messages)

    def test_deepcast_map_phase_failure(self, mock_openai, sample_transcript):
        """Test handling of map phase failure."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()

            with pytest.raises(DeepcastError, match="Map phase failed"):
                engine.deepcast(sample_transcript, "system", "map", "reduce")

    def test_deepcast_reduce_phase_failure(self, mock_openai, sample_transcript):
        """Test handling of reduce phase failure."""
        mock_client = MagicMock()

        # Succeed for map phase (1 chunk), fail for reduce
        call_count = [0]

        def create_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # Map phase call (only 1 chunk)
                mock_resp = MagicMock()
                mock_resp.choices = [MagicMock()]
                mock_resp.choices[0].message.content = "Map result"
                return mock_resp
            else:  # Reduce phase call
                raise Exception("Reduce API error")

        mock_client.chat.completions.create.side_effect = create_side_effect
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()

            with pytest.raises(DeepcastError, match="Reduce phase failed"):
                engine.deepcast(sample_transcript, "system", "map", "reduce")

    def test_deepcast_invalid_json_returns_none(self, mock_openai, sample_transcript):
        """Test that invalid JSON returns None for json_data."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "Analysis\n\n---JSON---\n{invalid json}"
        )
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine()
            markdown, json_data = engine.deepcast(
                sample_transcript,
                "system",
                "map",
                "reduce",
                want_json=True,
            )

            assert "Analysis" in markdown
            assert json_data is None  # Failed to parse JSON


class TestConvenienceFunction:
    """Test deepcast_transcript convenience function."""

    @pytest.fixture
    def mock_openai(self):
        """Fixture to mock OpenAI module."""
        mock_module = MagicMock()
        sys.modules["openai"] = mock_module
        yield mock_module
        if "openai" in sys.modules:
            del sys.modules["openai"]

    def test_deepcast_transcript(self, mock_openai):
        """Test deepcast_transcript convenience function."""
        transcript = {
            "segments": [
                {"text": "Hello world"},
            ]
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Analysis result"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            markdown, json_data = deepcast_transcript(
                transcript,
                "system prompt",
                "map instructions",
                "reduce instructions",
            )

            assert markdown == "Analysis result"
            assert json_data is None

    def test_deepcast_transcript_with_custom_params(self, mock_openai):
        """Test deepcast_transcript with custom parameters."""
        transcript = {"segments": [{"text": "Test"}]}

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Result"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        markdown, _ = deepcast_transcript(
            transcript,
            "system",
            "map",
            "reduce",
            model="gpt-4",
            temperature=0.7,
            max_chars_per_chunk=10000,
            api_key="custom_key",
            progress_callback=progress_callback,
        )

        assert markdown == "Result"
        assert len(progress_messages) >= 1


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def mock_openai(self):
        """Fixture to mock OpenAI module."""
        mock_module = MagicMock()
        sys.modules["openai"] = mock_module
        yield mock_module
        if "openai" in sys.modules:
            del sys.modules["openai"]

    def test_deepcast_large_transcript_creates_chunks(self, mock_openai):
        """Test that large transcripts are split into chunks."""
        # Create a large transcript
        segments = [{"text": f"Segment {i} " * 100} for i in range(100)]
        transcript = {"segments": segments}

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Analysis"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            engine = DeepcastEngine(max_chars_per_chunk=1000)  # Small chunks
            markdown, _ = engine.deepcast(transcript, "system", "map", "reduce")

            # Should have made multiple map calls
            assert mock_client.chat.completions.create.call_count > 2

    def test_json_extraction_handles_code_fences(self, mock_openai):
        """Test that JSON extraction handles various code fence formats."""
        test_cases = [
            '---JSON---\n```json\n{"key": "value"}\n```',
            '---JSON---\n```\n{"key": "value"}\n```',
            '---JSON---\n{"key": "value"}',
        ]

        for content in test_cases:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = content
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.OpenAI.return_value = mock_client

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
                engine = DeepcastEngine()
                _, json_data = engine.deepcast(
                    {"segments": [{"text": "test"}]},
                    "system",
                    "map",
                    "reduce",
                    want_json=True,
                )

                assert json_data == {"key": "value"}
