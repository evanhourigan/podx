#!/bin/bash
# Auto-update context file after each user message

CONTEXT_FILE=".claude/CONTEXT.md"
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

if [ -f "$CONTEXT_FILE" ]; then
    # Update timestamp
    sed -i.bak "s/\*\*Last Updated\*\*:.*/\*\*Last Updated**: $TIMESTAMP/" "$CONTEXT_FILE"
    rm -f "$CONTEXT_FILE.bak"

    # Optional: Auto-commit (uncomment if desired)
    # if ! git diff --quiet "$CONTEXT_FILE"; then
    #     git add "$CONTEXT_FILE"
    #     git commit -m "chore(context): auto-update $(date +%H:%M)" --no-verify
    # fi
fi
