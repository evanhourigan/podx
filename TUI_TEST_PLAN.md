# PodX TUI Test Plan

## Overview
This test plan covers all interactive TUI commands to verify:
- Clean terminal output (no Rich panels/headers before/after TUI)
- Proper navigation (Esc to go back, Enter to continue)
- Cancellation messages
- Completion messages with detailed information

## ⚠️ Deferred Features (Not Yet Implemented)
The following features are **NOT** currently implemented but have infrastructure ready:
- **Test 7**: Selection preservation (requires architectural change)
- **Test 8**: ExecutionTUI progress tracking (requires refactoring)

These are clearly marked in their respective test sections below.

---

## Test 1: `podx run` - Main Pipeline with TUI

### Test 1.1: Full Pipeline Flow with Episode Selection
```bash
podx run
```

**Expected Behavior:**
1. ✅ TUI launches immediately (no Rich panels/headers in terminal)
2. ✅ Episode browser shows with list of episodes
3. ✅ Footer shows: `Enter Continue  Esc Cancel`
4. ✅ Select an episode and press Enter
5. ✅ Config modal appears (titled "Pipeline Settings")
6. ✅ Modal text: "Select the settings for the pipeline"
7. ✅ Footer shows: `Enter Continue  Esc Cancel`
8. ✅ Configure options and press Enter
9. ✅ TUI exits cleanly back to terminal
10. ✅ Terminal shows clean progress output (no Rich panels)
11. ✅ Progress messages like: `✅ Audio transcoded to wav16 (0:01)`
12. ✅ When complete, shows detailed completion message:
    ```
    ✅ Pipeline completed in X.Xs
       Show: {show} • Title: {title} • Date: {date}
       Steps: fetch → transcode → transcribe → ...
       📄 Transcript: {path}
       🤖 Analysis: {path}
    ```

**Note:** ExecutionTUI (live progress in TUI) is NOT YET IMPLEMENTED. This is a deferred enhancement requiring significant refactoring.
**Note:** "Go Back" from config to episode browser is NOT possible with current architecture (separate apps). Esc cancels the entire flow.

### Test 1.2: Cancel at Episode Selection
```bash
podx run
```

**Expected Behavior:**
1. TUI launches
2. Press Esc at episode selection
3. TUI exits and terminal shows:
   ```
   ❌ Episode selection cancelled
   ```

### Test 1.3: Go Back from Config Panel
```bash
podx run
```

**Expected Behavior:**
1. TUI launches, select an episode
2. Config modal appears
3. Press Esc
4. ✅ Returns to episode browser (NOT exit)
5. ✅ Previously selected episode is still highlighted
6. Select same episode again, press Enter
7. ✅ Config modal shows with previous selections preserved

### Test 1.4: Cancel from Config Panel
```bash
podx run
```

**Expected Behavior:**
1. Navigate to config panel
2. Modify some options
3. Press Esc twice (once to go back, once to cancel from episode list)
4. Terminal shows cancellation message

---

## Test 2: `podx-preprocess` - Interactive Transcript Processing

### Test 2.1: Full Preprocessing Flow
```bash
podx-preprocess --interactive
```

**Expected Behavior:**
1. ✅ TUI launches with two-phase browser (episode → transcript)
2. Select an episode
3. ✅ Shows available transcripts (preprocessed → diarized → aligned → base)
4. Select most processed transcript
5. ✅ Prompted for preprocessing options (merge, normalize, restore)
6. Complete preprocessing
7. ✅ TUI exits with completion message:
    ```
    ✅ Preprocessing complete
       Steps: merge + normalize + restore
       Output: {output_file}
    ```

### Test 2.2: Cancel at Episode Selection
```bash
podx-preprocess --interactive
```

**Expected Behavior:**
1. Press Esc at episode selection
2. Terminal shows:
   ```
   ❌ Transcript pre-processing cancelled
   ```

### Test 2.3: Cancel at Options Prompt
```bash
podx-preprocess --interactive
```

**Expected Behavior:**
1. Select an episode
2. Select a transcript
3. At preprocessing options prompt, enter 'Q'
4. Terminal shows:
   ```
   ❌ Transcript pre-processing cancelled
   ```

---

## Test 3: `podx-diarize` - Interactive Diarization

### Test 3.1: Full Diarization Flow
```bash
podx-diarize --interactive
```

**Expected Behavior:**
1. ✅ TUI launches with two-phase browser
2. Select episode → select transcript
3. Diarization runs
4. ✅ Completion message:
    ```
    ✅ Diarization complete
       Model: {asr_model}
       Output: {output_file}
    ```

### Test 3.2: Cancel Diarization
```bash
podx-diarize --interactive
```

**Expected Behavior:**
1. Press Esc at selection
2. Terminal shows:
   ```
   ❌ Transcript selection cancelled
   ```

---

## Test 4: `podx-deepcast` - Interactive Analysis

### Test 4.1: Full Deepcast Flow
```bash
podx-deepcast --interactive
```

**Expected Behavior:**
1. ✅ TUI launches with episode selection
2. ✅ Footer shows proper shortcuts
3. Select episode, press Enter
4. ✅ TUI exits (no Rich output)
5. ✅ Terminal prompts for deepcast type selection:
    ```
    📝 Select deepcast type:
       1  general ← Default
       2  technical
       ...
    ```
6. Select type
7. ✅ Terminal prompts for AI model:
    ```
    👉 Select AI model (default: gpt-4o, Q to cancel):
    ```
8. Select model
9. Processing runs
10. ✅ Completion message:
     ```
     ✅ Deepcast complete
        Type: {type}
        AI Model: {model}
        Outputs:
           🤖 JSON: {json_path}
           📄 Markdown: {md_path}
           📕 PDF: {pdf_path}
     ```

