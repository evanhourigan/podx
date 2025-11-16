"""Notion service modules for CLI operations."""

from .block_utils import _split_blocks_for_notion, rt
from .interactive import (
    _detect_shows,
    _interactive_table_flow,
    _list_deepcast_models,
    _list_episode_dates,
    _prompt_numbered_choice,
    _scan_notion_rows,
)
from .page_operations import _clear_children, _list_children_all, upsert_page

__all__ = [
    # Block utils
    "rt",
    "_split_blocks_for_notion",
    # Interactive
    "_detect_shows",
    "_list_episode_dates",
    "_list_deepcast_models",
    "_prompt_numbered_choice",
    "_scan_notion_rows",
    "_interactive_table_flow",
    # Page operations
    "_list_children_all",
    "_clear_children",
    "upsert_page",
]
