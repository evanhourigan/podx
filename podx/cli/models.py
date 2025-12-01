#!/usr/bin/env python3
"""List AI models with pricing.

Simple display of available models for transcription and analysis.
"""

from __future__ import annotations

import click

try:
    from rich.table import Table

    from podx.ui import TABLE_BORDER_STYLE, TABLE_HEADER_STYLE, make_console

    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False


@click.command(context_settings={"max_content_width": 120})
def main():
    """List available AI models with pricing.

    Shows models for transcription (ASR) and analysis (LLM) with
    estimated cost per hour of podcast audio.
    """
    from podx.models import list_models

    if not RICH_AVAILABLE:
        print("AI Models for PodX")
        print("=" * 70)
        print("\nASR Models (Transcription):")
        print("  local:large-v3-turbo  Best quality, optimized (free)")
        print("  local:large-v3        Best quality (free)")
        print("  local:medium          Good balance (free)")
        print("  openai:whisper-1      Cloud ($0.006/min)")
        print("\nLLM Models (Analysis):")
        print("  Run with Rich installed for detailed pricing table")
        return

    console = make_console()

    # ASR Models section
    console.print("\n[bold cyan]ASR Models (Transcription)[/bold cyan]\n")

    asr_table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        border_style=TABLE_BORDER_STYLE,
        expand=False,
    )
    asr_table.add_column("Model", width=22, no_wrap=True)
    asr_table.add_column("$/hr", justify="right", width=10)
    asr_table.add_column("Description")

    asr_models = [
        ("local:large-v3-turbo", "Free", "Best quality, optimized for speed"),
        ("local:large-v3", "Free", "Best quality, slightly slower"),
        ("local:large-v2", "Free", "Previous generation best quality"),
        ("local:medium", "Free", "Good balance of speed and quality"),
        ("local:base", "Free", "Fast transcription, lower accuracy"),
        ("local:tiny", "Free", "Fastest transcription, lowest accuracy"),
        ("openai:whisper-1", "$0.36", "OpenAI cloud transcription API"),
        ("hf:distil-large-v3", "Free", "Distilled model, faster than large-v3"),
    ]

    for model, cost, desc in asr_models:
        asr_table.add_row(model, cost, desc)

    console.print(asr_table)

    # LLM Models section
    console.print("\n[bold cyan]LLM Models (Analysis)[/bold cyan]\n")

    llm_table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        border_style=TABLE_BORDER_STYLE,
        expand=False,
    )
    llm_table.add_column("Model", width=30, no_wrap=True)
    llm_table.add_column("$/hr*", justify="right", width=10)
    llm_table.add_column("Description")

    # Get models from catalog, show defaults only
    try:
        models = list_models(default_only=True)

        for model in models:
            # Calculate $/hr estimate (assuming ~15k tokens/hr of podcast)
            # Input: ~15k tokens, Output: ~3k tokens (analysis is shorter)
            input_tokens = 15000
            output_tokens = 3000
            input_cost = (input_tokens / 1_000_000) * model.pricing.input_per_1m
            output_cost = (output_tokens / 1_000_000) * model.pricing.output_per_1m
            hourly_cost = input_cost + output_cost

            # Show "< $0.01" for very cheap models instead of "$0.00"
            if hourly_cost < 0.01 and hourly_cost > 0:
                cost_str = "< $0.01"
            else:
                cost_str = f"${hourly_cost:.2f}"
            llm_table.add_row(
                f"{model.provider}:{model.id}", cost_str, model.description or ""
            )
    except Exception:
        # Fallback if catalog fails
        llm_table.add_row("openai:gpt-4o", "$0.08", "Best quality (default)")
        llm_table.add_row("openai:gpt-4o-mini", "$0.01", "Good quality, lower cost")
        llm_table.add_row("anthropic:claude-sonnet-4-5", "$0.10", "Great alternative")

    console.print(llm_table)

    console.print(
        "\n[dim]* Estimated cost per hour of podcast audio[/dim]"
        "\n[dim]  Local models run on your machine (requires GPU for best performance)[/dim]"
        "\n[dim]  Cloud models require API keys (see 'podx config')[/dim]\n"
    )


if __name__ == "__main__":
    main()
