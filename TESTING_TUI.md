# Testing Textual TUI Applications

## ⚠️ CRITICAL: Terminal Corruption Issue

### The Problem

**NEVER use `timeout` or forcefully kill Textual TUI applications during testing.**

When a Textual TUI app is forcefully terminated (via `timeout`, Ctrl+C, or kill signals), it cannot properly clean up the terminal state. This leaves the terminal in "alternate screen mode" with escape sequences active, causing:

- Escape codes appearing in normal terminal output
- Mouse movements generating visible escape sequences
- Special keys (Shift+Space, etc.) outputting codes like `[32;2u`
- Terminal becoming **completely unusable** and unrecoverable within the session

### Why This Happens

Textual apps use terminal escape codes to:
1. Enter alternate screen buffer (full-screen mode)
2. Enable mouse tracking
3. Set up raw input mode
4. Configure special key handling

When killed forcefully, the cleanup code (`App.exit()`) never runs, leaving these modes active.

### Impact on Claude Code Sessions

**Terminal corruption makes the Claude Code session UNRECOVERABLE:**
- Cannot continue working - must close terminal and start new session
- Loses all context unless properly saved beforehand
- Wastes significant time and disrupts workflow

**This is why we implemented the context recovery system** - to mitigate the impact of forced session termination.

## ✅ Safe Testing Approaches

### Option 1: Manual Testing (RECOMMENDED for Claude Code)

When Claude implements TUI changes, **DO NOT test automatically**. Instead:

**Claude's instructions should be:**
```
I've implemented the changes. To test:

1. Open a NEW terminal window (separate from this Claude Code session)
2. Navigate to the test directory:
   cd ~/Desktop/Current/podx-test
3. Run the command:
   podx run --interactive --scan-dir .
4. Verify the changes (e.g., no command palette, clean header)
5. Press Escape to exit cleanly
6. Report back the results

DO NOT test in this terminal window.
```

**Benefits:**
- Keeps Claude Code session safe
- User can test at their own pace
- Proper cleanup when exiting with Escape
- No terminal corruption risk

### Option 2: Automated Testing with Textual's Test Harness

For CI/CD and automated testing, use Textual's built-in testing utilities:

```python
import pytest
from textual.pilot import Pilot
from podx.ui.episode_browser_tui import EpisodeBrowserTUI

async def test_episode_browser_no_command_palette():
    """Test that command palette is disabled."""
    app = EpisodeBrowserTUI(episodes=[], scan_dir=Path("."))

    async with app.run_test() as pilot:
        # Verify command palette is disabled
        assert not app.ENABLE_COMMAND_PALETTE

        # Verify header has no icon
        header = app.query_one("Header")
        # Test header properties...

        # Exit cleanly
        await pilot.press("escape")

# Run with pytest
pytest tests/tui/test_episode_browser.py -v
```

**Benefits:**
- No actual terminal rendering
- Fast execution
- Can test UI logic without corruption risk
- Fully automated in CI/CD

**Example test file:** `tests/tui/test_episode_browser.py`

```python
"""Tests for Textual TUI episode browser."""
import pytest
from pathlib import Path
from textual.pilot import Pilot
from podx.ui.episode_browser_tui import (
    EpisodeBrowserTUI,
    ModelLevelProcessingBrowser,
    SimpleProcessingBrowser,
)


class TestCommandPaletteDisabled:
    """Test that command palette is disabled across all TUI apps."""

    async def test_episode_browser_tui_no_palette(self):
        """EpisodeBrowserTUI should have command palette disabled."""
        app = EpisodeBrowserTUI(episodes=[], scan_dir=Path("."))
        assert app.ENABLE_COMMAND_PALETTE is False

    async def test_model_level_browser_no_palette(self):
        """ModelLevelProcessingBrowser should have command palette disabled."""
        app = ModelLevelProcessingBrowser(items=[], model_key="asr_model")
        assert app.ENABLE_COMMAND_PALETTE is False

    async def test_simple_processing_browser_no_palette(self):
        """SimpleProcessingBrowser should have command palette disabled."""
        app = SimpleProcessingBrowser(episodes=[])
        assert app.ENABLE_COMMAND_PALETTE is False


class TestHeaderConfiguration:
    """Test that headers are configured correctly."""

    async def test_episode_browser_header(self):
        """EpisodeBrowserTUI should have clean header."""
        app = EpisodeBrowserTUI(episodes=[], scan_dir=Path("."))

        async with app.run_test() as pilot:
            # Verify header exists
            header = app.query_one("Header")
            assert header is not None

            # Note: Testing icon and clock requires examining the Header widget's
            # internal state or rendering output
            await pilot.press("escape")


# Run with: pytest tests/tui/ -v
```

