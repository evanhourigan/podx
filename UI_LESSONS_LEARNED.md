# UI Lessons Learned (Pre-Refactor Documentation)

## Date
2025-10-27

## Purpose
Document UI/UX decisions and lessons from the partial TUI implementation (v1.9.0)
before refactoring, so we don't repeat work when building PodX Studio.

---

## Color Scheme & Styling

### What Worked
```python
# Episode Browser Colors
- Header background: $boost (highlighted)
- Selected row: $secondary 30% (subtle highlight)
- Borders: $primary (consistent framing)
- Episode title: white
- Show name: magenta
- Date: green
- Status indicators: cyan, yellow, blue
- Detail panel background: $panel
- Field labels: bold cyan
```

### Consistency Rules
- **All browsers should use same color scheme**
- **Border style should match** (solid $primary)
- **Detail panels should have fixed height** (8 lines) at bottom
- **Table should scroll**, detail panel should not

---

## Layout Principles

### Fixed Detail Panel at Bottom
**What we learned**: Users need context always visible

```css
#table-container {
    height: 1fr;           /* Takes remaining space */
    border: solid $primary;
}

#detail-panel {
    height: 8;             /* Fixed height, always visible */
    border-top: solid $primary;
    padding: 1 2;
    background: $panel;
}
```

**DON'T**: Use percentages (80%, 20%) - causes overflow issues
**DO**: Use `1fr` for flexible, fixed numbers for rigid

---

## Episode Detail Panel Fields

### Format Decisions

**ASR Models**: Show clean model names only
```
✗ BAD:  aligned-large-v3, diarized-large-v3, transcript-large-v3
✓ GOOD: large-v3, medium
```

**Processing Status**: Use "Label: value or (none)" pattern
```
Diarizations: large-v3, medium  OR  (none)
Pre-Processed: large-v3  OR  (none)
Deepcasts: (large-v3, gpt-4, general)  OR  (none)
```

**Show duration**: Always include
```
Duration: 1:23:45
```

**Last Run**: Only show if episode has been processed
- If never processed: Don't show field at all
- If processed: Show timestamp

**Directory**: Always show in dim style
```
Directory: [dim]/path/to/episode[/dim]
```

---

## Navigation & Keyboard Shortcuts

### What Users Expect

**Episode Browser**:
- `Enter`: Select episode and continue
- `Esc`: Cancel and exit
- `↑/↓`: Navigate rows
- `f`: Fetch new episode (when in podx run)

**Transcript Browser**:
- `Enter`: Select transcript and continue
- `Esc`: **Go back to episode browser** (NOT exit to terminal)
- `↑/↓`: Navigate rows

**Modals (ASR selection, config)**:
- `Enter`: Confirm selection
- `Esc`: Cancel and return to parent screen (NOT exit)

### Key Insight
**Modal navigation should feel like drilling down and backing up, not entering/exiting the app**

---

## Transcript Browser Simplification

### What Should Be in Table

**Minimal columns** (show episode info once in detail panel):
- ASR Model: "large-v3"
- Stage: "Base", "Diarized", "Preprocessed"

**NOT in table**:
- Show name (redundant - same episode)
- Date (redundant - same episode)
- Title (redundant - same episode)

### Detail Panel for Transcript Browser

Show episode context:
```
Show: Lenny's Podcast: Product | Career | Growth
Date: 2025-10-26
Title: How Block is becoming the most AI-native enterprise
ASR Model: large-v3
Stage: Diarized
Directory: /path/to/episode
```

---

## Progress Display Patterns

### What Worked
- **Live timer**: Show elapsed time during operations
- **Separate timers for each step**: Better UX than combined timer
- **Completion messages**: ✓ Step completed in M:SS
- **Clean terminal output**: Suppress logs during interactive mode

### Example Pattern
```
Aligning transcript (1:23)
✓ Alignment completed in 1:23

Diarizing (identifying speakers) (0:45)
✓ Diarization completed in 0:45

✅ Diarization complete
   Model: large-v3
   Output: /path/to/transcript-diarized-large-v3.json
```

---

## Modal Design

### ASR Model Selection Modal

**Layout**:
```
┌─ Select ASR Model ─────────────────────┐
│                                        │
│  Model              Status             │
│  tiny               ← Recommended      │
│  base                                  │
│  small                                 │
│  medium                                │
│  large              ✓ Already done     │
│  large-v2                              │
│  large-v3                              │
│  small.en                              │
│  medium.en                             │
│  openai:large-v3-turbo                 │
│  hf:distil-large-v3                    │
│                                        │
│  Use ↑↓ • Enter confirm • Esc cancel   │
└────────────────────────────────────────┘
```

**Recommendations**:
- Show "← Recommended" for next logical step
- Show "✓ Already done" for completed
- Auto-select recommended model on open
- Column widths: Model=24, Status=20

---

## Configuration Modal Design

### What Worked

**Toggle-based config** (not checkboxes):
```
m - Merge adjacent segments: [ON]
n - Normalize text: [ON]
r - Semantic restore: [ON]

Press keys to toggle • Enter to continue • Esc to cancel
```

**Why**: More interactive, clearer feedback than static checkboxes

---

## Logging & Output Management

### Critical Pattern

