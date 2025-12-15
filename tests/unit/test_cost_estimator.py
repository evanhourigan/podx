#!/usr/bin/env python3
"""Tests for cost estimator."""

import pytest

from podx.monitoring import CostEstimator


class TestCostEstimator:
    """Test cost estimation functionality."""

    @pytest.fixture
    def estimator(self):
        """Create cost estimator instance."""
        return CostEstimator()

    def test_estimate_transcription_local(self, estimator):
        """Test that local transcription is free."""
        cost = estimator.estimate_transcription(60.0, provider="local")
        assert cost == 0.0

    def test_estimate_transcription_openai(self, estimator):
        """Test OpenAI Whisper cost estimation."""
        # 60 minutes at $0.006 per minute
        cost = estimator.estimate_transcription(60.0, provider="openai")
        assert cost == 60.0 * 0.006
        assert cost == 0.36

    def test_estimate_deepcast_gpt4o(self, estimator):
        """Test GPT-4o deepcast cost estimation."""
        # Estimate for 10,000 characters
        text_length = 10_000
        result = estimator.estimate_deepcast(text_length, model="gpt-4o")

        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "input_cost" in result
        assert "output_cost" in result
        assert "total_cost" in result

        # Should have reasonable token estimates
        # ~2,500 base tokens (10k chars / 4)
        # ~6,250 total input tokens (2.5x for map-reduce)
        assert result["input_tokens"] > 0
        assert result["output_tokens"] > 0
        assert result["total_cost"] > 0

    def test_estimate_deepcast_claude(self, estimator):
        """Test Claude cost estimation."""
        text_length = 10_000
        result = estimator.estimate_deepcast(
            text_length, model="claude-3-sonnet", provider="anthropic"
        )

        assert result["total_cost"] > 0
        assert "input_tokens" in result
        assert "output_tokens" in result
        assert "input_cost" in result
        assert "output_cost" in result

    def test_estimate_deepcast_auto_provider(self, estimator):
        """Test auto-detection of provider from model name."""
        # Should auto-detect openai
        gpt_result = estimator.estimate_deepcast(10_000, model="gpt-4o")
        assert gpt_result["total_cost"] > 0

        # Should auto-detect anthropic
        claude_result = estimator.estimate_deepcast(10_000, model="claude-3-sonnet")
        assert claude_result["total_cost"] > 0

    def test_estimate_full_pipeline_local_asr(self, estimator):
        """Test full pipeline with local ASR."""
        duration_minutes = 60.0
        text_length = 45_000  # ~60 min * 150 words/min * 5 chars/word

        result = estimator.estimate_full_pipeline(
            duration_minutes=duration_minutes,
            text_length=text_length,
            asr_provider="local",
            llm_model="gpt-4o",
        )

        assert "transcription" in result
        assert "preprocessing" in result
        assert "deepcast" in result
        assert "total" in result

        # Local transcription should be free
        assert result["transcription"] == 0.0

        # Preprocessing should be 0 by default
        assert result["preprocessing"] == 0.0

        # Deepcast should have cost
        assert result["deepcast"] > 0

        # Total should equal sum
        assert result["total"] == sum(
            [result["transcription"], result["preprocessing"], result["deepcast"]]
        )

    def test_estimate_full_pipeline_openai_asr(self, estimator):
        """Test full pipeline with OpenAI ASR."""
        duration_minutes = 60.0
        text_length = 45_000

        result = estimator.estimate_full_pipeline(
            duration_minutes=duration_minutes,
            text_length=text_length,
            asr_provider="openai",
            llm_model="gpt-4o-mini",
        )

        # OpenAI transcription should have cost
        assert result["transcription"] > 0

        # Total should be sum of all stages
        assert result["total"] == sum(
            [result["transcription"], result["preprocessing"], result["deepcast"]]
        )

    def test_estimate_full_pipeline_with_preprocessing(self, estimator):
        """Test full pipeline with preprocessing enabled."""
        result = estimator.estimate_full_pipeline(
            duration_minutes=60.0,
            text_length=45_000,
            asr_provider="local",
            llm_model="gpt-4o",
            include_preprocessing=True,
        )

        # Preprocessing should have cost when enabled
        assert result["preprocessing"] > 0

    def test_format_cost(self, estimator):
        """Test cost formatting."""
        assert estimator.format_cost(0.0) == "$0.00"
        assert estimator.format_cost(1.23) == "$1.23"
        assert estimator.format_cost(0.005) == "$0.0050"
        assert estimator.format_cost(12.5) == "$12.50"

    def test_estimate_from_audio_file(self, estimator):
        """Test estimation from audio file metadata."""
        duration_seconds = 5010.0  # 83.5 minutes
        result = estimator.estimate_from_audio_file(
            duration_seconds=duration_seconds,
            asr_provider="local",
            llm_model="gpt-4o",
        )

        assert "duration_seconds" in result
        assert "duration_minutes" in result
        assert "estimated_transcript_chars" in result
        assert "costs" in result

        assert result["duration_seconds"] == duration_seconds
        assert result["duration_minutes"] == duration_seconds / 60

        # Should auto-estimate transcript length
        assert result["estimated_transcript_chars"] > 0

        # Costs should be present
        costs = result["costs"]
        assert "transcription" in costs
        assert "deepcast" in costs
        assert "total" in costs

    def test_estimate_from_audio_file_known_transcript_length(self, estimator):
        """Test estimation with known transcript length."""
        duration_seconds = 5010.0
        known_length = 50_000

        result = estimator.estimate_from_audio_file(
            duration_seconds=duration_seconds,
            transcript_chars=known_length,
            asr_provider="openai",
            llm_model="claude-3-haiku",
        )

        # Should use provided transcript length
        assert result["estimated_transcript_chars"] == known_length

    def test_pricing_data_structure(self, estimator):
        """Test that pricing data has expected structure."""
        assert "openai" in estimator.PRICING
        assert "anthropic" in estimator.PRICING
        assert "openrouter" in estimator.PRICING

        # Check OpenAI has models
        assert "gpt-4o" in estimator.PRICING["openai"]
        assert "gpt-4o-mini" in estimator.PRICING["openai"]
        assert "whisper-1" in estimator.PRICING["openai"]

        # Check model pricing structure
        gpt4o = estimator.PRICING["openai"]["gpt-4o"]
        assert "input" in gpt4o
        assert "output" in gpt4o

    def test_unknown_model_fallback(self, estimator):
        """Test that unknown models fall back gracefully."""
        result = estimator.estimate_deepcast(10_000, model="unknown-model-xyz", provider="openai")

        # Should fall back to gpt-4o-mini
        assert result["total_cost"] >= 0
