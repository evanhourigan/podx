"""
Centralized model catalog for PodX.

This module provides a single source of truth for all LLM model information,
including pricing, capabilities, and provider configuration. It eliminates
code duplication and makes it easy to add new models or update pricing.

Public API:
    - get_model(model_id_or_alias) - Get model by ID or alias
    - list_models(provider, default_only, capability) - List/filter models
    - get_provider(provider_name) - Get provider configuration
    - list_providers() - List all providers
    - check_api_key(provider_name) - Check if API key is configured
    - get_api_key(provider_name) - Get API key from environment
    - get_pricing_for_model(model_id_or_alias) - Get pricing in legacy format

Data classes:
    - Model - Represents a language model with metadata
    - ModelPricing - Model pricing information
    - Provider - Provider configuration details

Example usage:
    >>> from podx.models import get_model, list_models
    >>> model = get_model("gpt5.1")  # Case-insensitive, supports aliases
    >>> print(f"{model.name}: ${model.pricing.input_per_1m}/M")
    >>> openai_models = list_models(provider="openai", default_only=True)
"""

from podx.models.catalog import (
    Model,
    ModelCatalog,
    ModelPricing,
    Provider,
    check_api_key,
    get_api_key,
    get_model,
    get_pricing_for_model,
    get_provider,
    list_models,
    list_providers,
)

__all__ = [
    # Data classes
    "Model",
    "ModelPricing",
    "Provider",
    "ModelCatalog",
    # Query functions
    "get_model",
    "list_models",
    "get_provider",
    "list_providers",
    "check_api_key",
    "get_api_key",
    # Backward compatibility
    "get_pricing_for_model",
]
