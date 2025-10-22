"""Workflow and fidelity preset utilities.

These functions delegate to domain layer factory methods to ensure
single source of truth for preset logic.
"""

from typing import Any, Dict, Union

from ..domain import PipelineConfig
from ..domain.enums import ASRPreset


def apply_fidelity_preset(
    fidelity: str,
    current_preset: Union[str, ASRPreset, None] = None,
    interactive: bool = False,
) -> Dict[str, Any]:
    """Apply fidelity level mapping to pipeline flags.

    This delegates to PipelineConfig.from_fidelity() to ensure single source
    of truth for fidelity mappings.

    Args:
        fidelity: Fidelity level 1-5
            1: Deepcast only (fastest)
            2: Recall preset + preprocess + restore + deepcast
            3: Precision preset + preprocess + restore + deepcast
            4: Balanced preset + preprocess + restore + deepcast (recommended)
            5: Dual QA (precision + recall) + preprocess + restore (best)
        current_preset: Current preset value (if any) - string or ASRPreset enum
        interactive: Whether in interactive mode (affects preset behavior)

    Returns:
        Dictionary with pipeline flags: align, diarize, preprocess, restore, deepcast, dual, preset
        Note: preset values are ASRPreset enums for type safety
    """
    # Delegate to domain factory method
    config = PipelineConfig.from_fidelity(int(fidelity), preset=current_preset)

    # Convert to dict for backward compatibility with orchestrate.py
    flags = {
        "preset": config.preset,
        "align": config.align,
        "diarize": config.diarize,
        "preprocess": config.preprocess,
        "restore": config.restore,
        "deepcast": config.deepcast,
        "dual": config.dual,
    }

    return flags
