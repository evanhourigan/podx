"""Tests for LLM provider abstraction."""

import pytest

from podx.llm import LLMMessage, LLMProviderError, LLMResponse, MockLLMProvider, get_provider


class TestLLMMessage:
    """Test LLMMessage class."""

    def test_create_message(self):
        """Test creating a message."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_to_dict(self):
        """Test converting message to dict."""
        msg = LLMMessage(role="system", content="You are helpful")
        assert msg.to_dict() == {"role": "system", "content": "You are helpful"}

    def test_system_constructor(self):
        """Test system message constructor."""
        msg = LLMMessage.system("System prompt")
        assert msg.role == "system"
        assert msg.content == "System prompt"

    def test_user_constructor(self):
        """Test user message constructor."""
        msg = LLMMessage.user("User query")
        assert msg.role == "user"
        assert msg.content == "User query"

    def test_assistant_constructor(self):
        """Test assistant message constructor."""
        msg = LLMMessage.assistant("Assistant response")
        assert msg.role == "assistant"
        assert msg.content == "Assistant response"


class TestLLMResponse:
    """Test LLMResponse class."""

    def test_create_response(self):
        """Test creating a response."""
        resp = LLMResponse(content="Hello!", model="gpt-4")
        assert resp.content == "Hello!"
        assert resp.model == "gpt-4"
        assert resp.usage is None
        assert resp.raw_response is None

    def test_response_with_usage(self):
        """Test response with token usage."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        resp = LLMResponse(content="Test", model="gpt-4", usage=usage)
        assert resp.usage == usage
        assert resp.usage["total_tokens"] == 30


class TestMockLLMProvider:
    """Test MockLLMProvider."""

    def test_single_response(self):
        """Test provider with single response."""
        mock = MockLLMProvider(responses=["Hello!"])
        messages = [LLMMessage.user("Hi")]

        resp = mock.complete(messages, model="test-model")

        assert resp.content == "Hello!"
        assert resp.model == "test-model"
        assert mock.call_count == 1
        assert len(mock.calls) == 1

    def test_multiple_responses(self):
        """Test provider with multiple responses."""
        mock = MockLLMProvider(responses=["First", "Second", "Third"])

        resp1 = mock.complete([LLMMessage.user("Q1")], model="test")
        resp2 = mock.complete([LLMMessage.user("Q2")], model="test")
        resp3 = mock.complete([LLMMessage.user("Q3")], model="test")

        assert resp1.content == "First"
        assert resp2.content == "Second"
        assert resp3.content == "Third"
        assert mock.call_count == 3

    def test_response_cycling(self):
        """Test that responses cycle when exhausted."""
        mock = MockLLMProvider(responses=["A", "B"])

        resp1 = mock.complete([LLMMessage.user("Q1")], model="test")
        resp2 = mock.complete([LLMMessage.user("Q2")], model="test")
        resp3 = mock.complete([LLMMessage.user("Q3")], model="test")  # Cycles back

        assert resp1.content == "A"
        assert resp2.content == "B"
        assert resp3.content == "A"  # Back to first

    def test_call_tracking(self):
        """Test that calls are tracked correctly."""
        mock = MockLLMProvider(responses=["Response"])
        messages = [LLMMessage.user("Test")]

        mock.complete(messages, model="gpt-4", temperature=0.5)

        assert len(mock.calls) == 1
        call_messages, call_model, call_temp = mock.calls[0]
        assert call_messages == messages
        assert call_model == "gpt-4"
        assert call_temp == 0.5

    def test_reset(self):
        """Test resetting call tracking."""
        mock = MockLLMProvider(responses=["Test"])

        mock.complete([LLMMessage.user("Q1")], model="test")
        mock.complete([LLMMessage.user("Q2")], model="test")

        assert mock.call_count == 2
        assert len(mock.calls) == 2

        mock.reset()

        assert mock.call_count == 0
        assert len(mock.calls) == 0

    def test_set_responses(self):
        """Test updating responses."""
        mock = MockLLMProvider(responses=["Original"])

        resp1 = mock.complete([LLMMessage.user("Q1")], model="test")
        assert resp1.content == "Original"

        mock.set_responses(["Updated"])
        resp2 = mock.complete([LLMMessage.user("Q2")], model="test")

        assert resp2.content == "Updated"
        assert mock.call_count == 1  # Reset by set_responses

    @pytest.mark.asyncio
    async def test_async_complete(self):
        """Test async completion."""
        mock = MockLLMProvider(responses=["Async response"])

        resp = await mock.complete_async([LLMMessage.user("Test")], model="test")

        assert resp.content == "Async response"
        assert mock.call_count == 1

    def test_supports_streaming(self):
        """Test streaming support check."""
        mock = MockLLMProvider()
        assert not mock.supports_streaming()

    def test_get_available_models(self):
        """Test getting available models."""
        mock = MockLLMProvider()
        models = mock.get_available_models()
        assert "mock-model-1" in models
        assert "mock-model-2" in models


class TestProviderFactory:
    """Test provider factory functions."""

    def test_get_provider_invalid_name(self):
        """Test getting provider with invalid name."""
        with pytest.raises(LLMProviderError, match="Provider 'invalid' not found"):
            get_provider("invalid")

    def test_get_provider_openai_no_key(self):
        """Test OpenAI provider without API key raises error."""
        # This will fail if OPENAI_API_KEY is not set
        import os

        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(Exception):  # Will raise auth error
                get_provider("openai")
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key


class TestDeepcastEngineWithMock:
    """Test AnalyzeEngine with mock LLM provider."""

    def test_analyze_with_mock_provider(self):
        """Test analyze using mock provider."""
        from podx.core.analyze import AnalyzeEngine

        # Create mock with pre-defined responses
        mock = MockLLMProvider(
            responses=[
                "Map note 1",  # First chunk
                "Final synthesis",  # Reduce phase
            ]
        )

        # Create engine with mock provider
        engine = AnalyzeEngine(
            model="test-model",
            temperature=0.5,
            llm_provider=mock,
        )

        # Small transcript (single chunk)
        transcript = {
            "segments": [
                {"text": "Hello world", "start": 0.0, "end": 1.0},
            ]
        }

        # Run analyze
        result, json_data = engine.analyze(
            transcript=transcript,
            system_prompt="Test system",
            map_instructions="Analyze",
            reduce_instructions="Synthesize",
        )

        assert result == "Final synthesis"
        assert json_data is None
        assert mock.call_count == 2  # Map + reduce


class TestPreprocessEngineWithMock:
    """Test PreprocessEngine with mock LLM provider."""

    def test_preprocess_with_mock_provider(self):
        """Test preprocessing with mock provider."""
        from podx.core.preprocess import TranscriptPreprocessor

        # Create mock provider
        mock = MockLLMProvider(
            responses=[
                "Cleaned segment one.\n---SEGMENT---\nCleaned segment two.",
            ]
        )

        # Create preprocessor with mock
        preprocessor = TranscriptPreprocessor(
            restore=True,
            restore_batch_size=20,
            llm_provider=mock,
        )

        # Test semantic restore
        texts = ["segment one", "segment two"]
        restored = preprocessor.semantic_restore(texts)

        assert len(restored) == 2
        assert restored[0] == "Cleaned segment one."
        assert restored[1] == "Cleaned segment two."
        assert mock.call_count == 1
