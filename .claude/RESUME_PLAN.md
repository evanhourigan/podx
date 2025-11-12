# Resume Plan: Phase 1 Completion - Large File Refactoring

**Last Updated**: 2025-11-12 03:00:00 UTC
**Current Branch**: `refactor/unified-solid-improvements`
**Status**: Phase 1.1 & 1.2 complete, ready to tackle large files

## 🎯 Immediate Next Steps

Split 3 large files (all > 1,000 lines) to complete Phase 1:

### 1. notion.py (1,385 lines → target: ~520 lines)

**Extract to `podx/cli/notion_services/`:**

- **block_utils.py** (~110 lines, lines 52-152)
  - `rt()` - Rich text helper
  - `_split_blocks_for_notion()` - Block chunking
  - `_find_optimal_split_point()` - Split optimization
  - `_is_optimal_split_point()` - Split validation

- **interactive.py** (~400 lines, lines 154-551)
  - `_detect_shows()` - Show detection
  - `_list_episode_dates()` - Date listing
  - `_list_deepcast_models()` - Model listing
  - `_prompt_numbered_choice()` - Interactive selection
  - `_scan_notion_rows()` - Row scanning
  - `_interactive_table_flow()` - Full interactive flow

- **page_operations.py** (~260 lines, lines 553-811)
  - `_list_children_all()` - List page children
  - `_clear_children()` - Clear page children
  - `upsert_page()` - Create/update Notion pages

**Keep in notion.py** (~520 lines):
- CLI command definition (lines 812-end)
- `notion_client_from_env()` helper

**Import fixes needed:**
- interactive.py needs: `import re, os, json, click` + Rich imports
- page_operations.py needs: `import click`
- Both need `notion_client_from_env` import from parent

### 2. deepcast.py (1,007 lines → target: ~650 lines)

**Extract to `podx/cli/deepcast_services/`:**

- **prompt_builder.py** (~200 lines)
  - `build_episode_header()` (lines 137-159)
  - `build_prompt_variant()` (lines 161-233)
  - `_build_prompt_display()` (lines 300-366)

- **ui_helpers.py** (~100 lines)
  - `select_deepcast_type()` (lines 235-284)
  - `select_ai_model()` (lines 286-298)

**Keep in deepcast.py** (~650 lines):
- `generate_deepcast_filename()` (lines 102-119)
- `read_stdin_or_file()` (lines 121-135)
- `deepcast()` function (lines 368-572)
- `main()` CLI command (lines 574-end)

### 3. api/client.py (1,188 lines → target: 3 files ~400 lines each)

**Split into:**

- **api/config.py** (~30 lines)
  - `ClientConfig` class (lines 40-60)

- **api/sync_client.py** (~650 lines)
  - `PodxClient` class (lines 62-748)

- **api/async_client.py** (~500 lines)
  - `AsyncPodxClient` class (lines 750-end)

**Update api/client.py** to re-export all three:
```python
from .config import ClientConfig
from .sync_client import PodxClient
from .async_client import AsyncPodxClient

__all__ = ["ClientConfig", "PodxClient", "AsyncPodxClient"]
```

### 4. Optional: Move config_panel.py to modals/

**Quick organization:**
```bash
mv podx/ui/config_panel.py podx/ui/modals/config_modals.py
# Update podx/ui/__init__.py import
```

## 📊 Success Criteria

- ✅ All files < 600 lines
- ✅ Tests passing
- ✅ No functionality changes (pure refactoring)
- ✅ Clean commits with detailed messages

## 🚀 How to Resume

```
Continue Phase 1: Split large files (notion.py, deepcast.py, api/client.py)

Current state:
- Branch: refactor/unified-solid-improvements
- Phase 1.1 ✅ (orchestrate.py: 2,533 → 1,256 lines)
- Phase 1.2 ✅ (episode_browser_tui.py: 1,828 → 146 lines)
- Last commit: 6c91f72 "docs: update CONTEXT.md with Phase 1.1 completion"

Next: Split 3 large files to complete Phase 1
1. notion.py (1,385 lines) → notion_services/ modules
2. deepcast.py (1,007 lines) → deepcast_services/ modules
3. api/client.py (1,188 lines) → 3 separate files

See RESUME_PLAN.md for detailed extraction plan.
Let's start with notion.py!
```

## ⚠️ Known Issues

- **Import dependencies**: Extracted modules need proper imports (re, os, json, click, Rich)
- **Circular imports**: Use relative imports and parent function imports carefully
- **Testing**: Run `pytest tests/ -x --tb=short -q` after each extraction

## 📈 Progress Tracking

**Phase 1 Status**: 2/4 tasks complete (50%)
- ✅ orchestrate.py decomposition
- ✅ episode_browser_tui.py split
- ⏳ Large file refactoring (notion, deepcast, api/client)
- ⏳ Optional config_panel organization

**Context**: 135K / 200K tokens used (68%) before compaction
