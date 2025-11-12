"""Configuration for API client."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ClientConfig:
    """Configuration for PodxClient.

    Attributes:
        default_model: Default ASR model to use
        default_llm_model: Default LLM model for analysis
        output_dir: Default output directory for results
        cache_enabled: Whether to enable result caching
        retry_failed: Whether to retry failed operations
        validate_inputs: Whether to validate inputs before processing
        verbose: Enable verbose logging
    """

    default_model: str = "base"
    default_llm_model: str = "gpt-4o"
    output_dir: Optional[Path] = None
    cache_enabled: bool = True
    retry_failed: bool = True
    validate_inputs: bool = True
    verbose: bool = False