### Option 3: Visual Screenshot Testing

For verifying visual appearance, use screenshot-based testing:

**How to provide screenshots to Claude:**

1. **Take a screenshot:**
   - macOS: `Command + Shift + 4` (select area) or `Command + Shift + 3` (full screen)
   - Linux: `gnome-screenshot` or `scrot`
   - Saves to Desktop by default

2. **Provide the path to Claude:**
   ```
   Here's a screenshot of the TUI:
   [Drag and drop the image, or provide path]
   /Users/evan/Desktop/Screenshot 2025-10-22 at 10.15.23.png
   ```

3. **Claude can read the image:**
   - Claude Code has the Read tool that can view images (PNG, JPG, etc.)
   - Claude will analyze the visual appearance
   - Can verify layout, colors, text content, etc.

**Example workflow:**
```
User: "Here's a screenshot of the TUI after your changes"
User: [provides screenshot path or drags image]

Claude: [uses Read tool to view image]
Claude: "I can see the header is now clean without the circle icon..."
```

## 🚫 What NOT To Do

### ❌ NEVER Use These Commands

```bash
# BAD - Will corrupt terminal
timeout 5 podx run --interactive
timeout 10 podx-diarize --interactive
pkill podx
kill -9 <pid>

# BAD - Ctrl+C during TUI app
# (Sometimes okay if app handles it, but risky)
```

### ❌ NEVER Test TUI in Claude Code Session

```bash
# BAD - Testing in same terminal as Claude Code
cd ~/Desktop/Current/podx-test
podx run --interactive --scan-dir .
# [Terminal gets corrupted, session becomes unusable]
```

## ✅ Recovery Procedures

### If Terminal Gets Corrupted

**During a Claude Code session:**

1. **Save session context immediately:**
   ```
   "Please save this session"
   ```

2. **Close the corrupted terminal window:**
   - Don't try to continue working
   - `reset` won't work from within the session

3. **Open new terminal:**
   - Start fresh Claude Code session
   - Tell Claude: "Read .claude/CONTEXT.md and SESSION_X_SUMMARY.md"
   - Continue from where you left off

**After closing corrupted terminal:**

If you see corruption in a NEW terminal (rare), run:
```bash
reset
stty sane
tput reset
```

## 📋 Testing Checklist

Before implementing TUI changes, decide on testing approach:

- [ ] **Manual testing** - Provide user with clear instructions for separate terminal
- [ ] **Unit tests** - Write Textual test harness tests
- [ ] **Screenshot review** - Request user to provide screenshot

After implementation:

- [ ] Document what needs to be tested
- [ ] Provide clear testing instructions (if manual)
- [ ] Wait for user confirmation before proceeding
- [ ] Update context after testing is complete

## 🎯 Best Practices Summary

1. **Manual testing in separate terminal** - Safest for development
2. **Automated tests with Textual harness** - Best for CI/CD
3. **Screenshot review** - Good for visual verification
4. **NEVER use timeout with TUI apps** - Causes unrecoverable corruption
5. **Save context before testing** - Protection against corruption
6. **Exit TUI apps with Escape** - Ensures proper cleanup

## 📚 References

- [Textual Testing Documentation](https://textual.textualize.io/guide/testing/)
- [Textual Pilot API](https://textual.textualize.io/api/pilot/)
- [Claude Code Read Tool](https://docs.claude.com/claude-code) - Supports image viewing

---

**Last Updated:** 2025-10-22 (Session 1)
**Related Issues:** Terminal corruption, TUI testing, Session recovery
