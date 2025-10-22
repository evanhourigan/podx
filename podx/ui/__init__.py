"""UI components for podx CLI."""

# Import from ui_styles.py module (for backward compatibility with old imports)
from ..ui_styles import (
    CMD_STYLE,
    FLAG_STYLE,
    ARG_STYLE,
    SYMBOL_STYLE,
    COMMENT_STYLE,
    HEADING_STYLE,
    EXAMPLE_HEADING_STYLE,
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_TITLE_STYLE,
    TABLE_NUM_STYLE,
    TABLE_SHOW_STYLE,
    TABLE_DATE_STYLE,
    TABLE_FLAG_VALUE_STYLE,
    TABLE_TITLE_COL_STYLE,
    make_console,
    format_example_line,
)

# Import from new ui/ package modules
from .asr_selector import ASR_MODELS, get_most_sophisticated_model, select_asr_model
from .config_panel import configure_pipeline_interactive
from .confirmation import Confirmation
from .deepcast_browser import (
    DeepcastBrowser,
    flatten_episodes_to_rows,
    scan_deepcastable_episodes,
)
from .deepcast_selector import select_deepcast_type
from .diarize_browser import DiarizeTwoPhase, scan_diarizable_transcripts
from .episode_browser_tui import select_episode_for_processing, select_episode_with_tui
from .episode_selector import scan_episode_status, select_episode_interactive
from .fetch_browser import EpisodeBrowser
from .formatters import clean_cell, sanitize_filename
from .interactive_browser import InteractiveBrowser
from .live_timer import LiveTimer
from .transcode_browser import TranscodeBrowser, scan_transcodable_episodes
from .transcribe_browser import TranscribeBrowser, scan_transcribable_episodes

# Backward compatibility alias
DiarizeBrowser = DiarizeTwoPhase

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
    "Confirmation",
    "DeepcastBrowser",
    "DiarizeBrowser",
    "EpisodeBrowser",
    "InteractiveBrowser",
    "LiveTimer",
    "TranscodeBrowser",
    "TranscribeBrowser",
    "clean_cell",
    "configure_pipeline_interactive",
    "flatten_episodes_to_rows",
    "get_most_sophisticated_model",
    "sanitize_filename",
    "scan_deepcastable_episodes",
    "scan_diarizable_transcripts",
    "scan_episode_status",
    "scan_transcodable_episodes",
    "scan_transcribable_episodes",
    "select_asr_model",
    "select_deepcast_type",
    "select_episode_for_processing",
    "select_episode_interactive",
    "select_episode_with_tui",
]