### Test 4.2: Cancel at Episode Selection
```bash
podx-deepcast --interactive
```

**Expected Behavior:**
1. Press Esc in TUI
2. Terminal shows:
   ```
   ❌ Episode selection cancelled
   ```

### Test 4.3: Cancel at Type Selection
```bash
podx-deepcast --interactive
```

**Expected Behavior:**
1. Select episode in TUI
2. At type prompt, enter 'Q'
3. Exits gracefully

---

## Test 5: `podx-notion` - Interactive Notion Upload

### Test 5.1: Full Notion Upload Flow
```bash
podx-notion --interactive
```

**Expected Behavior:**
1. ✅ Terminal shows formatted table (NOT Rich table):
    ```
    🪄 Select an analysis to upload to Notion

      #  Show                  Date          Title                           AI              ASR            Type                Trk   Rec  Notion
    --------------------------------------------------------------------------------------------------------------------------------------------
      1  My Show              2025-01-15    Episode Title                   gpt-4o         whisper-large  general             C     ✓    -
    ```
2. ✅ Prompt shows:
    ```
    Enter selection number, or Q to cancel.
    👉 1-5 (Enter=1):
    ```
3. Select analysis
4. ✅ Database selection prompt (simple print, not Rich):
    ```
    Select Notion database:
      1. Production DB
      2. Test DB
      0. Enter ID manually
    ```
5. Select database
6. Upload completes
7. ✅ Completion message:
    ```
    ✅ Notion upload complete
       Episode: {episode_title}
       Database: {db_name}
       Page URL: {page_url}
    ```

### Test 5.2: Cancel at Analysis Selection
```bash
podx-notion --interactive
```

**Expected Behavior:**
1. At analysis selection, enter 'Q'
2. Terminal shows:
   ```
   ❌ Notion upload cancelled
   ```

### Test 5.3: Dry Run Mode
```bash
podx-notion --interactive --dry-run
```

**Expected Behavior:**
1. Select analysis and database
2. ✅ Shows JSON payload (not Rich formatted)
3. ✅ Shows completion:
    ```
    ✅ Dry run prepared. Payload summarized above.
    ```

---

## Test 6: Terminal Corruption Prevention

### Test 6.1: Rapid Cancellation
```bash
podx run
# Immediately press Esc when TUI appears
```

**Expected Behavior:**
1. TUI exits cleanly
2. Terminal prompt works normally (not corrupted)
3. Run `reset` to verify terminal is clean

### Test 6.2: Ctrl+C During TUI
```bash
podx run
# Press Ctrl+C while in TUI
```

**Expected Behavior:**
1. TUI exits
2. Terminal returns to normal state
3. Run `reset` if needed to verify

---

## Test 7: Selection Preservation

**STATUS: NOT YET IMPLEMENTED**

This requires architectural changes to show ConfigPanel as a modal WITHIN EpisodeBrowserTUI (instead of separate apps).

**Current behavior:**
- Episode browser exits when you press Enter
- ConfigPanel launches as separate app
- Pressing Esc in config shows cancellation message and exits
- Cannot navigate back to episode list

**When implemented:**
- ConfigPanel will be a modal within episode browser
- Esc will dismiss modal and return to episode list with cursor preserved
- Can re-enter config or select different episode

---

## Test 8: ExecutionTUI Progress Tracking

**STATUS: NOT YET IMPLEMENTED**

ExecutionTUI infrastructure exists but is not integrated with the pipeline orchestrator. This is a deferred enhancement (estimated 4-6 hours of refactoring).

**When implemented, it will:**
- Show live progress in TUI during pipeline execution
- Display progress bar with current step
- Show execution log with timestamps
- Support --verbose mode for detailed logging

**Current behavior:** After config, TUI exits and progress shows in terminal.

---

## Test 9: No Rich Output Verification

### Test 9.1: Check All Commands
For each command, verify NO Rich panels/headers appear:

```bash
podx run                           # Should go straight to TUI
podx-preprocess --interactive      # Should go straight to TUI
podx-diarize --interactive         # Should go straight to TUI
podx-deepcast --interactive        # Should go straight to TUI
podx-notion --interactive          # Should show plain table
```

**Expected:**
- No decorative boxes/panels before TUI
- No "PodX" header with version
- No Rich-formatted confirmation prompts

---

## Test 10: Edge Cases

### Test 10.1: Empty Episode Directory
```bash
cd /tmp/empty_dir
podx run
```

**Expected:**
- TUI shows "No episodes found" message gracefully

### Test 10.2: No Deepcast Files for Notion
```bash
cd /tmp/no_deepcast
podx-notion --interactive
```

**Expected:**
```
❌ No deepcast files found in /tmp/no_deepcast
```

### Test 10.3: Invalid Selection
```bash
podx run
# Select episode
# In config, enter invalid values
```

**Expected:**
- Validation errors shown clearly
- Can correct and continue

---

## Success Criteria

All tests should pass with:
- ✅ Clean TUI launch (no Rich output)
- ✅ Proper navigation (Esc goes back on nested screens)
- ✅ Clear cancellation messages with ❌
- ✅ Detailed completion messages with ✅
- ✅ No terminal corruption
- ✅ Selection preservation when navigating back
- ✅ Live progress updates in ExecutionTUI
- ✅ All emoji-based terminal messages display correctly

---

## Notes

- Test in a clean terminal session
- Run `reset` between tests if terminal gets corrupted
- Verify all completion messages include relevant paths/info
- Check that Esc behavior is consistent (back vs cancel)
- Ensure Enter is always shown in footer with action label
