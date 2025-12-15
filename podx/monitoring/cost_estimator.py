"""Cost estimation for PodX operations.

Estimates costs before running expensive operations like transcription and deepcast.
Pricing data is current as of November 2025.
"""

from typing import Any, Dict, Optional, Union


class CostEstimator:
    """Estimate costs before running operations.

    Provides cost estimates for:
    - Transcription (Whisper API vs local)
    - Deepcast/LLM processing (GPT-4o, Claude, etc.)
    - Full pipeline costs

    Pricing is approximate and based on current API rates.
    """

    # Pricing (as of November 2025)
    # All costs in USD
    PRICING: Dict[str, Dict[str, Union[float, Dict[str, float]]]] = {
        "openai": {
            # GPT models (per 1K tokens)
            "gpt-4o": {"input": 0.0025, "output": 0.010},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4-turbo": {"input": 0.010, "output": 0.030},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            # Whisper (per minute)
            "whisper-1": 0.006,
        },
        "anthropic": {
            # Claude models (per 1K tokens)
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
        },
        "openrouter": {
            # Common OpenRouter models (per 1K tokens)
            "anthropic/claude-3-opus": {"input": 0.015, "output": 0.075},
            "anthropic/claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "openai/gpt-4o": {"input": 0.0025, "output": 0.010},
            "openai/gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        },
    }

    def estimate_transcription(self, duration_minutes: float, provider: str = "openai") -> float:
        """Estimate transcription cost.

        Args:
            duration_minutes: Audio duration in minutes
            provider: "openai" for Whisper API, "local" for free local inference

        Returns:
            Estimated cost in USD
        """
        if provider == "openai":
            whisper_price = self.PRICING["openai"]["whisper-1"]
            if isinstance(whisper_price, (int, float)):
                return duration_minutes * whisper_price
            return 0.0
        elif provider == "local":
            return 0.0  # Local inference is free (electricity costs not included)

        return 0.0

    def estimate_deepcast(
        self,
        text_length: int,
        model: str = "gpt-4o",
        provider: Optional[str] = None,
    ) -> Dict[str, float]:
        """Estimate deepcast/LLM processing cost.

        Args:
            text_length: Length of input text in characters
            model: Model name (e.g., "gpt-4o", "claude-3-sonnet")
            provider: Provider name ("openai", "anthropic", "openrouter")
                     If None, auto-detected from model name

        Returns:
            Dict with:
                - input_tokens: Estimated input tokens
                - output_tokens: Estimated output tokens
                - input_cost: Input cost in USD
                - output_cost: Output cost in USD
                - total_cost: Total cost in USD
        """
        # Estimate tokens (rough: 1 token ≈ 4 characters for English)
        base_tokens = text_length / 4

        # Deepcast uses map-reduce pattern:
        # - Map phase: ~2x text (chunking with overlap)
        # - Reduce phase: ~0.5x text (summaries)
        total_input_tokens = base_tokens * 2.5

        # Output is typically ~0.2x input for summaries
        output_tokens = total_input_tokens * 0.2

        # Auto-detect provider if not specified
        if provider is None:
            if "gpt" in model.lower():
                provider = "openai"
            elif "claude" in model.lower():
                provider = "anthropic"
            elif "/" in model:  # OpenRouter format
                provider = "openrouter"
            else:
                provider = "openai"  # Default

        # Get pricing
        provider_pricing = self.PRICING.get(provider, {})
        pricing: Optional[Dict[str, float]] = None
        if isinstance(provider_pricing, dict):
            model_pricing = provider_pricing.get(model)
            if isinstance(model_pricing, dict):
                pricing = model_pricing
        if pricing is None:
            # Fallback to gpt-4o-mini if model not found
            fallback = self.PRICING["openai"]["gpt-4o-mini"]
            pricing = (
                fallback if isinstance(fallback, dict) else {"input": 0.00015, "output": 0.0006}
            )

        input_cost = (total_input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return {
            "input_tokens": int(total_input_tokens),
            "output_tokens": int(output_tokens),
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
        }

    def estimate_full_pipeline(
        self,
        duration_minutes: float,
        text_length: int,
        asr_provider: str = "local",
        llm_model: str = "gpt-4o",
        llm_provider: Optional[str] = None,
        include_preprocessing: bool = False,
    ) -> Dict[str, float]:
        """Estimate full pipeline cost (transcription + deepcast).

        Args:
            duration_minutes: Audio duration in minutes
            text_length: Estimated transcript length in characters
            asr_provider: "openai" or "local" for transcription
            llm_model: LLM model for deepcast
            llm_provider: LLM provider (auto-detected if None)
            include_preprocessing: Include LLM-based preprocessing cost

        Returns:
            Dict with costs for each stage and total
        """
        costs = {}

        # Transcription
        costs["transcription"] = self.estimate_transcription(duration_minutes, asr_provider)

        # Preprocessing (optional LLM restore/cleanup)
        if include_preprocessing:
            # Use cheaper model for preprocessing
            preprocessing_est = self.estimate_deepcast(text_length, "gpt-4o-mini", "openai")
            costs["preprocessing"] = preprocessing_est["total_cost"] * 0.3
        else:
            costs["preprocessing"] = 0.0

        # Deepcast
        deepcast_est = self.estimate_deepcast(text_length, llm_model, llm_provider)
        costs["deepcast"] = deepcast_est["total_cost"]

        # Total
        costs["total"] = sum(costs.values())

        return costs

    def format_cost(self, cost: float) -> str:
        """Format cost as USD string.

        Args:
            cost: Cost in USD

        Returns:
            Formatted string like "$1.23" or "$0.00"
        """
        if cost == 0.0:
            return "$0.00"
        elif cost < 0.01:
            return f"${cost:.4f}"
        else:
            return f"${cost:.2f}"

    def estimate_from_audio_file(
        self,
        duration_seconds: float,
        transcript_chars: Optional[int] = None,
        asr_provider: str = "local",
        llm_model: str = "gpt-4o",
        include_preprocessing: bool = False,
    ) -> Dict[str, Any]:
        """Estimate costs from audio file metadata.

        Args:
            duration_seconds: Audio duration in seconds
            transcript_chars: Known transcript length (if None, estimated)
            asr_provider: Transcription provider
            llm_model: LLM model for deepcast
            include_preprocessing: Include preprocessing costs

        Returns:
            Dict with duration info and cost breakdown
        """
        duration_minutes = duration_seconds / 60

        # Estimate transcript length if not provided
        # Rough estimate: 150 words per minute, ~5 chars per word
        if transcript_chars is None:
            transcript_chars = int(duration_minutes * 150 * 5)

        costs = self.estimate_full_pipeline(
            duration_minutes=duration_minutes,
            text_length=transcript_chars,
            asr_provider=asr_provider,
            llm_model=llm_model,
            include_preprocessing=include_preprocessing,
        )

        return {
            "duration_seconds": duration_seconds,
            "duration_minutes": duration_minutes,
            "estimated_transcript_chars": transcript_chars,
            "costs": costs,
        }
