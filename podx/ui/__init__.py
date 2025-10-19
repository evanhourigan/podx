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
from .confirmation import Confirmation
from .episode_selector import (
    scan_episode_status,
    select_episode_interactive,
    select_fidelity_interactive,
)
from .formatters import clean_cell, sanitize_filename

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
    "Confirmation",
    "clean_cell",
    "sanitize_filename",
    "scan_episode_status",
    "select_episode_interactive",
    "select_fidelity_interactive",
]
