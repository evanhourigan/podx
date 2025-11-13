# Phase 3: UI Framework Consolidation - Textual Migration Plan

## Overview

Phase 3 consolidates PodX's UI layer by migrating all Rich-based CLI helpers to proper Textual TUIs. This provides a consistent, interactive user experience across all commands.

## Current State Analysis

### UI Files Breakdown (26 total)

**Already using Textual (9 files)** - Modern TUIs:
- `episode_browser.py` - Main episode browser with DataTable
- `transcribe_tui.py` - Transcription UI
- `execution_tui.py` - Pipeline execution UI
- `preprocess_browser.py` - Preprocessing browser
- `simple_processing.py` - Simple processing app
- `model_level_processing.py` - Model-level processing
- `standalone_fetch.py` - Standalone fetch app
- `fetch_modal.py` - Fetch modal dialog
- `config_modal.py` - Configuration modal

**Using ONLY Rich (8 files)** - CLI helpers needing migration:
1. `asr_selector.py` (131 lines) - Simple selector with `input()`
2. `transcode_browser.py` (196 lines) - InteractiveBrowser subclass
3. `fetch_browser.py` (253 lines) - InteractiveBrowser subclass
4. `transcribe_browser.py` (259 lines) - InteractiveBrowser subclass
5. `two_phase_browser.py` (328 lines) - InteractiveBrowser subclass
6. `episode_selector.py` (345 lines) - InteractiveBrowser subclass
7. `diarize_browser.py` (392 lines) - InteractiveBrowser subclass
8. `deepcast_browser.py` (477 lines) - InteractiveBrowser subclass

**Shared/Utility (9 files)** - Styling and helpers:
- `ui_styles.py`, `live_timer.py`, `progress_bar.py`, etc.

## Key Discovery: InteractiveBrowser Pattern

The `InteractiveBrowser` base class (`podx/ui/interactive_browser.py`, 167 lines):
- **NOT a true TUI** - uses Rich for display but `input()` for interaction
- Provides pagination pattern (N/P/Q/number navigation)
- Abstract `display_page()` method for subclasses to implement
- Standard selection confirmation pattern
- **7 of 8 Rich-only files extend this base class**

### InteractiveBrowser Usage Pattern

```python
class MyBrowser(InteractiveBrowser):
    def display_page(self) -> None:
        # Create Rich Table
        # Print with Rich Console
        # Show navigation options
        pass

    def browse(self) -> Optional[Dict[str, Any]]:
        while True:
            self.display_page()
            user_input = input("Your choice: ")
            # Parse N/P/Q/number
```

This pattern will be replaced with proper Textual DataTable + event handlers.

## Migration Strategy

### Why This Migration is Simpler Than Expected

1. **Existing Textual pattern exists**: `episode_browser.py` provides the blueprint:
   - `textual.widgets.DataTable` for listing
   - CSS styling for layout and colors
   - Binding system for keyboard shortcuts (f/enter/esc)
   - Modal dialogs for complex interactions

2. **Common pattern to migrate**: Most files extend `InteractiveBrowser`:
   - Replace Rich Table → Textual DataTable
   - Replace `input()` loop → Textual event handlers
   - Extract pagination into shared Textual component
   - Reuse existing CSS patterns

3. **One outlier**: `asr_selector.py` is standalone (not InteractiveBrowser-based):
   - Simplest to migrate (just a selector function)
   - Can become a reusable modal widget

## Migration Plan

### Phase 3.1: Audit Current UI State ✅ COMPLETE
- [x] Identify all UI files and categorize by framework
- [x] Analyze InteractiveBrowser architecture
- [x] Document existing Textual patterns
- [x] Create migration plan

### Phase 3.2: Migrate Rich-Only Files to Textual

#### Phase 3.2.1: Migrate `asr_selector.py` (Simplest)
**Complexity**: Low (131 lines, standalone function)
**Approach**:
- Create `ASRSelectorModal` Textual widget
- Replace Rich Table + `input()` → Textual DataTable + bindings
- Reuse existing model list logic
- Test with transcribe command's interactive mode

**Files to modify**:
- `podx/ui/asr_selector.py` - Convert to Textual modal
- Test: `podx transcribe --interactive` (user testing required)

#### Phase 3.2.2: Create Shared `SelectionBrowser` Widget
**Purpose**: Replace InteractiveBrowser base class with proper Textual component
**Features**:
- Textual DataTable with pagination support
- Standard keybindings (arrows/enter/esc)
- Customizable columns via composition
- Reusable across all browser migrations

**Implementation**:
- Create `podx/ui/widgets/selection_browser.py`
- Abstract column configuration
- Handle selection + cancellation events
- Include built-in pagination controls

#### Phase 3.2.3: Migrate InteractiveBrowser Subclasses
Migrate in order of increasing complexity:

1. **`transcode_browser.py` (196 lines)**
   - Simplest InteractiveBrowser subclass
   - Single phase selection (episodes)
   - Test: `podx transcode --interactive`

