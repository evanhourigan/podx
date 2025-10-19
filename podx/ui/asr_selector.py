"""Interactive ASR model selection for transcription."""

from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# Available ASR models in order of sophistication (local/faster-whisper canonical names)
# Note: local models also support ".en" variants like "small.en", "medium.en".
ASR_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]


def get_most_sophisticated_model(models: List[str]) -> str:
    """Return the most sophisticated model from a list."""
    for model in reversed(ASR_MODELS):
        if model in models:
            return model
    return models[0] if models else "base"


def select_asr_model(
    episode: Dict[str, Any], console: Optional[Console]
) -> Optional[str]:
    """Prompt user to select ASR model with helpful context.

    Args:
        episode: Episode dictionary with 'transcripts' key containing already-transcribed models
        console: Rich Console instance for display (or None to return None)

    Returns:
        Selected model string, or None if user cancelled
    """
    if not console:
        return None

    transcribed_models = list(episode["transcripts"].keys())

    # Determine recommended local model (most sophisticated not yet transcribed)
    recommended = None
    for model in reversed(ASR_MODELS):
        if model not in transcribed_models:
            recommended = model
            break

    if not recommended:
        recommended = get_most_sophisticated_model(ASR_MODELS)

    console.print("\n[bold cyan]Select ASR model:[/bold cyan]\n")

    # Create table showing models
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Number", style="cyan", justify="right", width=3)
    table.add_column("Model", style="white", width=12)
    table.add_column("Status", style="yellow", width=20)

    # Display local models plus common variants and provider examples
    display_models: List[str] = []
    display_models.extend(ASR_MODELS)
    for extra in ["small.en", "medium.en", "openai:large-v3-turbo", "hf:distil-large-v3"]:
        if extra not in display_models:
            display_models.append(extra)

    for idx, model in enumerate(display_models, 1):
        if model in transcribed_models:
            status = "✓ Already transcribed"
        elif model == recommended:
            status = "← Recommended"
        else:
            status = ""
        table.add_row(str(idx), model, status)

    console.print(table)

    if transcribed_models:
        console.print(
            f"\n[dim]Already transcribed with: {', '.join(transcribed_models)}[/dim]"
        )

    # Get user selection
    while True:
        try:
            choice = input(f"\n👉 Select model (1-{len(display_models)}) or Q to cancel: ").strip().upper()

            if choice in ["Q", "QUIT", "CANCEL"]:
                return None

            model_idx = int(choice)
            if 1 <= model_idx <= len(display_models):
                selected_model = display_models[model_idx - 1]

                # Check if same model already exists - ask for confirmation
                if selected_model in transcribed_models:
                    console.print(
                        f"\n[yellow]⚠ Episode already transcribed with model '{selected_model}'[/yellow]"
                    )
                    confirm = (
                        input("Re-transcribe with same model? (yes/no): ")
                        .strip()
                        .lower()
                    )
                    if confirm not in ["yes", "y"]:
                        console.print(
                            "[dim]Selection cancelled. Choose a different model.[/dim]"
                        )
                        continue

                return selected_model
            else:
                console.print(
                        f"[red]❌ Invalid choice. Please select 1-{len(display_models)}[/red]"
                )

        except ValueError:
            console.print("[red]❌ Invalid input. Please enter a number.[/red]")
        except (KeyboardInterrupt, EOFError):
            return None
