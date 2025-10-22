# How to Automatically Save Context in Claude Code

## Option 1: User Prompt Submit Hook (Recommended)

Claude Code can run commands automatically after you submit a message. This is the best way to auto-update context.

### Setup Steps

1. **Create a hook script** (`.claude/hooks/update-context.sh`):

```bash
#!/bin/bash
# Auto-update context file after each user message

CONTEXT_FILE=".claude/CONTEXT.md"
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# Update timestamp in context file
if [ -f "$CONTEXT_FILE" ]; then
    sed -i.bak "s/\*\*Last Updated\*\*:.*/\*\*Last Updated**: $TIMESTAMP/" "$CONTEXT_FILE"
    rm -f "$CONTEXT_FILE.bak"
fi

# Optional: Auto-commit context changes
if git diff --quiet "$CONTEXT_FILE"; then
    exit 0
else
    git add "$CONTEXT_FILE"
    git commit -m "chore(context): auto-update context timestamp" --no-verify
fi
```

2. **Make it executable**:
```bash
chmod +x .claude/hooks/update-context.sh
```

3. **Configure in settings**:

Create/edit `.claude/settings.local.json`:
```json
{
  "hooks": {
    "user-prompt-submit": ".claude/hooks/update-context.sh"
  }
}
```

### How It Works
- **When**: After every message you send to Claude
- **What**: Updates timestamp, auto-commits context changes
- **Benefit**: Always have up-to-date context without manual intervention

---

## Context Recovery Best Practices

### 1. Use Descriptive Commit Messages
Every commit is a context checkpoint:
```bash
git commit -m "test(okr): add 13 tests for objectives and key results (67% coverage)"
```

### 2. Keep Multiple Context Files
- `.claude/CONTEXT.md` - Current state (this file)
- `SESSION_X_SUMMARY.md` - Detailed session summaries
- Git history - Complete audit trail

### 3. Document Key Decisions
When you make important decisions, document them:
```markdown
## Key Decisions Made
- **2025-10-22**: Migrated all interactive modes to Textual TUI for consistency
```

---

## What to Share When Context Is Lost

### Quick Recovery Template

```
Hi Claude! I lost context mid-session. Here's where we are:

**Project**: PodX v2.0 - Textual TUI Enhancement

**Current State**:
- Read .claude/CONTEXT.md for latest state
- All interactive modes using Textual TUI

**Last Working On**: [TASK]

**Next Step**: [NEXT TASK]

**Recent Commits**:
[paste: git log --oneline -5]

Please continue from where we left off!
```

### Files to Check
1. `.claude/CONTEXT.md` - Current state (always check this first!)
2. `SESSION_X_SUMMARY.md` - Latest session details
3. `git log --oneline -10` - Recent work
4. `README.md` - Project overview

---

**Recommendation**: Use **User Prompt Submit Hook** for automatic timestamp updates,
combined with **manual milestone updates** for detailed documentation.
