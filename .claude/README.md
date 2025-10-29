# PodX Claude Code Configuration

This directory contains Claude Code configuration and session documentation for the PodX project.

## Files

- **`settings.json`** - Project-specific permissions for Claude Code
- **`SESSION_NOTES.md`** - Detailed session notes for resuming work
- **`README.md`** - This file

## Quick Resume

To resume where you left off:

1. Read `SESSION_NOTES.md` for complete context
2. Check current branch: `git status`
3. Verify you're on `refactor/v2-architecture` branch
4. Current status: **Module extraction complete, ready for testing**

## Current State

✅ All 9 core modules extracted to `podx/core/`
✅ All commits pushed to remote
✅ 3,014 lines of pure business logic
⏳ Next: Write unit tests for 5 new modules

## Key Commands

```bash
# View session notes
cat .claude/SESSION_NOTES.md

# Run existing tests
pytest tests/unit/ -v

# Check core modules
ls -la podx/core/

# Check git state
git status
git log --oneline -10
```

## Permissions Configured

- ✅ Global: `~/.claude/settings.local.json`
- ✅ Project: `.claude/settings.json` (this directory)

Most development commands now run without approval.

---

**Last Updated**: 2025-10-28
**Branch**: `refactor/v2-architecture`
**Next Action**: Write unit tests
