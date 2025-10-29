# PodX Testing Guide

This document describes testing strategies, patterns, and best practices for PodX v2.0.

## Table of Contents

- [Overview](#overview)
- [Test Organization](#test-organization)
- [Testing Core Modules](#testing-core-modules)
- [Mocking Strategies](#mocking-strategies)
- [Test Patterns](#test-patterns)
- [Coverage Requirements](#coverage-requirements)
- [Running Tests](#running-tests)
- [Writing New Tests](#writing-new-tests)

---

## Overview

PodX v2.0's core/CLI separation enables **pure unit testing** without UI dependencies. All core modules have comprehensive test coverage (95-100%) using pytest with standard Python mocking.

### Testing Philosophy

1. **Unit tests for core modules** - Test business logic in isolation
2. **Integration tests for pipelines** - Test component interaction
3. **No UI in unit tests** - Core tests never import Click
4. **Mock external dependencies** - No real API calls in tests
5. **Fast test suite** - All tests run in < 30 seconds

### Test Statistics

Current test coverage (v2.0):

| Module | Tests | Coverage | Status |
|--------|-------|----------|--------|
| core.export | 51 | 99% | ✅ |
| core.youtube | 41 | 97% | ✅ |
| core.diarize | 20 | 100% | ✅ |
| core.deepcast | 32 | 98% | ✅ |
| core.notion | 39 | 85-95% | ✅ |
| **Total** | **183** | **97%** | ✅ |

---

## Test Organization

### Directory Structure

```
tests/
├── unit/                           # Fast, isolated unit tests
│   ├── test_core_transcode.py     # Transcode engine tests
│   ├── test_core_fetch.py         # Fetch engine tests
│   ├── test_core_preprocess.py    # Preprocess engine tests
│   ├── test_core_transcribe.py    # Transcribe engine tests
│   ├── test_core_diarize.py       # Diarize engine tests (20 tests)
│   ├── test_core_deepcast.py      # Deepcast engine tests (32 tests)
│   ├── test_core_notion.py        # Notion engine tests (39 tests)
│   ├── test_core_export.py        # Export engine tests (51 tests)
│   ├── test_core_youtube.py       # YouTube engine tests (41 tests)
│   └── ...                        # Other unit tests
│
├── integration/                    # Slower integration tests
│   ├── test_pipeline.py           # Pipeline component interaction
│   └── test_end_to_end.py         # Full pipeline tests
│
├── fixtures/                       # Shared test data
│   ├── audio/                     # Sample audio files
│   ├── transcripts/               # Sample transcript JSON
│   └── ...
│
└── conftest.py                    # Pytest configuration & fixtures
```

### Test File Naming

- **Unit tests:** `test_core_<module>.py`
- **Integration tests:** `test_<feature>.py`
- **Test classes:** `Test<ClassName>` or `Test<Feature>`
- **Test methods:** `test_<specific_behavior>`

---

## Testing Core Modules

### Basic Test Structure

Every core module test file follows this pattern:

```python
"""Unit tests for core.<module> module.

Tests pure business logic without UI dependencies.
Focuses on [specific functionality areas].
"""

import pytest
from unittest.mock import MagicMock, patch
from podx.core.<module> import <Module>Engine, <Module>Error


class Test<Module>EngineInit:
    """Test <Module>Engine initialization."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        engine = <Module>Engine()
        assert engine.option1 == expected_default
        assert engine.progress_callback is None

    def test_init_with_options(self):
        """Test initialization with custom options."""
        engine = <Module>Engine(option1=value1)
        assert engine.option1 == value1

    def test_init_with_callback(self):
        """Test initialization with progress callback."""
        callback = lambda msg: None
        engine = <Module>Engine(progress_callback=callback)
        assert engine.progress_callback is callback


class Test<Module>EngineOperation:
    """Test <Module>Engine main operations."""

    @pytest.fixture
    def engine(self):
        """Fixture providing configured engine."""
        return <Module>Engine()

    def test_operation_success(self, engine):
        """Test successful operation."""
        result = engine.operation(valid_input)
        assert result["status"] == "success"

    def test_operation_invalid_input(self, engine):
        """Test operation with invalid input raises error."""
        with pytest.raises(<Module>Error, match="Invalid input"):
            engine.operation(invalid_input)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_input(self):
        """Test handling of empty input."""
        engine = <Module>Engine()
        # Specific edge case test
```

### Progress Callback Testing

Test that progress callbacks are called appropriately:

```python
def test_operation_with_progress_callback(self):
    """Test that progress callback is called during operation."""
    messages = []
    engine = ModuleEngine(progress_callback=messages.append)

    engine.operation(test_input)

    # Verify callbacks were made
    assert len(messages) > 0
    assert "Starting" in messages[0]
    assert "Complete" in messages[-1]


def test_operation_without_callback(self):
    """Test that operation works without progress callback."""
    engine = ModuleEngine(progress_callback=None)

    # Should not raise
    result = engine.operation(test_input)
    assert result["status"] == "success"
```

---

## Mocking Strategies

### Mocking External Libraries

For optional dependencies like `yt-dlp`, `whisperx`, `openai`:

```python
import sys
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_yt_dlp():
    """Mock yt_dlp module for testing without installation."""
    mock_module = MagicMock()
    sys.modules["yt_dlp"] = mock_module

    yield mock_module

    # Cleanup
    if "yt_dlp" in sys.modules:
        del sys.modules["yt_dlp"]


def test_download_success(mock_yt_dlp):
    """Test successful download with mocked yt-dlp."""
    mock_ydl = MagicMock()
    mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {"title": "Test Video"}

    engine = YouTubeEngine()
    result = engine.download("https://youtube.com/watch?v=test")

    assert result["title"] == "Test Video"
```

### Mocking Missing Libraries

Test error handling when dependencies aren't installed:

```python
def test_operation_missing_library(self):
    """Test error when required library is not installed."""
    original_import = __builtins__["__import__"]

    def mock_import(name, *args, **kwargs):
        if name == "required_library":
            raise ImportError("No module named 'required_library'")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        engine = ModuleEngine()
        with pytest.raises(ModuleError, match="required_library not installed"):
            engine.operation(test_input)
```

### Mocking API Calls

Mock external API calls with predictable responses:

```python
def test_analyze_with_openai(self):
    """Test analysis with mocked OpenAI API."""
    with patch("openai.OpenAI") as mock_openai_class:
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Analysis result"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test
        engine = DeepcastEngine()
        markdown, insights = engine.deepcast(transcript, metadata)

        assert "Analysis result" in markdown
        mock_client.chat.completions.create.assert_called_once()
```

### Mocking File I/O

Use `tmp_path` fixture for temporary file testing:

```python
def test_export_creates_files(tmp_path):
    """Test that export creates all expected files."""
    engine = ExportEngine()

    result = engine.export(
        transcript=sample_transcript,
        formats=["txt", "srt"],
        output_dir=str(tmp_path),
        base_filename="test"
    )

    # Verify files were created
    assert (tmp_path / "test.txt").exists()
    assert (tmp_path / "test.srt").exists()
    assert result["files_written"] == 2
```

---

## Test Patterns

### Testing Initialization

```python
class TestModuleEngineInit:
    """Test ModuleEngine initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        engine = ModuleEngine()
        assert engine.option == default_value
        assert engine.progress_callback is None

    def test_init_with_options(self):
        """Test initialization with custom options."""
        engine = ModuleEngine(option=custom_value)
        assert engine.option == custom_value

    def test_init_with_env_var(self):
        """Test that initialization reads from environment."""
        with patch.dict(os.environ, {"MODULE_VAR": "env_value"}):
            engine = ModuleEngine()
            assert engine.var == "env_value"

    def test_init_explicit_overrides_env(self):
        """Test that explicit args override environment."""
        with patch.dict(os.environ, {"MODULE_VAR": "env_value"}):
            engine = ModuleEngine(var="explicit_value")
            assert engine.var == "explicit_value"
```

### Testing Success Paths

```python
class TestModuleEngineOperation:
    """Test ModuleEngine successful operations."""

    @pytest.fixture
    def sample_input(self):
        """Fixture providing sample input data."""
        return {"field": "value"}

    def test_operation_basic(self, sample_input):
        """Test basic successful operation."""
        engine = ModuleEngine()
        result = engine.operation(sample_input)

        assert result["status"] == "success"
        assert "output" in result

    def test_operation_with_options(self, sample_input):
        """Test operation respects engine options."""
        engine = ModuleEngine(option=True)
        result = engine.operation(sample_input)

        # Verify option was applied
        assert result["option_applied"] is True
```

### Testing Error Paths

```python
class TestModuleEngineErrors:
    """Test ModuleEngine error handling."""

    def test_operation_invalid_input(self):
        """Test operation with invalid input raises error."""
        engine = ModuleEngine()

        with pytest.raises(ModuleError, match="Invalid input"):
            engine.operation(invalid_input)

    def test_operation_external_failure(self):
        """Test handling of external service failures."""
        with patch("module.external_service") as mock_service:
            mock_service.call.side_effect = Exception("Service error")

            engine = ModuleEngine()
            with pytest.raises(ModuleError, match="Operation failed"):
                engine.operation(test_input)

    def test_operation_missing_required_field(self):
        """Test error when required field is missing."""
        engine = ModuleEngine()
        incomplete_input = {"field": "value"}  # Missing required_field

        with pytest.raises(ModuleError, match="required_field"):
            engine.operation(incomplete_input)
```

### Testing Edge Cases

```python
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input(self):
        """Test handling of empty input."""
        engine = ModuleEngine()
        result = engine.operation("")

        # Define expected behavior for empty input
        assert result == expected_empty_result

    def test_very_large_input(self):
        """Test handling of unusually large input."""
        large_input = "A" * 1000000
        engine = ModuleEngine()
        result = engine.operation(large_input)

        # Should handle without error
        assert result["status"] == "success"

    def test_special_characters(self):
        """Test handling of special characters."""
        special_input = "Text with <>&\"' special chars"
        engine = ModuleEngine()
        result = engine.operation(special_input)

        # Should preserve special characters
        assert special_input in result["output"]

    def test_concurrent_operations(self):
        """Test that engine handles concurrent operations."""
        engine = ModuleEngine()

        # Run operations in parallel (if applicable)
        results = [engine.operation(f"input_{i}") for i in range(10)]

        assert all(r["status"] == "success" for r in results)
```

---

## Coverage Requirements

### Target Coverage Levels

- **Core modules:** 95-100% coverage
- **Utility functions:** 90-95% coverage
- **Error handling:** 80-90% coverage

### Measuring Coverage

```bash
# Run tests with coverage
pytest tests/unit/test_core_*.py --cov=podx.core --cov-report=term-missing

# Generate HTML report
pytest tests/unit/test_core_*.py --cov=podx.core --cov-report=html

# View report
open htmlcov/index.html
```

### Coverage by Module

Based on actual v2.0 test results:

```
Name                      Stmts   Miss  Cover   Missing
-------------------------------------------------------
podx/core/export.py         156      2    99%   245-246
podx/core/youtube.py        112      3    97%   89-91
podx/core/diarize.py         98      0   100%
podx/core/deepcast.py       187      4    98%   312-315
podx/core/notion.py         203     25    88%   Various
-------------------------------------------------------
TOTAL                       756     34    96%
```

### Improving Coverage

If coverage is below target:

1. **Identify uncovered lines:**
```bash
pytest --cov=podx.core --cov-report=term-missing | grep -A5 "Missing"
```

2. **Add tests for uncovered paths:**
```python
# Example: Test error path
def test_previously_uncovered_error_case(self):
    """Test error handling that wasn't covered."""
    with pytest.raises(ModuleError):
        engine.operation(error_inducing_input)
```

3. **Test edge cases:**
- Empty inputs
- Null values
- Boundary conditions
- Concurrent access

---

## Running Tests

### Basic Test Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_core_export.py

# Run specific test class
pytest tests/unit/test_core_export.py::TestExportEngine

# Run specific test method
pytest tests/unit/test_core_export.py::TestExportEngine::test_export_single_format

# Run with verbose output
pytest -v

# Run with output capture disabled (see prints)
pytest -s

# Run with specific markers
pytest -m "not slow"
```

### Coverage Commands

```bash
# Basic coverage
pytest --cov=podx.core

# Coverage with missing lines
pytest --cov=podx.core --cov-report=term-missing

# Coverage for specific module
pytest tests/unit/test_core_export.py --cov=podx.core.export

# HTML coverage report
pytest --cov=podx.core --cov-report=html
open htmlcov/index.html
```

### Fast Test Iterations

```bash
# Run only failed tests from last run
pytest --lf

# Run failed tests first, then others
pytest --ff

# Stop on first failure
pytest -x

# Run specific number of processes in parallel
pytest -n 4
```

### Test Discovery

```bash
# List all tests without running
pytest --collect-only

# List tests matching pattern
pytest --collect-only -k "export"

# Show test durations
pytest --durations=10
```

---

## Writing New Tests

### Step-by-Step Test Writing

1. **Create test file:**
```bash
touch tests/unit/test_core_newmodule.py
```

2. **Import required modules:**
```python
"""Unit tests for core.newmodule."""

import pytest
from unittest.mock import MagicMock, patch
from podx.core.newmodule import NewModuleEngine, NewModuleError
```

3. **Create test class for initialization:**
```python
class TestNewModuleEngineInit:
    """Test NewModuleEngine initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        engine = NewModuleEngine()
        assert engine.progress_callback is None
```

4. **Add test fixtures:**
```python
@pytest.fixture
def sample_input():
    """Provide sample input data."""
    return {"key": "value"}

@pytest.fixture
def engine():
    """Provide configured engine."""
    return NewModuleEngine()
```

5. **Write success path tests:**
```python
class TestNewModuleEngineOperation:
    """Test NewModuleEngine operations."""

    def test_operation_success(self, engine, sample_input):
        """Test successful operation."""
        result = engine.operation(sample_input)
        assert result["status"] == "success"
```

6. **Write error path tests:**
```python
def test_operation_invalid_input(self, engine):
    """Test operation with invalid input."""
    with pytest.raises(NewModuleError):
        engine.operation(invalid_input)
```

7. **Add edge case tests:**
```python
class TestEdgeCases:
    """Test edge cases."""

    def test_empty_input(self, engine):
        """Test empty input handling."""
        result = engine.operation("")
        assert result is not None
```

8. **Run tests:**
```bash
pytest tests/unit/test_core_newmodule.py -v
```

### Test Template

Use this template for new test files:

```python
"""Unit tests for core.<module> module.

Tests pure business logic without UI dependencies.
Focuses on [main functionality areas].
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from podx.core.<module> import <Module>Engine, <Module>Error


class Test<Module>EngineInit:
    """Test <Module>Engine initialization."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        engine = <Module>Engine()
        assert engine.progress_callback is None


class Test<Module>EngineOperation:
    """Test <Module>Engine main operations."""

    @pytest.fixture
    def engine(self):
        """Fixture providing configured engine."""
        return <Module>Engine()

    @pytest.fixture
    def sample_input(self):
        """Fixture providing sample input."""
        return {"test": "data"}

    def test_operation_success(self, engine, sample_input):
        """Test successful operation."""
        result = engine.operation(sample_input)
        assert result["status"] == "success"

    def test_operation_with_callback(self, sample_input):
        """Test operation calls progress callback."""
        messages = []
        engine = <Module>Engine(progress_callback=messages.append)
        engine.operation(sample_input)
        assert len(messages) > 0

    def test_operation_invalid_input(self, engine):
        """Test operation with invalid input."""
        with pytest.raises(<Module>Error):
            engine.operation(invalid_input)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_input(self):
        """Test handling of empty input."""
        engine = <Module>Engine()
        # Test empty input behavior
```

---

## Best Practices

### DO

✅ **Test one thing per test**
```python
def test_export_creates_txt_file(self):
    """Test that TXT export creates file."""
    # Test only TXT file creation
```

✅ **Use descriptive test names**
```python
def test_diarize_identifies_multiple_speakers(self):
    """Clear description of what's being tested."""
```

✅ **Use fixtures for shared data**
```python
@pytest.fixture
def sample_transcript():
    return {"segments": [...]}
```

✅ **Mock external dependencies**
```python
@patch("openai.OpenAI")
def test_with_mocked_api(mock_openai):
    # No real API calls in tests
```

✅ **Test error cases**
```python
def test_operation_raises_error_for_invalid_input(self):
    with pytest.raises(ModuleError):
        engine.operation(invalid_input)
```

### DON'T

❌ **Don't test multiple things in one test**
```python
def test_everything(self):  # BAD
    # Tests too many things
```

❌ **Don't use vague test names**
```python
def test_function(self):  # BAD - what about it?
```

❌ **Don't make real API calls**
```python
def test_openai_api(self):
    client = openai.OpenAI()  # BAD - no mocking
```

❌ **Don't depend on test order**
```python
# BAD - tests should be independent
def test_first(self):
    global_var = "value"

def test_second(self):
    assert global_var == "value"  # Fragile
```

❌ **Don't use print for debugging**
```python
def test_something(self):
    print("Debug info")  # BAD - use logging or pytest output
```

---

## Debugging Failed Tests

### Running Single Test with Details

```bash
# Run with full traceback
pytest tests/unit/test_core_export.py::test_specific -vv

# With output capture disabled
pytest tests/unit/test_core_export.py::test_specific -s

# With Python debugger
pytest tests/unit/test_core_export.py::test_specific --pdb
```

### Using pytest debugging

```python
def test_something():
    result = function_under_test()

    # Drop into debugger
    import pdb; pdb.set_trace()

    assert result == expected
```

### Viewing Test Output

```bash
# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Longer tracebacks
pytest --tb=long
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install -e ".[dev]"

    - name: Run tests
      run: |
        pytest tests/unit/ --cov=podx.core --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Additional Resources

- **[Core API Reference](./CORE_API.md)** - API documentation
- **[Architecture Guide](./ARCHITECTURE_V2.md)** - Design patterns
- **[Pytest Documentation](https://docs.pytest.org/)** - pytest reference
- **[unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)** - Mocking reference

---

## Questions & Support

For questions about testing:
- 📖 Read this guide
- 💬 Ask in GitHub Discussions
- 🐛 Report test issues on GitHub
