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


# NOTE: Curated model lists are now loaded from the centralized catalog.
# Models are filtered by the default_in_cli flag in models.json.
# This eliminates duplication and makes it easy to add/update models.

# NOTE: Provider information is now loaded from the centralized catalog.
# Import the new functions we'll use

# Legacy mapping for backward compatibility with existing code
PROVIDER_API_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama": None,  # No API key required
}

# Provider descriptions for configuration (used for UI display)
# NOTE: Could be loaded from catalog, but keeping for now to minimize changes
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
    # Use centralized catalog
    from podx.models import list_models as catalog_list_models

    catalog = load_model_catalog(refresh=refresh)
    if estimate_input:
        transcript = json.loads(estimate_input.read_text())
    else:
        # Try to auto-detect a transcript
        transcript = _auto_find_transcript()

    rows = []
    providers_to_show = [provider] if provider != "all" else ["openai", "anthropic"]

    for prov in providers_to_show:
        # Get models from centralized catalog
        if show_all or variants:
            # Show all models for this provider
            models = catalog_list_models(provider=prov)
        else:
            # Show only default models
            models = catalog_list_models(provider=prov, default_only=True)

        for model in models:
            # Apply filter if specified
            if filter_str and filter_str.lower() not in model.id.lower():
                continue

            row = {
                "provider": model.provider,
                "model": model.id,
                "price_in": model.pricing.input_per_1m,
                "price_out": model.pricing.output_per_1m,
                "desc": model.description,
            }

            # Add cost estimate if transcript is available
            if transcript:
                est = estimate_deepcast_cost(transcript, model.provider, model.id, catalog)
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

        # Determine if we should show the Est USD column (only if we have estimates)
        has_estimates = any("est_usd" in r for r in rows)

        title = "🤖 Models (USD per 1M tokens"
        if has_estimates:
            title += "; with cost estimates for current transcript"
        title += ")"

        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            border_style=TABLE_BORDER_STYLE,
            title=title,
            expand=False,
        )
        table.add_column("Provider", width=9)
        table.add_column("Model", width=18)
        table.add_column("$In/M", justify="right", width=9)
        table.add_column("$Out/M", justify="right", width=9)
        if has_estimates:
            table.add_column("Est USD", justify="right", width=9)
        table.add_column("Description", justify="left")

        for r in rows:
            # Format prices with proper decimal places
            price_in = r.get("price_in")
            price_out = r.get("price_out")

            # Format with 2 decimal places, but show more if needed
            def format_price(price):
                if price is None:
                    return "None"
                # Check if we need more than 2 decimal places
                if price != round(price, 2):
                    # Has more than 2 decimal places
                    if price != round(price, 3):
                        return f"{price:.4f}"  # 4 decimal places
                    return f"{price:.3f}"  # 3 decimal places
                return f"{price:.2f}"  # 2 decimal places

            in_str = format_price(price_in)
            out_str = format_price(price_out)

            row_data = [
                r["provider"],
                r["model"],
                in_str,
                out_str,
            ]

            if has_estimates:
                est = f"${r['est_usd']:.2f}" if "est_usd" in r else "-"
                row_data.append(est)

            row_data.append(r.get("desc", ""))
            table.add_row(*row_data)
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
