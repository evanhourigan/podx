#!/usr/bin/env python3
"""
Shared model catalog, pricing, and estimation utilities.

Notes:
- Pricing data here is a curated baseline in USD per 1M tokens.
- Provider model listing APIs generally do not include pricing; we overlay.
- Cache lives at ~/.podx/cache/models.json with a per-provider fetched_at.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional SDKs
try:  # pragma: no cover
    import requests as _requests_module

    requests: Any = _requests_module
except Exception:  # pragma: no cover
    requests = None

CACHE_DIR = Path(os.path.expanduser("~/.podx/cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "models.json"


def _now() -> int:
    return int(time.time())


def _default_pricing_catalog() -> Dict[str, Any]:
    """Curated pricing and descriptions. USD per 1M tokens (Standard tier).

    Updated January 2025 with latest models from OpenAI and Anthropic.

    NOTE: This function now loads data from the centralized model catalog
    (podx/data/models.json) to maintain backward compatibility with existing code.
    The catalog includes models from OpenAI, Anthropic, Google, Meta, DeepSeek,
    Mistral, Cohere, and Ollama.
    """
    from podx.models import list_models

    # Build the legacy format from the centralized catalog
    result: Dict[str, Any] = {}

    # Get all models from the catalog
    all_models = list_models()

    # Group by provider
    for model in all_models:
        provider = model.provider
        if provider not in result:
            result[provider] = {}

        # Add model in legacy format
        result[provider][model.id] = {
            "in": model.pricing.input_per_1m,
            "out": model.pricing.output_per_1m,
            "desc": model.description,
        }

        # Also add aliases as separate entries for backward compatibility
        for alias in model.aliases:
            result[provider][alias] = {
                "in": model.pricing.input_per_1m,
                "out": model.pricing.output_per_1m,
                "desc": f"Alias for {model.name}",
            }

    return result


def _read_cache() -> Dict[str, Any]:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_cache(data: Dict[str, Any]) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def fetch_provider_models(provider: str, api_key: Optional[str]) -> List[str]:
    """Fetch model IDs from provider API. Returns simple list of names.

    We use lightweight HTTP calls to avoid heavy SDK deps; if requests is absent
    or API key missing, returns an empty list and rely on pricing catalog.
    """
    if requests is None or not api_key:
        return []
    try:
        headers = {}
        url = ""
        if provider == "openai":
            headers = {"Authorization": f"Bearer {api_key}"}
            base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
            url = f"{base}/v1/models"
        elif provider == "anthropic":
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
            url = "https://api.anthropic.com/v1/models"
        else:
            return []
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        # OpenAI: {data:[{id:...}]}; Anthropic: {data:[{id:...}]}
        items = data.get("data") or data.get("models") or []
        names = []
        for it in items:
            name = it.get("id") or it.get("name")
            if name:
                names.append(name)
        return sorted(set(names))
    except Exception:
        return []


def load_model_catalog(ttl_seconds: int = 7 * 24 * 3600, refresh: bool = False) -> Dict[str, Any]:
    """Load cached catalog; optionally refresh from providers.

    Returns structure: {
      provider: {
        "fetched_at": epoch,
        "models": ["gpt-4.1", ...],
        "pricing": {model: {in, out, desc}}
      }
    }
    """
    base_pricing = _default_pricing_catalog()
    cache = _read_cache()
    out: Dict[str, Any] = {}
    providers = ["openai", "anthropic"]

    for prov in providers:
        cached = cache.get(prov) or {}
        fetched_at = cached.get("fetched_at", 0)
        should_refresh = refresh or (_now() - fetched_at > ttl_seconds)
        models: List[str] = cached.get("models") or []
        if should_refresh:
            api_key = (
                os.getenv("OPENAI_API_KEY") if prov == "openai" else os.getenv("ANTHROPIC_API_KEY")
            )
            fresh = fetch_provider_models(prov, api_key)
            if fresh:
                models = fresh
                fetched_at = _now()
        # Merge pricing descriptions
        pricing = base_pricing.get(prov, {})
        out[prov] = {"fetched_at": fetched_at, "models": models, "pricing": pricing}

    # Save back
    _write_cache(out)
    return out


@dataclass
class Estimate:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_input_usd: float
    cost_output_usd: float
    total_usd: float


def _chars_to_tokens(chars: int, provider: str) -> int:
    # Rough heuristic: 4 chars/token for OpenAI; 4.5 for Anthropic
    ratio = 4.0 if provider == "openai" else 4.5
    return max(1, int(chars / ratio))


def _estimate_tokens_for_transcript_text(text: str, chunk_chars: int) -> Tuple[int, int]:
    """Return (map_input_tokens, reduce_input_tokens) based on chunking."""
    if not text:
        return (0, 0)
    chunks = max(1, (len(text) + chunk_chars - 1) // chunk_chars)
    # Each map chunk sees ~chunk_chars input; reduce sees concatenated notes (approx 15% of input)
    map_tokens = chunks * _chars_to_tokens(min(len(text), chunk_chars), "openai")
    reduce_tokens = int(_chars_to_tokens(len(text), "openai") * 0.15)
    return (map_tokens, reduce_tokens)


def _extract_text_from_transcript(transcript: Dict[str, Any]) -> str:
    segs = transcript.get("segments") or []
    lines = []
    for s in segs:
        t = s.get("text") or ""
        if t:
            lines.append(t.strip())
    txt = "\n".join(lines)
    if not txt.strip():
        txt = transcript.get("text", "")
    return txt


def estimate_deepcast_cost(
    transcript: Dict[str, Any],
    provider: str,
    model: str,
    pricing_catalog: Dict[str, Any],
    chunk_chars: int = 24000,
    expected_output_tokens_per_chunk: int = 600,  # average tokens per map response
) -> Estimate:
    pricing = pricing_catalog.get(provider, {}).get("pricing", {}).get(model, {})
    rate_in = float(pricing.get("in", 0)) / 1_000_000.0
    rate_out = float(pricing.get("out", 0)) / 1_000_000.0

    text = _extract_text_from_transcript(transcript)
    map_in, reduce_in = _estimate_tokens_for_transcript_text(text, chunk_chars)
    # Number of chunks
    chunks = max(1, (len(text) + chunk_chars - 1) // chunk_chars) if text else 1
    map_out = chunks * expected_output_tokens_per_chunk
    reduce_out = 800  # one reduce response

    total_in = map_in + reduce_in
    total_out = map_out + reduce_out

    cost_in = total_in * rate_in
    cost_out = total_out * rate_out
    total = cost_in + cost_out

    return Estimate(
        provider=provider,
        model=model,
        input_tokens=total_in,
        output_tokens=total_out,
        cost_input_usd=round(cost_in, 4),
        cost_output_usd=round(cost_out, 4),
        total_usd=round(total, 4),
    )
