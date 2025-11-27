"""UI components for podx CLI."""

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

# Import from new ui/ package modules
from .asr_selector import ASR_MODELS, get_most_sophisticated_model, select_asr_model
from .analyze_browser import (
    AnalyzeBrowser,
    flatten_episodes_to_rows,
    scan_analyzable_episodes,
)
from .analyze_selector import select_analysis_type
from .confirmation import Confirmation
from .diarize_browser import DiarizeTwoPhase, scan_diarizable_transcripts
from .episode_browser_tui import (
    select_episode_for_processing,
    select_episode_with_config,
    select_episode_with_tui,
)
from .episode_selector import scan_episode_status, select_episode_interactive
from .execution_tui import ExecutionTUI, TUIProgress
from .fetch_browser import EpisodeBrowser
from .formatters import clean_cell, sanitize_filename
from .interactive_browser import InteractiveBrowser
from .live_timer import LiveTimer
from .modals.config_modal import configure_pipeline_interactive
from .transcode_browser import TranscodeBrowser, scan_transcodable_episodes
from .transcribe_browser import TranscribeBrowser, scan_transcribable_episodes
from .transcribe_tui import (
    ASRModelModal,
    TranscriptionProgressApp,
    select_asr_model_tui,
)

# Backward compatibility aliases
DiarizeBrowser = DiarizeTwoPhase
DeepcastBrowser = AnalyzeBrowser
scan_deepcastable_episodes = scan_analyzable_episodes
select_deepcast_type = select_analysis_type

__all__ = [
    # From ui_styles.py
    "CMD_STYLE",
    "FLAG_STYLE",
    "ARG_STYLE",
    "SYMBOL_STYLE",
    "COMMENT_STYLE",
    "HEADING_STYLE",
    "EXAMPLE_HEADING_STYLE",
    "TABLE_BORDER_STYLE",
    "TABLE_HEADER_STYLE",
    "TABLE_TITLE_STYLE",
    "TABLE_NUM_STYLE",
    "TABLE_SHOW_STYLE",
    "TABLE_DATE_STYLE",
    "TABLE_FLAG_VALUE_STYLE",
    "TABLE_TITLE_COL_STYLE",
    "make_console",
    "format_example_line",
    # From new ui/ package
    "ASR_MODELS",
    "ASRModelModal",
    "AnalyzeBrowser",
    "Confirmation",
    "DeepcastBrowser",  # Backwards compatibility alias for AnalyzeBrowser
    "DiarizeBrowser",
    "EpisodeBrowser",
    "ExecutionTUI",
    "InteractiveBrowser",
    "LiveTimer",
    "TUIProgress",
    "TranscodeBrowser",
    "TranscribeBrowser",
    "TranscriptionProgressApp",
    "clean_cell",
    "configure_pipeline_interactive",
    "flatten_episodes_to_rows",
    "get_most_sophisticated_model",
    "sanitize_filename",
    "scan_analyzable_episodes",
    "scan_deepcastable_episodes",  # Backwards compatibility alias
    "scan_diarizable_transcripts",
    "scan_episode_status",
    "scan_transcodable_episodes",
    "scan_transcribable_episodes",
    "select_analysis_type",
    "select_asr_model",
    "select_asr_model_tui",
    "select_deepcast_type",  # Backwards compatibility alias
    "select_episode_for_processing",
    "select_episode_interactive",
    "select_episode_with_config",
    "select_episode_with_tui",
]
