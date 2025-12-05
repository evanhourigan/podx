"""UI components for podx CLI.

This module provides simple interactive prompts and console utilities.
Complex Textual TUI components have been removed in v4.0.0.
"""

# Import from ui_styles.py module (for backward compatibility with old imports)
from ..ui_styles import (
    ARG_STYLE,
    CMD_STYLE,
    COMMENT_STYLE,
    EXAMPLE_HEADING_STYLE,
    FLAG_STYLE,
    HEADING_STYLE,
    SYMBOL_STYLE,
    TABLE_BORDER_STYLE,
    TABLE_DATE_STYLE,
    TABLE_FLAG_VALUE_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    TABLE_SHOW_STYLE,
    TABLE_TITLE_COL_STYLE,
    TABLE_TITLE_STYLE,
    format_example_line,
    make_console,
)

# Simple interactive selectors
from .analyze_selector import select_analysis_type, select_deepcast_type
from .asr_selector import ASR_MODELS, get_most_sophisticated_model, select_asr_model
from .confirmation import Confirmation
from .download_progress import DownloadProgress
from .episode_selector import (
    RequiredArtifact,
    scan_episode_status,
    select_episode_interactive,
)
from .formatters import clean_cell, sanitize_filename
from .live_timer import LiveTimer
from .prompts import (
    get_asr_models_help,
    get_export_formats_help,
    get_languages_help,
    get_llm_models_help,
    get_templates_help,
    prompt_with_help,
    show_confirmation,
    validate_asr_model,
    validate_export_format,
    validate_language,
    validate_llm_model,
    validate_template,
)
from .speaker_identify import (
    apply_speaker_names,
    has_generic_speaker_ids,
    identify_speakers_interactive,
)

__all__ = [
    # From ui_styles.py
    "ARG_STYLE",
    "CMD_STYLE",
    "COMMENT_STYLE",
    "EXAMPLE_HEADING_STYLE",
    "FLAG_STYLE",
    "HEADING_STYLE",
    "SYMBOL_STYLE",
    "TABLE_BORDER_STYLE",
    "TABLE_DATE_STYLE",
    "TABLE_FLAG_VALUE_STYLE",
    "TABLE_HEADER_STYLE",
    "TABLE_NUM_STYLE",
    "TABLE_SHOW_STYLE",
    "TABLE_TITLE_COL_STYLE",
    "TABLE_TITLE_STYLE",
    "format_example_line",
    "make_console",
    # Interactive selectors
    "ASR_MODELS",
    "Confirmation",
    "DownloadProgress",
    "LiveTimer",
    "clean_cell",
    "get_most_sophisticated_model",
    "sanitize_filename",
    "RequiredArtifact",
    "scan_episode_status",
    "select_analysis_type",
    "select_asr_model",
    "select_deepcast_type",  # Backwards compatibility alias
    "select_episode_interactive",
    # Prompt utilities
    "get_asr_models_help",
    "get_export_formats_help",
    "get_languages_help",
    "get_llm_models_help",
    "get_templates_help",
    "prompt_with_help",
    "show_confirmation",
    "validate_asr_model",
    "validate_export_format",
    "validate_language",
    "validate_llm_model",
    "validate_template",
    # Speaker identification
    "apply_speaker_names",
    "has_generic_speaker_ids",
    "identify_speakers_interactive",
]