```python
# Before TUI
if interactive:
    from .logging import suppress_logging
    suppress_logging()

try:
    # Run TUI operations
    ...
finally:
    # After TUI
    if interactive:
        from .logging import restore_logging
        restore_logging()
```

**Why**: Prevents `[INFO]` log spam from corrupting TUI display

---

## What Didn't Work

### 1. `--interactive` Flags Everywhere
**Problem**: Inconsistent, fragmented experience
**Solution**: Unified studio with consistent navigation

### 2. Mixed Concerns in Command Files
**Problem**: CLI parsing, business logic, and UI all together
**Solution**: Separate core/, cli/, studio/

### 3. Percentage-Based Heights
**Problem**: Detail panels overflow or get clipped
**Solution**: Use `1fr` for flexible, fixed numbers for rigid

### 4. Separate Apps for Modals
**Problem**: Esc exits to terminal instead of parent screen
**Solution**: Use `push_screen_wait()` within same app

### 5. Complex Table Columns
**Problem**: Too much redundant info in transcript browser
**Solution**: Minimal table, rich detail panel

---

## Studio Design Principles (For Future)

### Dashboard Concept
```
┌─ PodX Studio ────────────────────────────┐
│ [Home] [Transcribe] [Diarize] [Pipeline] │
├──────────────────────────────────────────┤
│  Recent Episodes    Quick Actions         │
│  Processing Queue   System Status         │
└──────────────────────────────────────────┘
```

### Tab Navigation (F-keys)
- F1/Ctrl+1: Home
- F2/Ctrl+2: Transcribe
- F3/Ctrl+3: Diarize
- F4/Ctrl+4: Pipeline
- F5/Ctrl+5: Settings

### State Management
- Should persist recent episodes
- Should remember last workflow used
- Should save preferences (default model, etc.)

### Consistent Patterns
- All workflows follow: Select → Configure → Execute → Review
- All use same color scheme
- All have progress display
- All support Esc to back out

---

## Reusable Widget Patterns

### Episode List Widget
- Scrollable table with fixed detail panel
- Color scheme: magenta/green/white/cyan
- Cursor navigation (↑↓)
- Enter to select, Esc to cancel

### Model Selector Widget
- Modal overlay with recommendation
- Shows "already done" status
- Auto-focuses recommended option

### Progress Display Widget
- Live timer with elapsed time
- Step-by-step progress indicators
- Completion summary

### Config Panel Widget
- Toggle-based options
- Clear visual feedback
- Keyboard shortcuts (not just Enter/Esc)

---

## Testing Insights

### What to Test
1. **Layout at different terminal sizes**: Ensure detail panel always visible
2. **Long filenames**: Ensure truncation doesn't break display
3. **Empty states**: (none) displays properly
4. **Modal stacking**: Esc returns to parent, not terminal
5. **Logging interference**: No [INFO] spam during TUI

### Edge Cases Found
- Episodes with no processing: Don't show "Last Run"
- Model names with prefixes: Strip "aligned-", "diarized-", etc.
- Very long deepcast info: Limit to first 3, show "+N more"
- Table with 1 item: No scrollbar needed but layout shouldn't break

---

## Architecture Lessons

### What We Learned

**DON'T**:
- Mix UI code with business logic
- Use `--interactive` flags in command implementations
- Import UI modules from core logic
- Duplicate progress tracking logic across commands

**DO**:
- Separate core logic from presentation
- Use callback-based progress reporting
- Build unified UI entry point
- Share widgets and patterns

### The Pattern That Works

```python
# core/transcribe.py
class TranscriptionEngine:
    def transcribe(self, audio, model, progress_callback=None):
        # Pure logic
        if progress_callback:
            progress_callback(TranscriptionProgress(...))
        return Transcript(...)

# studio/screens/transcribe.py
class TranscribeScreen:
    def run(self):
        engine = TranscriptionEngine()
        result = await run_in_worker(
            engine.transcribe,
            audio=...,
            progress_callback=self.update_progress
        )

# cli/transcribe.py
def main(audio, model):
    engine = TranscriptionEngine()
    result = engine.transcribe(audio, model)  # No progress callback
    print(result.to_json())
```

---

## Summary: What to Preserve

### ✅ Keep These Concepts
- Color scheme and styling decisions
- Fixed detail panel layout pattern
- Modal navigation flow (drill down/back up)
- Progress display patterns
- Clean model name extraction
- Field labeling (Label: value or (none))

### ❌ Throw Away These Implementations
- Current `--interactive` flags
- Mixed concern command files
- Separate app modal pattern
- Percentage-based heights
- Complex table columns with redundant info

---

## Next Steps for Studio

When implementing PodX Studio, start with:

1. **Foundation**
   - Theme file with color scheme
   - Base screen class with common patterns
   - Reusable widgets (episode list, progress, etc.)

2. **Home Screen**
   - Recent episodes
   - Quick actions
   - System status

3. **Individual Workflows**
   - Transcribe (proof of concept)
   - Then replicate pattern to others

4. **Polish**
   - Settings/preferences
   - Help system
   - Keyboard shortcuts guide

---

*This document captures UI/UX lessons from v1.9.0 before architecture refactor.*
*Reference when building PodX Studio to avoid repeating work.*
