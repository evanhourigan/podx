#!/usr/bin/env python3
"""
Centralized model catalog with pricing, capabilities, and provider information.

This module loads the models.json catalog and provides a unified interface for
querying model information, pricing data, and provider configuration. It eliminates
DRY violations by centralizing all model metadata in a single source of truth.

The catalog is loaded once at module import time (singleton pattern) and cached
in memory for fast access.

Example usage:
    from podx.models import get_model, list_models, get_provider, check_api_key

    # Get model by ID or alias (case-insensitive)
    model = get_model("gpt5.1")  # Works with "gpt-5.1", "GPT5.1", etc.
    print(f"Price: ${model.pricing.input_per_1m}/M input")

    # List all models for a provider
    openai_models = list_models(provider="openai")

    # Get provider configuration
    provider = get_provider("openai")
    print(f"API Key: {provider.api_key_env}")

    # Check if API key is configured
    if not check_api_key("anthropic"):
        print("Please set ANTHROPIC_API_KEY")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Path to the JSON catalog (same directory as this module)
_CATALOG_PATH = Path(__file__).parent / "models.json"


@dataclass
class ModelPricing:
    """Model pricing information."""

    input_per_1m: float
    output_per_1m: float
    currency: str
    tier: str
    notes: Optional[str] = None

    def __repr__(self) -> str:
        return f"${self.input_per_1m}/${ self.output_per_1m} per 1M tokens"


@dataclass
class Model:
    """Represents a language model with its metadata and pricing."""

    id: str
    name: str
    provider: str
    aliases: List[str]
    description: str
    pricing: ModelPricing
    context_window: int
    capabilities: List[str]
    default_in_cli: bool

    @property
    def all_identifiers(self) -> List[str]:
        """Return all valid identifiers for this model (ID + aliases)."""
        return [self.id] + self.aliases


@dataclass
class Provider:
    """Represents an LLM provider with configuration details."""

    key: str
    name: str
    api_key_env: Optional[str]
    base_url_env: Optional[str]
    default_base_url: str
    docs_url: str


class ModelCatalog:
    """
    Centralized model catalog with fast lookup capabilities.

    This class loads the models.json file once and provides various query
    methods for accessing model and provider information.
    """

    def __init__(self, catalog_path: Path = _CATALOG_PATH):
        """Initialize the catalog from JSON file.

        Args:
            catalog_path: Path to the models.json file

        Raises:
            FileNotFoundError: If catalog file doesn't exist
            ValueError: If catalog JSON is invalid
        """
        if not catalog_path.exists():
            raise FileNotFoundError(
                f"Model catalog not found: {catalog_path}\n"
                "This is likely a package installation issue."
            )

        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in model catalog: {e}")

        self.version = data.get("version")
        self.last_updated = data.get("last_updated")

        # Parse providers
        self._providers: Dict[str, Provider] = {}
        for key, prov_data in data.get("providers", {}).items():
            self._providers[key] = Provider(
                key=key,
                name=prov_data["name"],
                api_key_env=prov_data.get("api_key_env"),
                base_url_env=prov_data.get("base_url_env"),
                default_base_url=prov_data["default_base_url"],
                docs_url=prov_data["docs_url"],
            )

        # Parse models
        self._models: Dict[str, Model] = {}
        self._alias_map: Dict[str, str] = {}  # alias -> model_id (lowercase)

        for model_data in data.get("models", []):
            pricing_data = model_data["pricing"]
            pricing = ModelPricing(
                input_per_1m=pricing_data["input_per_1m"],
                output_per_1m=pricing_data["output_per_1m"],
                currency=pricing_data["currency"],
                tier=pricing_data["tier"],
                notes=pricing_data.get("notes"),
            )

            model = Model(
                id=model_data["id"],
                name=model_data["name"],
                provider=model_data["provider"],
                aliases=model_data.get("aliases", []),
                description=model_data["description"],
                pricing=pricing,
                context_window=model_data["context_window"],
                capabilities=model_data["capabilities"],
                default_in_cli=model_data.get("default_in_cli", False),
            )

            # Store model by ID (lowercase for case-insensitive lookup)
            model_id_lower = model.id.lower()
            self._models[model_id_lower] = model

            # Build alias map (all lowercase)
            for alias in model.aliases:
                alias_lower = alias.lower()
                if alias_lower in self._alias_map:
                    # Warn about duplicate aliases, but continue
                    pass  # Could log warning here
                self._alias_map[alias_lower] = model_id_lower

    def get_model(self, model_id_or_alias: str) -> Model:
        """Get a model by ID or alias (case-insensitive).

        Args:
            model_id_or_alias: Model ID (e.g., "gpt-5.1") or alias (e.g., "gpt5.1")

        Returns:
            Model object with full metadata

        Raises:
            KeyError: If model not found
        """
        lookup = model_id_or_alias.lower()

        # Try direct ID lookup first
        if lookup in self._models:
            return self._models[lookup]

        # Try alias lookup
        if lookup in self._alias_map:
            model_id = self._alias_map[lookup]
            return self._models[model_id]

        # Not found - provide helpful error message
        raise KeyError(
            f"Model not found: '{model_id_or_alias}'\n"
            f"Use list_models() to see available models, or check for typos."
        )

    def list_models(
        self,
        provider: Optional[str] = None,
        default_only: bool = False,
        capability: Optional[str] = None,
    ) -> List[Model]:
        """List models with optional filtering.

        Args:
            provider: Filter by provider (e.g., "openai", "anthropic")
            default_only: If True, only include models marked as default_in_cli
            capability: Filter by capability (e.g., "vision", "function-calling")

        Returns:
            List of Model objects, sorted by provider then by ID
        """
        models = list(self._models.values())

        # Apply filters
        if provider:
            provider_lower = provider.lower()
            models = [m for m in models if m.provider == provider_lower]

        if default_only:
            models = [m for m in models if m.default_in_cli]

        if capability:
            capability_lower = capability.lower()
            models = [m for m in models if capability_lower in m.capabilities]

        # Sort by provider, then by ID
        models.sort(key=lambda m: (m.provider, m.id))

        return models

    def get_provider(self, provider_name: str) -> Provider:
        """Get provider configuration.

        Args:
            provider_name: Provider key (e.g., "openai", "anthropic")

        Returns:
            Provider object with configuration

        Raises:
            KeyError: If provider not found
        """
        provider_lower = provider_name.lower()

        if provider_lower not in self._providers:
            available = ", ".join(sorted(self._providers.keys()))
            raise KeyError(
                f"Provider not found: '{provider_name}'\n" f"Available providers: {available}"
            )

        return self._providers[provider_lower]

    def list_providers(self) -> List[Provider]:
        """List all providers.

        Returns:
            List of Provider objects, sorted by key
        """
        return sorted(self._providers.values(), key=lambda p: p.key)

    def check_api_key(self, provider_name: str) -> bool:
        """Check if API key is configured for a provider.

        Args:
            provider_name: Provider key (e.g., "openai", "anthropic")

        Returns:
            True if API key is configured (or not required), False otherwise
        """
        try:
            provider = self.get_provider(provider_name)
        except KeyError:
            return False

        # If provider doesn't require an API key (e.g., Ollama), return True
        if provider.api_key_env is None:
            return True

        # Check if environment variable is set
        api_key = os.getenv(provider.api_key_env)
        return bool(api_key)

    def get_api_key(self, provider_name: str) -> Optional[str]:
        """Get the API key for a provider from environment.

        Args:
            provider_name: Provider key (e.g., "openai", "anthropic")

        Returns:
            API key string if configured, None otherwise
        """
        try:
            provider = self.get_provider(provider_name)
        except KeyError:
            return None

        if provider.api_key_env is None:
            return None

        return os.getenv(provider.api_key_env)


# ============================================================================
# Module-level singleton instance and convenience functions
# ============================================================================

# Load catalog once at module import (singleton pattern)
_catalog: Optional[ModelCatalog] = None


def _get_catalog() -> ModelCatalog:
    """Get or initialize the singleton catalog instance."""
    global _catalog
    if _catalog is None:
        _catalog = ModelCatalog()
    return _catalog


def get_model(model_id_or_alias: str) -> Model:
    """Get a model by ID or alias (case-insensitive).

    This is a convenience function that uses the module-level singleton catalog.

    Args:
        model_id_or_alias: Model ID (e.g., "gpt-5.1") or alias (e.g., "gpt5.1")

    Returns:
        Model object with full metadata

    Raises:
        KeyError: If model not found
    """
    return _get_catalog().get_model(model_id_or_alias)


def list_models(
    provider: Optional[str] = None,
    default_only: bool = False,
    capability: Optional[str] = None,
) -> List[Model]:
    """List models with optional filtering.

    This is a convenience function that uses the module-level singleton catalog.

    Args:
        provider: Filter by provider (e.g., "openai", "anthropic")
        default_only: If True, only include models marked as default_in_cli
        capability: Filter by capability (e.g., "vision", "function-calling")

    Returns:
        List of Model objects, sorted by provider then by ID
    """
    return _get_catalog().list_models(
        provider=provider,
        default_only=default_only,
        capability=capability,
    )


def get_provider(provider_name: str) -> Provider:
    """Get provider configuration.

    This is a convenience function that uses the module-level singleton catalog.

    Args:
        provider_name: Provider key (e.g., "openai", "anthropic")

    Returns:
        Provider object with configuration

    Raises:
        KeyError: If provider not found
    """
    return _get_catalog().get_provider(provider_name)


def list_providers() -> List[Provider]:
    """List all providers.

    This is a convenience function that uses the module-level singleton catalog.

    Returns:
        List of Provider objects, sorted by key
    """
    return _get_catalog().list_providers()


def check_api_key(provider_name: str) -> bool:
    """Check if API key is configured for a provider.

    This is a convenience function that uses the module-level singleton catalog.

    Args:
        provider_name: Provider key (e.g., "openai", "anthropic")

    Returns:
        True if API key is configured (or not required), False otherwise
    """
    return _get_catalog().check_api_key(provider_name)


def get_api_key(provider_name: str) -> Optional[str]:
    """Get the API key for a provider from environment.

    This is a convenience function that uses the module-level singleton catalog.

    Args:
        provider_name: Provider key (e.g., "openai", "anthropic")

    Returns:
        API key string if configured, None otherwise
    """
    return _get_catalog().get_api_key(provider_name)


# ============================================================================
# Backward compatibility helpers
# ============================================================================


def get_pricing_for_model(model_id_or_alias: str) -> Dict[str, Any]:
    """Get pricing data in legacy format for backward compatibility.

    Returns pricing in the format expected by legacy code:
    {"in": float, "out": float, "desc": str}

    Args:
        model_id_or_alias: Model ID or alias

    Returns:
        Dictionary with "in", "out", and "desc" keys

    Raises:
        KeyError: If model not found
    """
    model = get_model(model_id_or_alias)
    return {
        "in": model.pricing.input_per_1m,
        "out": model.pricing.output_per_1m,
        "desc": model.description,
    }
