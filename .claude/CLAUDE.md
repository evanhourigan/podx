# PodX Claude Code Instructions

Project-specific instructions for Claude Code when working on the PodX codebase.

## Planning Multi-Step Features

For non-trivial features (more than a few file edits):

1. **Create a plan file** with implementation checklist in `~/.claude/plans/` or `.ai-docs/`
2. **Include progress tracking** - checkboxes to survive context compaction
3. **Add recovery instructions** - "If context compacts, read this file and X for full context"
4. **Update the plan file** as you complete steps (check off items)

Example checklist format:
```markdown
## Implementation Progress
- [x] 1. Completed step
- [ ] 2. Current step  <-- mark "Current step: 2" below
- [ ] 3. Next step

**Current step**: 2
**If context compacts**: Read this file and `.ai-docs/RELEVANT_RESEARCH.md`
```

## Pre-commit Checklist

Before committing any changes, always run these checks:

1. **Run tests**:
   ```bash
   pytest tests/
   ```

2. **Run linting**:
   ```bash
   ruff check podx/
   ```

3. **Run formatter checks**:
   ```bash
   black --check podx/
   isort --check-only podx/
   ```

4. **Fix any issues** - If checks fail:
   ```bash
   ruff check podx/ --fix
   black podx/
   isort podx/
   ```

5. **Evaluate documentation** - Consider if changes need:
   - CHANGELOG.md updates
   - README.md updates
   - docs/ updates (TROUBLESHOOTING.md, etc.)

6. **Version bumping** - Follow semantic versioning:
   - **Patch** (4.1.0 → 4.1.1): Bug fixes, minor improvements
   - **Minor** (4.1.0 → 4.2.0): New features, backwards compatible
   - **Major** (4.1.0 → 5.0.0): Breaking changes

   Update version in:
   - `podx/__init__.py` (`__version__`)
   - `CHANGELOG.md` (add new section)

## CI Failure Protocol

If CI fails after pushing:

1. Fix the issues locally
2. If multiple fix commits are needed, squash them:
   ```bash
   git rebase -i HEAD~N  # N = number of commits to squash
   ```
3. Force push to update the branch:
   ```bash
   git push --force
   ```

## Code Style

- Use type hints for function signatures
- Add `-> None` return type for functions that don't return values
- Follow existing patterns in the codebase
- Prefer editing existing files over creating new ones

## Testing

- Run full test suite before commits: `pytest tests/`
- Run specific tests during development: `pytest tests/ -k "keyword"`
- Tests should pass locally before pushing

## Documentation

- Keep CHANGELOG.md up to date with user-facing changes
- Update TROUBLESHOOTING.md for new error scenarios
- Update .claude/CONTEXT.md to reflect current state

## Release Workflow

After all checks pass and changes are committed:

1. **Push to main**: `git push`
2. **Watch CI**: `gh run watch` - wait for all checks to pass
3. **Tag the release** (after CI passes):
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

Always tag releases so users can reference specific versions.