2. **`fetch_browser.py` (253 lines)**
   - Single phase selection (RSS episodes)
   - Includes RSS feed loading
   - Test: `podx fetch --interactive --show "Some Podcast"`

3. **`transcribe_browser.py` (259 lines)**
   - Single phase selection (audio files)
   - File system scanning
   - Test: `podx transcribe --interactive`

4. **`two_phase_browser.py` (328 lines)**
   - Two-level selection (episode → transcript)
   - More complex navigation
   - Used by diarize browser
   - Test: Helper function, tested via diarize

5. **`episode_selector.py` (345 lines)**
   - Episode selection with metadata display
   - File system scanning + JSON parsing
   - Test: Used by multiple commands

6. **`diarize_browser.py` (392 lines)**
   - Uses `two_phase_browser.py`
   - Two-phase: episode → base transcript
   - Test: `podx diarize --interactive`

7. **`deepcast_browser.py` (477 lines)** (Most complex)
   - Uses `two_phase_browser.py`
   - Two-phase: episode → diarized transcript
   - Additional validation logic
   - Test: `podx deepcast --interactive`

### Phase 3.3: Extract Shared Textual Components

Create reusable widgets in `podx/ui/widgets/`:
- `selection_browser.py` - Generic selection browser (Phase 3.2.2)
- `episode_table.py` - Episode listing table
- `transcript_table.py` - Transcript listing table
- `detail_panel.py` - Detail display panel (reuse from episode_browser.py)

### Phase 3.4: Create User Test Scenarios

**CRITICAL**: NO TUI TESTING IN CLAUDE CODE SESSIONS (corrupts terminal)

For each migrated UI, create test scenario document:
1. Command to launch
2. Expected initial display
3. Navigation test steps (arrows, page up/down)
4. Selection test (enter)
5. Cancellation test (esc/q)
6. Expected output format verification

User must manually test each scenario in separate terminal.

### Phase 3.5: Update Documentation

- Update `README.md` with new interactive mode examples
- Update CLI help text if needed
- Document Textual widgets in `docs/UI_COMPONENTS.md`
- Update `CHANGELOG.md` with Phase 3 completion

## Technical Details

### Textual Pattern (from episode_browser.py)

```python
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header
from textual.binding import Binding

class MyBrowserTUI(App[Optional[Dict[str, Any]]]):
    TITLE = "My Browser"

    CSS = """
    DataTable {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("enter", "select", "Select", show=True),
        Binding("escape", "quit_app", "Cancel", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Col1", "Col2")
        for item in self.items:
            table.add_row(item["field1"], item["field2"])

    def action_select(self) -> None:
        table = self.query_one(DataTable)
        row_key = table.cursor_row
        selected = self.items[row_key]
        self.exit(selected)

    def action_quit_app(self) -> None:
        self.exit(None)
```

### Migration Checklist (Per File)

- [ ] Replace Rich imports with Textual imports
- [ ] Convert function/class to Textual App
- [ ] Replace Rich Table → Textual DataTable
- [ ] Replace `input()` loop → Textual event handlers
- [ ] Add CSS styling (can reuse from episode_browser.py)
- [ ] Add keybindings (enter/esc minimum)
- [ ] Handle selection event → exit with result
- [ ] Handle cancellation event → exit with None
- [ ] Update calling code to use `app.run()` instead of `browse()`
- [ ] Create user test scenario document
- [ ] User tests in separate terminal (NOT in Claude Code)
- [ ] Verify all tests pass

## Success Criteria

Phase 3 is complete when:
- [ ] All 8 Rich-only files migrated to Textual
- [ ] All tests passing (332 tests)
- [ ] All interactive modes tested by user
- [ ] Documentation updated
- [ ] `InteractiveBrowser` base class deprecated/removed
- [ ] Shared Textual components extracted and reusable

## Timeline Estimate

- Phase 3.1: ✅ COMPLETE
- Phase 3.2.1: 1 file (asr_selector) - ~1 hour
- Phase 3.2.2: Shared widget - ~1 hour
- Phase 3.2.3: 7 files - ~5 hours (iterative, with testing breaks)
- Phase 3.3: Extract shared components - ~1 hour
- Phase 3.4: Test scenarios - ~1 hour
- Phase 3.5: Documentation - ~30 mins

**Total: ~10 hours of development + user testing time**

## Risk Mitigation

1. **TUI Testing**: User must test in separate terminal (NOT Claude Code)
2. **Backward Compatibility**: Keep old functions as deprecated wrappers initially
3. **Incremental Testing**: Test each file migration before moving to next
4. **Rollback Plan**: Git branches for each phase, easy to revert

## References

- Textual Docs: https://textual.textualize.io/
- Existing Textual Example: `podx/ui/apps/episode_browser.py`
- InteractiveBrowser Base: `podx/ui/interactive_browser.py`
