#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click  # type: ignore

from .pricing import load_model_catalog, estimate_deepcast_cost


@click.command()
@click.option("--refresh", is_flag=True, help="Refresh cached model lists from providers")
@click.option("--provider", type=click.Choice(["all", "openai", "anthropic"]), default="all")
@click.option("--json", "json_out", is_flag=True, help="Output JSON instead of a table")
@click.option("--filter", "filter_str", help="Substring filter for model names")
@click.option("--estimate", "estimate_input", type=click.Path(exists=True, path_type=Path), help="Estimate cost for a given transcript JSON")
def main(refresh: bool, provider: str, json_out: bool, filter_str: Optional[str], estimate_input: Optional[Path]):
    """List available AI models with pricing, and optionally estimate deepcast cost for a transcript."""
    catalog = load_model_catalog(refresh=refresh)
    if estimate_input:
        transcript = json.loads(estimate_input.read_text())
    else:
        transcript = None

    rows = []
    providers = [provider] if provider != "all" else ["openai", "anthropic"]
    for prov in providers:
        entry = catalog.get(prov) or {}
        models = entry.get("models") or []
        pricing = entry.get("pricing") or {}
        for name in sorted(set(list(models) + list(pricing.keys()))):
            if filter_str and filter_str.lower() not in name.lower():
                continue
            price = pricing.get(name, {})
            desc = price.get("desc", "")
            row = {
                "provider": prov,
                "model": name,
                "price_in": price.get("in"),
                "price_out": price.get("out"),
                "desc": desc,
            }
            if transcript and price:
                est = estimate_deepcast_cost(transcript, prov, name, catalog)
                row.update({
                    "est_usd": est.total_usd,
                    "est_in_tokens": est.input_tokens,
                    "est_out_tokens": est.output_tokens,
                })
            rows.append(row)

    if json_out:
        print(json.dumps({"models": rows}, indent=2))
        return

    # Simple text table (avoid heavy rich to keep this standalone)
    from textwrap import shorten

    headers = ["Provider", "Model", "$In/M", "$Out/M", "Est USD", "Description"]
    print(" | ".join(headers))
    print("-" * 100)
    for r in rows:
        est = f"${r['est_usd']:.2f}" if "est_usd" in r else "-"
        print(
            f"{r['provider']:9} | {r['model']:18} | {str(r['price_in'] or '-') :>6} | {str(r['price_out'] or '-') :>7} | {est:>7} | "
            + shorten(r.get("desc", ""), width=60, placeholder="...")
        )


