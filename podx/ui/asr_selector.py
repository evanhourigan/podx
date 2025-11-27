"""Interactive ASR model selection for transcription.

Simple interactive model selector that works with stdin/stdout.
"""

from typing import Any, Dict, List, Optional

# Available ASR models in order of sophistication
ASR_MODELS = [
    "tiny",
    "base",
    "small",
    "medium",
    "large-v2",
    "large-v3",
    "distil-large-v3",
]

__all__ = [
    "ASR_MODELS",
    "get_most_sophisticated_model",
    "select_asr_model",
]


def get_most_sophisticated_model(models: List[str]) -> str:
    """Return the most sophisticated model from a list."""
    for model in reversed(ASR_MODELS):
        if model in models:
            return model
    return models[0] if models else "base"


def select_asr_model(
    episode: Dict[str, Any], console: Optional[Any] = None
) -> Optional[str]:
    """Prompt user to select ASR model with helpful context.

    Args:
        episode: Episode dictionary with 'transcripts' key containing already-transcribed models
        console: Rich Console instance for display (optional)

    Returns:
        Selected model string, or None if user cancelled
    """
    transcribed_models = list(episode.get("transcripts", {}).keys())

    if console:
        console.print("\n[bold cyan]Select ASR model:[/bold cyan]")
    else:
        print("\nSelect ASR model:")

    for i, model in enumerate(ASR_MODELS, start=1):
        status = " [done]" if model in transcribed_models else ""
        if console:
            console.print(f"  {i:2}  {model}{status}")
        else:
            print(f"  {i:2}  {model}{status}")

    default = "large-v3"
    prompt = f"\n👉 Choose 1-{len(ASR_MODELS)} (Enter for {default}, Q=cancel): "
    choice = input(prompt).strip()

    if choice.upper() in {"Q", "QUIT", "EXIT"}:
        return None

    if not choice:
        return default

    try:
        idx = int(choice)
        if 1 <= idx <= len(ASR_MODELS):
            return ASR_MODELS[idx - 1]
    except ValueError:
        pass

    return default
