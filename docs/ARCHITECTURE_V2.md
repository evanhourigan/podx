# PodX v2.0 Architecture

This document explains the architectural design of PodX v2.0, focusing on the core/CLI separation pattern that enables better testability, reusability, and maintainability.

## Table of Contents

- [Overview](#overview)
- [Design Principles](#design-principles)
- [Core/CLI Separation](#corecli-separation)
- [Module Organization](#module-organization)
- [Data Flow](#data-flow)
- [Progress Callback Pattern](#progress-callback-pattern)
- [Error Handling Strategy](#error-handling-strategy)
- [Testing Architecture](#testing-architecture)
- [Migration Guide](#migration-guide)

---

## Overview

PodX v2.0 introduces a major architectural refactor that separates **business logic** from **UI concerns**. This "The iPhone Moment" redesign makes PodX simpler, more testable, and easier to integrate.

### Key Architectural Goals

1. **Testability** - Test business logic without UI mocking
2. **Reusability** - Use core engines in any context (CLI, API, GUI, scripts)
3. **Maintainability** - Clear separation of concerns
4. **Extensibility** - Easy to add new features and integrations

### Before & After

**v1.x Architecture:**
```
┌─────────────────────────────────────┐
│         CLI Commands                │
│  (Click + Business Logic Mixed)     │
│                                     │
│  • Heavy Click dependencies         │
│  • Difficult to test                │
│  • Hard to reuse logic              │
└─────────────────────────────────────┘
```

**v2.0 Architecture:**
```
┌─────────────────────────────────────┐
│         CLI Layer                   │
│  (podx.cli.* - Click UI)            │
│                                     │
│  • User interaction                 │
│  • Progress display                 │
│  • Error formatting                 │
└──────────────┬──────────────────────┘
               │
               ▼ Uses
┌─────────────────────────────────────┐
│         Core Layer                  │
│  (podx.core.* - Business Logic)     │
│                                     │
│  • Pure business logic              │
│  • No UI dependencies               │
│  • Fully testable                   │
│  • Reusable engines                 │
└─────────────────────────────────────┘
```

---

## Design Principles

### 1. Separation of Concerns

**Core modules** contain only business logic:
- No Click imports
- No direct terminal I/O
- No UI formatting
- Pure Python functions and classes

**CLI modules** handle user interaction:
- Click commands and options
- Rich terminal output
- Progress bars and formatting
- User prompts and confirmations

### 2. Dependency Inversion

Core modules don't know about CLI:
```python
# Core module (podx/core/transcribe.py)
class TranscribeEngine:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback  # Abstract callback

    def transcribe(self, audio_file):
        if self.progress_callback:
            self.progress_callback("Starting transcription...")
        # Business logic here
```

CLI depends on core:
```python
# CLI module (podx/cli/transcribe.py)
import click
from podx.core.transcribe import TranscribeEngine

@click.command()
def transcribe(audio_file):
    engine = TranscribeEngine(progress_callback=click.echo)
    result = engine.transcribe(audio_file)
    click.echo("Done!")
```

### 3. Interface Consistency

All engines follow the same pattern:
```python
class ModuleEngine:
    """Core business logic for [module purpose]."""

    def __init__(
        self,
        # Module-specific options
        option1: type = default,
        option2: type = default,
        # Standard across all engines
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.option1 = option1
        self.option2 = option2
        self.progress_callback = progress_callback

    def main_operation(self, input_data):
        """Primary operation of this engine."""
        if self.progress_callback:
            self.progress_callback("Starting operation...")

        # Business logic

        if self.progress_callback:
            self.progress_callback("Operation complete")

        return result
```

### 4. Explicit Over Implicit

Configuration and dependencies are explicit:
- No hidden globals
- No environment variable magic in core
- All options passed to constructors
- Clear error messages for missing dependencies

---

## Core/CLI Separation

### Directory Structure

```
podx/
├── core/                    # Pure business logic
│   ├── __init__.py
│   ├── transcode.py        # Audio conversion engine
│   ├── fetch.py            # Episode fetching engine
│   ├── preprocess.py       # Transcript preprocessing engine
│   ├── transcribe.py       # Speech-to-text engine
│   ├── diarize.py          # Speaker diarization engine
│   ├── deepcast.py         # AI analysis engine
│   ├── notion.py           # Notion publishing engine
│   ├── export.py           # Format export engine
│   └── youtube.py          # YouTube download engine
│
└── cli/                     # CLI wrappers (future)
    ├── __init__.py
    ├── transcode.py        # podx-transcode command
    ├── fetch.py            # podx-fetch command
    ├── preprocess.py       # podx-preprocess command
    ├── transcribe.py       # podx-transcribe command
    ├── diarize.py          # podx-diarize command
    ├── deepcast.py         # podx-deepcast command
    ├── notion.py           # podx-notion command
    ├── export.py           # podx-export command
    └── youtube.py          # podx-youtube command
```

### Core Module Template

```python
"""Core business logic for [module name].

This module provides pure business logic without UI dependencies.
It can be used directly in Python code, APIs, or wrapped by CLI commands.
"""

from typing import Any, Callable, Dict, Optional


class [Module]Error(Exception):
    """Raised when [module] operations fail."""
    pass


class [Module]Engine:
    """Core business logic for [module purpose].

    This class contains no UI dependencies and can be used in any context.

    Args:
        option1: Description of option 1
        option2: Description of option 2
        progress_callback: Optional callback for progress updates.
            Called with status messages (str) during processing.

    Example:
        >>> engine = [Module]Engine(progress_callback=print)
        >>> result = engine.main_operation(input_data)
    """

    def __init__(
        self,
        option1: type = default,
        option2: type = default,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.option1 = option1
        self.option2 = option2
        self.progress_callback = progress_callback

    def _progress(self, message: str):
        """Internal helper to call progress callback."""
        if self.progress_callback:
            self.progress_callback(message)

    def main_operation(self, input_data: Any) -> Dict[str, Any]:
        """Main operation description.

        Args:
            input_data: Description of input

        Returns:
            Dict with results

        Raises:
            [Module]Error: If operation fails
        """
        self._progress("Starting operation...")

        try:
            # Business logic here
            result = self._do_work(input_data)
        except Exception as e:
            raise [Module]Error(f"Operation failed: {e}") from e

        self._progress("Operation complete")
        return result

    def _do_work(self, input_data):
        """Internal implementation."""
        # Implementation details
        pass
```

### CLI Wrapper Template

```python
"""CLI command for [module name].

This module wraps core.[module] business logic with Click UI.
"""

import click
from pathlib import Path

from podx.core.[module] import [Module]Engine, [Module]Error


@click.command()
@click.option("--option1", help="Option 1 description")
@click.option("--option2", help="Option 2 description")
def [command](option1, option2):
    """[Command description].

    Example usage:

        podx-[command] --option1 value1 --option2 value2
    """
    try:
        # Initialize engine with progress callback
        engine = [Module]Engine(
            option1=option1,
            option2=option2,
            progress_callback=lambda msg: click.echo(f"[{command}] {msg}")
        )

        # Execute operation
        result = engine.main_operation(input_data)

        # Display results
        click.echo(f"Success: {result}")

    except [Module]Error as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        raise


if __name__ == "__main__":
    [command]()
```

---

## Module Organization

### Core Modules

Each core module follows this structure:

```python
# podx/core/module.py

"""Module docstring explaining purpose and usage."""

from typing import Any, Callable, Dict, Optional


# 1. Custom exception
class ModuleError(Exception):
    """Raised when module operations fail."""
    pass


# 2. Main engine class
class ModuleEngine:
    """Core business logic class.

    Contains all business logic without UI dependencies.
    """

    def __init__(self, ..., progress_callback=None):
        """Initialize engine with options."""
        pass

    def main_operation(self, input_data):
        """Primary public method."""
        pass

    def _internal_helper(self, data):
        """Private helper methods prefixed with _."""
        pass


# 3. Utility functions (if needed)
def utility_function(data):
    """Pure utility functions that don't need state."""
    pass


# 4. Public API export
__all__ = ["ModuleEngine", "ModuleError", "utility_function"]
```

### Typical Module Sizes

Based on actual v2.0 modules:

| Module | LOC | Classes | Functions | Complexity |
|--------|-----|---------|-----------|------------|
| export | ~300 | 1 | 5 | Low |
| youtube | ~200 | 1 | 3 | Low |
| notion | ~400 | 1 | 8 | Medium |
| diarize | ~250 | 1 | 4 | Medium |
| deepcast | ~500 | 1 | 10 | High |
| transcribe | ~350 | 1 | 6 | Medium |

**Guidelines:**
- Keep modules focused (single responsibility)
- Aim for < 500 LOC per module
- Extract utilities if module grows too large
- Consider splitting if complexity is high

---

## Data Flow

### Pipeline Architecture

PodX processes podcasts through a series of transformations:

```
Episode URL
    ↓
┌───────────────┐
│  FETCH        │ ← FetchEngine
└───────┬───────┘
        │ {episode_meta, audio_file}
        ↓
┌───────────────┐
│  TRANSCODE    │ ← TranscodeEngine
└───────┬───────┘
        │ {audio_file: wav16}
        ↓
┌───────────────┐
│  TRANSCRIBE   │ ← TranscribeEngine
└───────┬───────┘
        │ {segments: [{text, start, end}, ...]}
        ↓
    ┌───┴───┐
    │       │
    ↓       ↓
┌────────┐ ┌────────┐
│DIARIZE │ │PREPROC │ ← DiarizeEngine, PreprocessEngine
└───┬────┘ └───┬────┘
    │          │
    │ {segments: [{speaker, words, ...}, ...]}
    │          │
    └────┬─────┘
         ↓
┌───────────────┐
│  DEEPCAST     │ ← DeepcastEngine
└───────┬───────┘
        │ {markdown, insights_json}
        ↓
    ┌───┴───┐
    │       │
    ↓       ↓
┌────────┐ ┌────────┐
│ EXPORT │ │ NOTION │ ← ExportEngine, NotionEngine
└────────┘ └────────┘
  {files}   {page_url}
```

### Data Format Conventions

**Episode Metadata:**
```python
{
    "title": str,
    "date": str,  # YYYY-MM-DD
    "show": str,
    "audio_file": str,  # Path to audio file
    "duration": float,  # Seconds
    "url": str,  # Original URL
}
```

**Transcript Format:**
```python
{
    "segments": [
        {
            "text": str,
            "start": float,  # Seconds
            "end": float,    # Seconds
            "speaker": str,  # Optional, from diarization
            "words": [       # Optional, word-level timing
                {
                    "word": str,
                    "start": float,
                    "end": float,
                }
            ]
        }
    ]
}
```

**Analysis Format:**
```python
{
    "markdown": str,  # Formatted analysis
    "insights": {
        "title": str,
        "summary": str,
        "key_points": [str],
        "quotes": [{"speaker": str, "quote": str, "context": str}],
        "topics": [str],
        "actionable_takeaways": [str],
    }
}
```

---

## Progress Callback Pattern

### Why Callbacks?

Progress callbacks enable UI integration without coupling:

```python
# Core module doesn't know about Click
class Engine:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback

    def process(self):
        if self.progress_callback:
            self.progress_callback("Processing...")
```

### Callback Implementations

**Simple logging:**
```python
engine = Engine(progress_callback=print)
```

**Click CLI:**
```python
engine = Engine(progress_callback=click.echo)
```

**Rich progress bar:**
```python
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("Processing", total=100)

    def callback(msg):
        progress.console.log(msg)
        progress.advance(task, 1)

    engine = Engine(progress_callback=callback)
```

**Custom logger:**
```python
import logging
logger = logging.getLogger(__name__)

engine = Engine(progress_callback=logger.info)
```

**Silent mode:**
```python
engine = Engine(progress_callback=None)  # No output
```

### Best Practices

1. **Keep messages concise** - One line status updates
2. **Use present continuous** - "Downloading...", not "Download"
3. **Include context when useful** - "Transcribing segment 5/10"
4. **Don't overuse** - Only for significant milestones
5. **Make optional** - Always check `if self.progress_callback`

---

## Error Handling Strategy

### Exception Hierarchy

```python
# Base exception for module
class ModuleError(Exception):
    """Base exception for module operations."""
    pass

# Specific exceptions if needed
class ModuleValidationError(ModuleError):
    """Raised when input validation fails."""
    pass

class ModuleAPIError(ModuleError):
    """Raised when external API calls fail."""
    pass
```

### Error Handling Pattern

**In core modules:**
```python
def process(self, data):
    # Validate inputs
    if not data:
        raise ModuleError("Input data is required")

    # Catch and wrap external errors
    try:
        result = external_api.call(data)
    except ExternalError as e:
        raise ModuleAPIError(f"API call failed: {e}") from e

    return result
```

**In CLI wrappers:**
```python
@click.command()
def command():
    try:
        engine = Engine()
        result = engine.process(data)
        click.echo("Success!")
    except ModuleError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        raise
```

### Error Message Guidelines

1. **Be specific** - "Audio file not found: /path/to/file.wav"
2. **Include context** - "Transcription failed at segment 5: ..."
3. **Suggest solutions** - "API key not found. Set OPENAI_API_KEY environment variable"
4. **Chain exceptions** - Use `raise NewError(...) from original_error`

---

## Testing Architecture

### Test Organization

```
tests/
├── unit/                    # Unit tests for core modules
│   ├── test_core_transcode.py
│   ├── test_core_fetch.py
│   ├── test_core_preprocess.py
│   ├── test_core_transcribe.py
│   ├── test_core_diarize.py
│   ├── test_core_deepcast.py
│   ├── test_core_notion.py
│   ├── test_core_export.py
│   └── test_core_youtube.py
│
└── integration/             # Integration tests
    ├── test_pipeline.py
    └── test_end_to_end.py
```

### Unit Test Pattern

Pure unit tests with no UI dependencies:

```python
"""Unit tests for core.module."""

import pytest
from unittest.mock import MagicMock, patch
from podx.core.module import ModuleEngine, ModuleError


class TestModuleEngine:
    """Test ModuleEngine class."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        engine = ModuleEngine()
        assert engine.option1 == expected_default
        assert engine.progress_callback is None

    def test_init_with_callback(self):
        """Test initialization with progress callback."""
        callback = lambda msg: None
        engine = ModuleEngine(progress_callback=callback)
        assert engine.progress_callback is callback

    def test_operation_success(self):
        """Test successful operation."""
        engine = ModuleEngine()
        result = engine.operation(test_input)
        assert result["status"] == "success"

    def test_operation_with_callback(self):
        """Test operation calls progress callback."""
        messages = []
        engine = ModuleEngine(progress_callback=messages.append)
        engine.operation(test_input)
        assert "Starting" in messages[0]
        assert "Complete" in messages[-1]

    def test_operation_invalid_input(self):
        """Test operation with invalid input."""
        engine = ModuleEngine()
        with pytest.raises(ModuleError, match="Invalid input"):
            engine.operation(invalid_input)

    def test_operation_external_failure(self):
        """Test handling of external API failures."""
        with patch("module.external_api") as mock_api:
            mock_api.call.side_effect = Exception("API error")
            engine = ModuleEngine()
            with pytest.raises(ModuleError, match="API call failed"):
                engine.operation(test_input)
```

### Test Coverage

Target coverage for core modules:
- **95-100%** - Core business logic
- **80-95%** - Error handling paths
- **70-80%** - Edge cases

```bash
# Run tests with coverage
pytest tests/unit/test_core_*.py --cov=podx.core --cov-report=html

# View coverage report
open htmlcov/index.html
```

---

## Migration Guide

### From v1.x to v2.0

If you have custom code using v1.x CLI functions:

**v1.x (Direct CLI usage):**
```python
from podx.transcribe import transcribe_command
# Can't easily use without Click context
```

**v2.0 (Core module usage):**
```python
from podx.core.transcribe import TranscribeEngine

engine = TranscribeEngine(model="large-v3-turbo")
result = engine.transcribe("audio.wav")
```

### Creating New Modules

To add a new module to PodX:

1. **Create core module:** `podx/core/newmodule.py`
```python
"""Core business logic for new module."""

class NewModuleError(Exception):
    pass

class NewModuleEngine:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback

    def process(self, input_data):
        # Implementation
        pass
```

2. **Create tests:** `tests/unit/test_core_newmodule.py`
```python
"""Unit tests for core.newmodule."""

def test_basic_operation():
    engine = NewModuleEngine()
    result = engine.process(test_data)
    assert result["status"] == "success"
```

3. **Create CLI wrapper:** `podx/cli/newmodule.py` (optional)
```python
"""CLI wrapper for new module."""

@click.command()
def newmodule_command():
    engine = NewModuleEngine(progress_callback=click.echo)
    # ...
```

4. **Update documentation:** Add to `docs/CORE_API.md`

---

## Benefits Summary

### For Developers

- ✅ **Easy testing** - No UI mocking needed
- ✅ **Clear structure** - Business logic separated from UI
- ✅ **Type safe** - Full type hints throughout
- ✅ **Documented** - Comprehensive docstrings and examples

### For Users

- ✅ **Programmatic API** - Use PodX in Python scripts
- ✅ **Custom integrations** - Build on core engines
- ✅ **Better errors** - Clear, actionable error messages
- ✅ **Consistent behavior** - Uniform interface across modules

### For Contributors

- ✅ **Easy to extend** - Clear patterns to follow
- ✅ **Well tested** - 95%+ test coverage
- ✅ **Good docs** - Examples and API references
- ✅ **Clean code** - Consistent style and structure

---

## Future Directions

### Planned Enhancements

1. **REST API** - HTTP API wrapping core engines
2. **Web UI** - Browser-based interface using core logic
3. **Python SDK** - Official SDK package for programmatic use
4. **Async support** - Async/await versions of engines
5. **Streaming** - Real-time processing with progress streams

### Extensibility Points

The architecture enables:
- Custom storage backends
- Alternative UI frameworks
- Third-party integrations
- Cloud deployment options
- Microservice architecture

---

## Additional Resources

- **[Core API Reference](./CORE_API.md)** - Complete API documentation
- **[Testing Guide](./TESTING.md)** - Testing patterns and best practices
- **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute
- **[Plugin System](./PLUGINS.md)** - Creating custom plugins

---

## Questions & Support

For questions about the architecture:
- 📖 Read the documentation
- 💬 Ask in GitHub Discussions
- 🐛 Report issues on GitHub
