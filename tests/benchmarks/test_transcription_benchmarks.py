"""Benchmarks for transcription utility operations."""
import pytest

from podx.core.transcribe import parse_model_and_provider


class TestModelParserBenchmarks:
    """Benchmark model/provider parsing utility."""

    @pytest.fixture
    def model_inputs(self):
        """Various model input formats to benchmark."""
        return [
            # Simple model names
            "small",
            "medium",
            "large-v3",
            "large-v3-turbo",
            "distil-large-v3",
            # Provider prefixes
            "local:large-v3",
            "openai:large-v3-turbo",
            "hf:distil-large-v3",
            # Edge cases
            "unknown-model",
            "",
        ]

    def test_parse_model_simple(self, benchmark):
        """Benchmark parsing simple model name."""
        result = benchmark(parse_model_and_provider, "large-v3")
        assert result[0] == "local"
        assert result[1] == "large-v3"

    def test_parse_model_with_prefix(self, benchmark):
        """Benchmark parsing model with provider prefix."""
        result = benchmark(parse_model_and_provider, "openai:large-v3-turbo")
        assert result[0] == "openai"
        assert result[1] == "whisper-1"

    def test_parse_model_with_explicit_provider(self, benchmark):
        """Benchmark parsing with explicit provider argument."""
        result = benchmark(parse_model_and_provider, "large-v3", "openai")
        assert result[0] == "openai"
        assert result[1] == "whisper-1"

    def test_parse_model_hf_alias(self, benchmark):
        """Benchmark parsing Hugging Face model alias."""
        result = benchmark(parse_model_and_provider, "hf:distil-large-v3")
        assert result[0] == "hf"
        assert result[1] == "distil-whisper/distil-large-v3"

    def test_parse_model_default(self, benchmark):
        """Benchmark parsing empty/default model."""
        result = benchmark(parse_model_and_provider, "")
        assert result[0] == "local"
        assert result[1] == "small"

    def test_parse_model_batch(self, benchmark, model_inputs):
        """Benchmark parsing batch of different model formats."""

        def parse_batch():
            results = []
            for model in model_inputs:
                results.append(parse_model_and_provider(model))
            return results

        results = benchmark(parse_batch)
        assert len(results) == len(model_inputs)
