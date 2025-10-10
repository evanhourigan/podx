#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any, List

import click  # type: ignore

from .pricing import load_model_catalog, estimate_deepcast_cost

try:  # pragma: no cover
    from rich.table import Table
    from rich.panel import Panel
    from .ui import make_console, TABLE_BORDER_STYLE, TABLE_HEADER_STYLE
    RICH_AVAILABLE = True
except Exception:  # pragma: no cover
    RICH_AVAILABLE = False


CURATED_OPENAI = [
    # Flagship and common families
    "gpt-5",
    "gpt-5-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
    # Popular/legacy families users still ask for
    "o3",
    "o3-mini",
    "o4",
    "o4-mini",
    "gpt-3.5",
    "gpt-3.5-turbo",
]
CURATED_ANTHROPIC = [
    "claude-4.5-sonnet",
    "claude-4-sonnet",
    "claude-3-5-sonnet",
    "claude-3-5-haiku",
    "claude-3-opus",
]


def _auto_find_transcript() -> Optional[Dict[str, Any]]:
    # Prefer ./latest.json, then newest transcript-*.json in cwd
    here = Path.cwd()
    latest = here / "latest.json"
    if latest.exists():
        try:
            return json.loads(latest.read_text())
        except Exception:
            pass
    candidates: List[Path] = sorted(here.glob("transcript-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in candidates:
        try:
            return json.loads(p.read_text())
        except Exception:
            continue
    return None


@click.command()
@click.option("--refresh", is_flag=True, help="Refresh cached model lists from providers")
@click.option("--provider", type=click.Choice(["all", "openai", "anthropic"]), default="all")
@click.option("--json", "json_out", is_flag=True, help="Output JSON instead of a table")
@click.option("--filter", "filter_str", help="Substring filter for model names")
@click.option("--estimate", "estimate_input", type=click.Path(exists=True, path_type=Path), help="Estimate cost for a given transcript JSON")
@click.option("--all", "show_all", is_flag=True, help="Show all provider models (not only curated)")
def main(refresh: bool, provider: str, json_out: bool, filter_str: Optional[str], estimate_input: Optional[Path], show_all: bool):
    """List available AI models with pricing, and optionally estimate deepcast cost for a transcript."""
    catalog = load_model_catalog(refresh=refresh)
    if estimate_input:
        transcript = json.loads(estimate_input.read_text())
    else:
        # Try to auto-detect a transcript
        transcript = _auto_find_transcript()

    rows = []
    providers = [provider] if provider != "all" else ["openai", "anthropic"]
    for prov in providers:
        entry = catalog.get(prov) or {}
        models = entry.get("models") or []
        pricing = entry.get("pricing") or {}
        curated = CURATED_OPENAI if prov == "openai" else CURATED_ANTHROPIC
        if show_all:
            names = sorted(set(list(models) + list(pricing.keys())))
        else:
            # Include any provider models that start with curated families, plus the
            # curated family names themselves and any priced variants that match.
            names_set = set()
            for m in models:
                if any(m.startswith(f) for f in curated):
                    names_set.add(m)
            for p in pricing.keys():
                if any(p.startswith(f) for f in curated):
                    names_set.add(p)
            for fam in curated:
                names_set.add(fam)
            names = sorted(names_set)
        for name in sorted(set(names)):
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

    if RICH_AVAILABLE:
        console = make_console()
        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            border_style=TABLE_BORDER_STYLE,
            title="🤖 Models (USD per 1M tokens; estimates use current transcript if found)",
            expand=False,
        )
        table.add_column("Provider", width=9)
        table.add_column("Model", width=18)
        table.add_column("$In/M", justify="right", width=7)
        table.add_column("$Out/M", justify="right", width=7)
        table.add_column("Est USD", justify="right", width=9)
        table.add_column("Description", justify="left")
        for r in rows:
            est = f"${r['est_usd']:.2f}" if "est_usd" in r else "-"
            table.add_row(
                r["provider"],
                r["model"],
                str(r.get("price_in", "-")),
                str(r.get("price_out", "-")),
                est,
                r.get("desc", ""),
            )
        console.print(table)
        if not transcript:
            console.print(Panel("Tip: run in an episode folder (with latest.json) or pass --estimate to see per-episode cost.", border_style=TABLE_BORDER_STYLE))
    else:
        # Fallback plain output
        headers = ["Provider", "Model", "$In/M", "$Out/M", "Est USD", "Description"]
        print(" | ".join(headers))
        print("-" * 100)
        for r in rows:
            est = f"${r['est_usd']:.2f}" if "est_usd" in r else "-"
            print(
                f"{r['provider']:9} | {r['model']:18} | {str(r['price_in'] or '-') :>6} | {str(r['price_out'] or '-') :>7} | {est:>7} | {r.get('desc','')}"
            )


