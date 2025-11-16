#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import click  # type: ignore

from podx.pricing import estimate_deepcast_cost, load_model_catalog

try:  # pragma: no cover
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table

    from podx.ui import TABLE_BORDER_STYLE, TABLE_HEADER_STYLE, make_console

    RICH_AVAILABLE = True
except Exception:  # pragma: no cover
    RICH_AVAILABLE = False


# Canonical family names to display by default (ordered)
CURATED_OPENAI = [
    # Flagship and common families
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-pro",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
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
    "claude-4.1-opus",
    "claude-4.5-sonnet",
    "claude-4-sonnet",
    "claude-3-5-sonnet",
    "claude-3-5-haiku",
    "claude-3-opus",
]

# API key environment variables for each provider
PROVIDER_API_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama": None,  # No API key required
}

# Provider descriptions for configuration
PROVIDER_INFO = {
    "openai": {
        "name": "OpenAI",
        "url": "https://platform.openai.com/api-keys",
        "description": "GPT-4, GPT-3.5, and other OpenAI models",
    },
    "anthropic": {
        "name": "Anthropic",
        "url": "https://console.anthropic.com/settings/keys",
        "description": "Claude models (Opus, Sonnet, Haiku)",
    },
    "openrouter": {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/keys",
        "description": "Access multiple models through one API",
    },
    "ollama": {
        "name": "Ollama",
        "url": "https://ollama.ai",
        "description": "Local models (no API key required)",
    },
}


def _get_api_key_status(provider: str) -> tuple[bool, Optional[str]]:
    """Check if API key is configured for a provider.

    Args:
        provider: Provider name (openai, anthropic, etc.)

    Returns:
        Tuple of (is_configured, env_var_name)
    """
    env_var = PROVIDER_API_KEYS.get(provider)
    if env_var is None:
        # Provider doesn't require API key (e.g., Ollama)
        return True, None

    api_key = os.getenv(env_var)
    return bool(api_key), env_var


def _show_api_key_status() -> None:
    """Display API key configuration status for all providers."""
    if not RICH_AVAILABLE:
        print("Provider API Key Status")
        print("-" * 60)
        for provider in ["openai", "anthropic", "openrouter", "ollama"]:
            is_configured, env_var = _get_api_key_status(provider)
            status_str = "✓ Configured" if is_configured else "✗ Not configured"
            info = PROVIDER_INFO[provider]
            print(f"{info['name']:12} {status_str:20} {env_var or 'N/A'}")
        return

    console = make_console()

    # Title
    console.print("\n[bold cyan]API Key Configuration Status[/bold cyan]\n")

    # Status table
    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        border_style=TABLE_BORDER_STYLE,
        expand=False,
    )
    table.add_column("Provider", width=12)
    table.add_column("Status", width=15)
    table.add_column("Environment Variable", width=25)
    table.add_column("Description", justify="left")

    for provider in ["openai", "anthropic", "openrouter", "ollama"]:
        is_configured, env_var = _get_api_key_status(provider)
        info = PROVIDER_INFO[provider]

        if env_var is None:
            status_text = "[dim]N/A (local)[/dim]"
            env_var_text = "[dim]Not required[/dim]"
        elif is_configured:
            status_text = "[green]✓ Configured[/green]"
            env_var_text = env_var
        else:
            status_text = "[red]✗ Not configured[/red]"
            env_var_text = f"[yellow]{env_var}[/yellow]"

        table.add_row(info["name"], status_text, env_var_text, info["description"])

    console.print(table)

    # Show instructions
    unconfigured = [
        provider
        for provider in ["openai", "anthropic", "openrouter"]
        if not _get_api_key_status(provider)[0]
    ]

    if unconfigured:
        console.print(
            f"\n[yellow]⚠[/yellow]  {len(unconfigured)} provider(s) not configured"
        )
        console.print(
            "\n[dim]Run[/dim] [cyan]podx-models --configure[/cyan] [dim]to set up API keys[/dim]\n"
        )
    else:
        console.print("\n[green]✓[/green] All providers configured!\n")


