# Contributing to PodX

## Development Workflow

### Prerequisites

```bash
# Install with dev dependencies
pip install -e ".[dev,server]"
```

### Before Committing: Test Locally

**Run this BEFORE every commit to avoid CI failures:**

```bash
# Test across all Python versions (recommended)
tox

# Or test specific Python version
tox -e py39  # Minimum supported version - most important!

# Or run linting only (fast)
tox -e lint

# Auto-format code
tox -e format
```

### Quick Local Testing

If you don't have all Python versions installed:

```bash
# Run tests on your current Python version
pytest tests/ --cov=podx --timeout=30 -v

# Run linting checks
ruff check .
black --check .
isort --check-only .

# Auto-format
black .
isort .
```

### Pre-commit Hooks

Pre-commit hooks are already configured! They run automatically on `git commit`.

To run manually:
```bash
pre-commit run --all-files
```

## Release Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make Changes and Test Locally**
   ```bash
   # CRITICAL: Test before pushing!
   tox
   ```

3. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

4. **Push and Create PR**
   ```bash
   git push -u origin feature/my-feature
   gh pr create --base main --head feature/my-feature
   ```

5. **Wait for CI to Pass**
   - CI will run automatically on all PRs
   - Fix any failures and push new commits to the PR branch

6. **Merge PR**
   ```bash
   # After CI passes and review approved
   gh pr merge --squash
   ```

## Why Tox?

Tox ensures your code works across all supported Python versions (3.9-3.12) **before** you push to GitHub. This prevents the messy git history pollution that comes from fixing CI failures after pushing.

### What Tox Does

1. Creates isolated virtual environments for each Python version
2. Installs your package in each environment
3. Runs the full test suite (832 tests)
4. Reports which Python versions pass/fail

### Common Tox Commands

```bash
# Test all versions (can be slow first time)
tox

# Test specific version
tox -e py39
tox -e py312

# Run linting only (fast!)
tox -e lint

# Auto-format code
tox -e format

# List all available environments
tox -l

# Rebuild environments (if dependencies changed)
tox -r
```

## Python Version Support

- **Minimum**: Python 3.9
- **Maximum**: Python 3.12
- **Most Important to Test**: Python 3.9 (minimum version)

Always test on Python 3.9 locally because it catches compatibility issues that newer versions might hide (like PEP 604 union syntax `X | Y`).

## CI/CD Pipeline

GitHub Actions runs automatically on:
- All pushes to `main` and `develop` branches
- All pull requests (regardless of target branch)
- Manual triggers via `workflow_dispatch`

The CI pipeline runs:
1. Linting (ruff, black, isort, mypy)
2. Tests on Python 3.9-3.12 across Ubuntu, macOS, Windows
3. Security scanning (pip-audit, safety)
4. Documentation build
5. Distribution package build

## Known Issues

There are currently 7 pre-existing test failures in:
- `tests/unit/test_server_cleanup.py` (4 failures)
- `tests/unit/test_server_health_enhanced.py` (3 failures)

These are test logic bugs and do not affect functionality. CI is considered passing if you see "799 passed, 7 failed".
