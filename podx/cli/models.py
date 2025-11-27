#!/usr/bin/env python3
"""List AI models with pricing.

Simple display of available models for transcription and analysis.
"""

from __future__ import annotations

import click


@click.command()
def main():
    """List available AI models with pricing.

    Shows models for transcription (ASR) and analysis (LLM) with
    estimated cost per hour of podcast audio.

    \b
    ASR Models (Transcription):
      local:large-v3      Best quality, runs locally (free)
      local:large-v2      Previous best, runs locally (free)
      local:medium        Good balance of speed/quality (free)
      local:base          Fast, lower accuracy (free)
      local:tiny          Fastest, lowest accuracy (free)
      openai:whisper-1    Cloud transcription ($0.006/min)
      hf:distil-large-v3  Distilled model, fast (free)

    \b
    LLM Models (Analysis):
      Run 'podx models' to see current pricing.
    """
    from podx.models import list_models

    click.echo()
    click.echo("ASR Models (Transcription)")
    click.echo("-" * 60)
    click.echo(f"{'Model':<25}{'$/hr':<12}Description")
    click.echo("-" * 60)

    asr_models = [
        ("local:large-v3", "Free", "Best quality (default)"),
        ("local:large-v2", "Free", "Previous best"),
        ("local:medium", "Free", "Good balance of speed/quality"),
        ("local:base", "Free", "Fast, lower accuracy"),
        ("local:tiny", "Free", "Fastest, lowest accuracy"),
        ("openai:whisper-1", "$0.36", "Cloud transcription"),
        ("hf:distil-large-v3", "Free", "Distilled, faster than large-v3"),
    ]

    for model, cost, desc in asr_models:
        click.echo(f"{model:<25}{cost:<12}{desc}")

    click.echo()
    click.echo("LLM Models (Analysis)")
    click.echo("-" * 60)
    click.echo(f"{'Model':<25}{'$/hr*':<12}Description")
    click.echo("-" * 60)

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

            cost_str = f"${hourly_cost:.2f}"
            model_id = f"{model.provider}:{model.id}"
            desc = model.description or ""
            click.echo(f"{model_id:<25}{cost_str:<12}{desc}")
    except Exception:
        # Fallback if catalog fails
        click.echo(f"{'openai:gpt-4o':<25}{'$0.08':<12}Best quality (default)")
        click.echo(f"{'openai:gpt-4o-mini':<25}{'$0.01':<12}Good quality, lower cost")
        click.echo(f"{'anthropic:claude-sonnet-4-5':<25}{'$0.10':<12}Great alternative")

    click.echo()
    click.echo("* Estimated cost per hour of podcast audio")
    click.echo("  Local models run on your machine (requires GPU for best performance)")
    click.echo("  Cloud models require API keys (see 'podx config')")
    click.echo()


if __name__ == "__main__":
    main()