def _configure_api_keys() -> None:
    """Interactive wizard to configure API keys."""
    if not RICH_AVAILABLE:
        print("Error: Rich library required for interactive configuration")
        print("Install with: pip install 'podx[dev]'")
        return

    console = make_console()

    # Welcome
    console.print("\n[bold cyan]API Key Configuration Wizard[/bold cyan]\n")
    console.print(
        "This wizard will help you configure API keys for LLM providers.\n"
        "API keys will be displayed as environment variable export commands.\n"
        "[dim]You'll need to add these to your shell profile (~/.zshrc, ~/.bashrc, etc.)[/dim]\n"
    )

    configured_providers = []
    export_commands = []

    for provider in ["openai", "anthropic", "openrouter"]:
        is_configured, env_var = _get_api_key_status(provider)
        info = PROVIDER_INFO[provider]

        console.print(f"\n[bold]{info['name']}[/bold]")
        console.print(f"[dim]{info['description']}[/dim]")

        if is_configured:
            console.print(f"[green]✓ Already configured ({env_var})[/green]")
            skip = Confirm.ask("Do you want to update this key?", default=False)
            if not skip:
                continue

        console.print(f"\n[dim]Get your API key at: {info['url']}[/dim]")

        # Prompt for API key
        api_key = Prompt.ask(
            f"Enter your {info['name']} API key (or press Enter to skip)",
            password=True,
            default="",
        )

        if api_key:
            export_commands.append(f'export {env_var}="{api_key}"')
            configured_providers.append(info["name"])
        else:
            console.print(f"[dim]Skipped {info['name']}[/dim]")

    # Show results
    console.print("\n" + "=" * 60 + "\n")

    if export_commands:
        console.print("[bold green]✓ Configuration complete![/bold green]\n")
        console.print(
            "[bold]Next steps:[/bold] Add these commands to your shell profile:\n"
        )

        for cmd in export_commands:
            console.print(f"  [cyan]{cmd}[/cyan]")

        console.print("\n[bold]Then reload your shell:[/bold]")
        console.print("  [cyan]source ~/.zshrc[/cyan]  # or ~/.bashrc\n")

        console.print("[dim]Or set them in your current session:[/dim]")
        for cmd in export_commands:
            console.print(f"  [dim]{cmd}[/dim]")

        console.print(
            f"\n[green]Configured providers:[/green] {', '.join(configured_providers)}"
        )
    else:
        console.print("[yellow]No API keys configured.[/yellow]")
        console.print(
            "\nRun [cyan]podx-models --status[/cyan] to check current configuration.\n"
        )


def _auto_find_transcript() -> Optional[Dict[str, Any]]:
    # Prefer ./latest.json, then newest transcript-*.json in cwd
    here = Path.cwd()
    latest = here / "latest.json"
    if latest.exists():
        try:
            return json.loads(latest.read_text())
        except Exception:
            pass
    candidates: List[Path] = sorted(
        here.glob("transcript-*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for p in candidates:
        try:
            return json.loads(p.read_text())
        except Exception:
            continue
    return None


@click.command()
@click.option(
    "--refresh", is_flag=True, help="Refresh cached model lists from providers"
)
@click.option(
    "--provider", type=click.Choice(["all", "openai", "anthropic"]), default="all"
)
@click.option("--json", "json_out", is_flag=True, help="Output JSON instead of a table")
@click.option("--filter", "filter_str", help="Substring filter for model names")
@click.option(
    "--estimate",
    "estimate_input",
    type=click.Path(exists=True, path_type=Path),
    help="Estimate cost for a given transcript JSON",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all provider models (not only curated)",
)
@click.option(
    "--variants",
    is_flag=True,
    help="Include dated/preview variants instead of family-only view",
)
@click.option(
    "--status",
    is_flag=True,
    help="Show API key configuration status for each provider",
)
@click.option(
    "--configure",
    is_flag=True,
    help="Interactive setup wizard for API keys",
)
def main(
    refresh: bool,
    provider: str,
    json_out: bool,
    filter_str: Optional[str],
    estimate_input: Optional[Path],
    show_all: bool,
    variants: bool,
    status: bool,
    configure: bool,
):
    """List available AI models with pricing, and optionally estimate deepcast cost for a transcript."""
    # Handle --status flag
    if status:
        _show_api_key_status()
        return

    # Handle --configure flag
    if configure:
        _configure_api_keys()
        return
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
        if show_all or variants:
            names = sorted(set(list(models) + list(pricing.keys())))
        else:
            # Family-only view: show one canonical entry per curated family.
            names = []
            for fam in curated:
                # Prefer exact family id; otherwise pick the newest provider model starting with the family
                if fam in models or fam in pricing:
                    names.append(fam)
                else:
                    candidates = [m for m in models if m.startswith(fam)]
                    if candidates:
                        # Heuristic: pick lexicographically max as newest
                        names.append(sorted(candidates)[-1])
        for name in sorted(set(names)):
            if filter_str and filter_str.lower() not in name.lower():
                continue
            # Inherit pricing/desc from family key if exact price not available
            price = pricing.get(name, {})
            if not price:
                base_keys = list(pricing.keys())
                for k in base_keys:
                    if name.startswith(k):
                        price = pricing.get(k, {})
                        break
            desc = price.get("desc", "")
            row = {
                "provider": prov,
                "model": (
                    name
                    if (show_all or variants)
                    else (next((fam for fam in curated if name.startswith(fam)), name))
                ),
                "price_in": price.get("in"),
                "price_out": price.get("out"),
                "desc": desc,
            }
            if transcript and price:
                est = estimate_deepcast_cost(transcript, prov, name, catalog)
                row.update(
                    {
                        "est_usd": est.total_usd,
                        "est_in_tokens": est.input_tokens,
                        "est_out_tokens": est.output_tokens,
                    }
                )
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
            console.print(
                Panel(
                    "Tip: run in an episode folder (with latest.json) or pass --estimate to see per-episode cost.",
                    border_style=TABLE_BORDER_STYLE,
                )
            )
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
