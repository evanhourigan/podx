"""Interactive ASR model selection for transcription.

This module provides ASR model selection functionality using Textual TUI.
The old Rich-based select_asr_model() is deprecated but kept for backward compatibility.

The Textual implementation lives in transcribe_tui.py (ASRModelModal + select_asr_model_tui).
"""

import warnings
from typing import Any, Dict, List, Optional

# Re-export from transcribe_tui for backward compatibility
from .transcribe_tui import ASR_MODELS, select_asr_model_tui

__all__ = [
    "ASR_MODELS",
    "get_most_sophisticated_model",
    "select_asr_model",
    "select_asr_model_tui",
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

    DEPRECATED: This Rich-based function is deprecated. Use select_asr_model_tui() instead.

    Args:
        episode: Episode dictionary with 'transcripts' key containing already-transcribed models
        console: Rich Console instance for display (DEPRECATED - ignored, using Textual TUI)

    Returns:
        Selected model string, or None if user cancelled
    """
    warnings.warn(
        "select_asr_model() with Rich is deprecated. Use select_asr_model_tui() for Textual TUI.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Extract transcribed models and use new Textual TUI
    transcribed_models = list(episode.get("transcripts", {}).keys())
    return select_asr_model_tui(transcribed_models)
