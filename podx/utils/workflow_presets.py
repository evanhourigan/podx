"""Workflow and fidelity preset utilities."""

from typing import Any, Dict, Union

from ..domain.enums import ASRPreset


def apply_fidelity_preset(
    fidelity: str,
    current_preset: Union[str, ASRPreset, None] = None,
    interactive: bool = False,
) -> Dict[str, Any]:
    """Apply fidelity level mapping to pipeline flags.

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
    flags: Dict[str, Any] = {}

    if fidelity == "1":
        # Deepcast only; keep other flags off
        flags = {
            "align": False,
            "diarize": False,
            "preprocess": False,
            "dual": False,
            "deepcast": True,
            "restore": False,
            "preset": current_preset,
        }
    elif fidelity == "2":
        flags = {
            "preset": ASRPreset.RECALL if interactive else (current_preset or ASRPreset.RECALL),
            "preprocess": True,
            "restore": True,
            "deepcast": True,
            "dual": False,
        }
    elif fidelity == "3":
        flags = {
            "preset": ASRPreset.PRECISION if interactive else (current_preset or ASRPreset.PRECISION),
            "preprocess": True,
            "restore": True,
            "deepcast": True,
            "dual": False,
        }
    elif fidelity == "4":
        flags = {
            "preset": ASRPreset.BALANCED if interactive else (current_preset or ASRPreset.BALANCED),
            "preprocess": True,
            "restore": True,
            "deepcast": True,
            "dual": False,
        }
    elif fidelity == "5":
        flags = {
            "dual": True,
            "preprocess": True,
            "restore": True,
            "deepcast": True,
            "preset": current_preset or ASRPreset.BALANCED,
        }

    return flags


def apply_workflow_preset(workflow: str) -> Dict[str, Any]:
    """Apply workflow preset to pipeline flags.

    Args:
        workflow: Workflow name (quick, analyze, publish)

    Returns:
        Dictionary with pipeline flags
    """
    flags: Dict[str, Any] = {}

    if workflow == "quick":
        flags = {
            "align": False,
            "diarize": False,
            "deepcast": False,
            "extract_markdown": False,
            "notion": False,
        }
    elif workflow == "analyze":
        flags = {
            "align": True,
            "diarize": False,
            "deepcast": True,
            "extract_markdown": True,
        }
    elif workflow == "publish":
        flags = {
            "align": True,
            "diarize": False,
            "deepcast": True,
            "extract_markdown": True,
            "notion": True,
        }

    return flags
