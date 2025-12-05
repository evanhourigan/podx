# PodX Claude Code Instructions

Project-specific instructions for Claude Code when working on the PodX codebase.

## Core Workflow Principles

### 1. Commit Early and Often (But Don't Push)

**ALWAYS commit changes as you complete them.** Create atomic commits for each logical change:
- One commit per feature, bug fix, or improvement
- Include relevant documentation updates IN THE SAME COMMIT as the code change
- **DO NOT push** until user explicitly requests it or approves the commit history

This allows the user to review, reorder, squash, or amend commits before pushing.

### 2. Documentation Is Part of the Change

**Every code change that affects user-facing behavior MUST include documentation updates in the same commit:**

- **New features/commands**: Update README.md command table, add usage examples
- **Bug fixes**: Update CHANGELOG.md (in Unreleased section)
- **New options/flags**: Update command help text and README
- **Breaking changes**: Update CHANGELOG.md, MIGRATION docs if needed
- **Error handling changes**: Update TROUBLESHOOTING.md

Ask yourself: "If a user reads only the docs, will they know about this change?"

### 3. Pre-Push Verification (CI Simulation)

**Before pushing, run the FULL CI pipeline locally:**

```bash
# 1. Run all tests
pytest tests/

# 2. Run linting
ruff check podx/

# 3. Run formatters (check mode)
black --check podx/
isort --check-only podx/

# 4. Fix any issues if needed
ruff check podx/ --fix
black podx/
isort podx/
```

**Only push after ALL checks pass locally.** This prevents CI failures and wasted iteration cycles.

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

## Commit Message Format

Use conventional commits:
```
type(scope): short description

Longer description if needed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## Pre-commit Checklist

Before committing any changes:

1. **Run tests**: `pytest tests/`
2. **Run linting**: `ruff check podx/`
3. **Run formatter checks**: `black --check podx/ && isort --check-only podx/`
4. **Fix any issues**:
   ```bash
   ruff check podx/ --fix
   black podx/
   isort podx/
   ```
5. **Update documentation** (CHANGELOG.md, README.md, docs/) as needed
6. **Version bump** if releasing (see below)

## Version Bumping

Follow semantic versioning:
- **Patch** (4.1.0 → 4.1.1): Bug fixes, minor improvements
- **Minor** (4.1.0 → 4.2.0): New features, backwards compatible
- **Major** (4.1.0 → 5.0.0): Breaking changes

Update version in:
- `podx/__init__.py` (`__version__`)
- `CHANGELOG.md` (add new section with date)

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

## Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | User-facing docs, command reference, examples |
| `CHANGELOG.md` | Release notes, what changed between versions |
| `docs/TROUBLESHOOTING.md` | Common errors and solutions |
| `docs/QUICKSTART.md` | Getting started guide |
| `.claude/CONTEXT.md` | Internal context for Claude Code |

## Release Workflow

After all checks pass and user approves commits:

1. **Push to main**: `git push`
2. **Watch CI**: `gh run watch` - wait for all checks to pass
3. **Tag the release** (after CI passes):
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

Always tag releases so users can reference specific versions.
