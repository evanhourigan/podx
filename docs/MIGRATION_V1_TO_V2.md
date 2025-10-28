# Migration Guide: v1.x → v2.0

This guide helps you migrate from PodX v1.x to v2.0. The v2.0 release includes a major architecture refactor that improves modularity, testability, and usability.

## Overview of Changes

### ✅ What's New in v2.0

1. **Clean Architecture**: Core business logic separated from CLI
2. **Python SDK**: Use PodX as a library in your code
3. **PodX Studio**: New interactive TUI application
4. **Better Testing**: 97% unit test coverage
5. **Improved Documentation**: Comprehensive API docs

### 🔄 What's Changed

1. **CLI Commands**: Same commands, cleaner implementation
2. **Import Paths**: New module structure (backward compatible)
3. **Configuration**: Enhanced config system
4. **Error Handling**: More specific error types

### ❌ What's Removed

1. **Interactive CLI flags**: Removed `--interactive` from individual commands (use `podx-studio` or `podx run --interactive` instead)

## Migration Steps

### 1. Update Installation

```bash
# Uninstall old version
pip uninstall podx

# Install v2.0
pip install podx[asr,llm,whisperx,notion]
```

### 2. CLI Commands (No Changes Required!)

All CLI commands work exactly as before:

```bash
# v1.x
podx-transcribe --input audio.wav --model base

# v2.0 - Same!
podx-transcribe --input audio.wav --model base
```

The CLI interface is **100% backward compatible**.

### 3. Python Imports

If you were importing from PodX modules directly, update your imports:

#### Old (v1.x):

```python
# ❌ v1.x imports (still work but deprecated)
from podx.transcribe import TranscriptionEngine
from podx.deepcast import DeepcastEngine
from podx.diarize import DiarizationEngine
```

#### New (v2.0):

```python
# ✅ v2.0 imports (recommended)
from podx import (
    TranscriptionEngine,
    DeepcastEngine,
    DiarizationEngine,
)

# Or use core modules directly
from podx.core.transcribe import TranscriptionEngine
from podx.core.deepcast import DeepcastEngine
from podx.core.diarize import DiarizationEngine
```

### 4. Error Handling

Error types are now more specific and located in core modules:

#### Old (v1.x):

```python
# ❌ v1.x errors
from podx.errors import PodxError
```

#### New (v2.0):

```python
# ✅ v2.0 errors - more specific
from podx import (
    TranscriptionError,
    DiarizationError,
    DeepcastError,
    FetchError,
    NotionError,
    YouTubeError,
    PodxError,  # Still available as base class
)

try:
    engine = TranscriptionEngine()
    result = engine.transcribe("audio.wav")
except TranscriptionError as e:
    print(f"Transcription failed: {e}")
```

### 5. Replace Interactive CLI

The `--interactive` flag has been removed from individual commands. Use `podx-studio` instead:

#### Old (v1.x):

```bash
# ❌ No longer supported
podx-transcribe --interactive
podx-deepcast --interactive
podx-diarize --interactive
```

#### New (v2.0):

```bash
# ✅ Use PodX Studio for interactive workflows
podx-studio

# Or use the orchestrator's interactive mode
podx run --interactive
```

### 6. Configuration

Configuration is enhanced in v2.0:

#### Old (v1.x):

```bash
# Environment variables only
export OPENAI_API_KEY="..."
export DEFAULT_ASR_MODEL="base"
```

#### New (v2.0):

```bash
# Environment variables (still supported)
export OPENAI_API_KEY="..."
export PODX_DEFAULT_ASR_MODEL="base"

# OR use config file (new!)
cat > ~/.podx/config.yaml <<EOF
default_asr_model: "base"
default_ai_model: "gpt-4.1"
default_compute: "int8"

notion:
  databases:
    main:
      db_id: "abc123"
EOF
```

## Detailed Breaking Changes

### 1. Module Structure

**Before (v1.x):**
```
podx/
├── transcribe.py    # CLI + logic mixed
├── deepcast.py      # CLI + logic mixed
├── diarize.py       # CLI + logic mixed
└── ...
```

**After (v2.0):**
```
podx/
├── core/            # Pure business logic
│   ├── transcribe.py
│   ├── deepcast.py
│   └── diarize.py
├── cli/             # CLI layer
│   ├── transcribe.py
│   ├── deepcast.py
│   └── diarize.py
└── studio/          # TUI application
    └── app.py
```

### 2. Engine Initialization

Engine initialization is the same, but now you can import from the top level:

**Before (v1.x):**
```python
from podx.transcribe import TranscriptionEngine

engine = TranscriptionEngine(
    model="base",
    compute_type="int8"
)
```

**After (v2.0):**
```python
# Simpler top-level import
from podx import TranscriptionEngine

engine = TranscriptionEngine(
    model="base",
    compute_type="int8"
)
```

### 3. Schema/Model Imports

Schemas can now be imported from the top level:

**Before (v1.x):**
```python
from podx.schemas import Transcript, AudioMeta
```

**After (v2.0):**
```python
# Still works the same way!
from podx.schemas import Transcript, AudioMeta

# Or from top level (new)
from podx import Transcript, AudioMeta
```

## Code Migration Examples

### Example 1: Transcription Script

**Before (v1.x):**
```python
from pathlib import Path
from podx.transcribe import TranscriptionEngine

def transcribe_file(audio_path: str):
    engine = TranscriptionEngine(model="base")
    result = engine.transcribe(Path(audio_path))
    return result

transcript = transcribe_file("audio.wav")
print(f"Segments: {len(transcript['segments'])}")
```

**After (v2.0):**
```python
from pathlib import Path
from podx import TranscriptionEngine  # Simpler import

def transcribe_file(audio_path: str):
    engine = TranscriptionEngine(model="base")
    result = engine.transcribe(Path(audio_path))
    return result

transcript = transcribe_file("audio.wav")
print(f"Segments: {len(transcript['segments'])}")
```

*Only the import changed!*

### Example 2: Full Pipeline

**Before (v1.x):**
```python
from podx.transcribe import TranscriptionEngine
from podx.diarize import DiarizationEngine
from podx.deepcast import DeepcastEngine

# Transcribe
trans_engine = TranscriptionEngine(model="base")
transcript = trans_engine.transcribe("audio.wav")

# Diarize
diar_engine = DiarizationEngine()
diarized = diar_engine.diarize("audio.wav", transcript)

# Analyze
deep_engine = DeepcastEngine(model="gpt-4.1")
analysis = deep_engine.analyze(diarized)
```

**After (v2.0):**
```python
from podx import (  # Cleaner imports from one place
    TranscriptionEngine,
    DiarizationEngine,
    DeepcastEngine,
)

# Transcribe
trans_engine = TranscriptionEngine(model="base")
transcript = trans_engine.transcribe("audio.wav")

# Diarize
diar_engine = DiarizationEngine()
diarized = diar_engine.diarize("audio.wav", transcript)

# Analyze
deep_engine = DeepcastEngine(model="gpt-4.1")
analysis = deep_engine.analyze(diarized)
```

*Only imports changed, logic is identical!*

### Example 3: Error Handling

**Before (v1.x):**
```python
from podx.transcribe import TranscriptionEngine
from podx.errors import PodxError

try:
    engine = TranscriptionEngine()
    result = engine.transcribe("audio.wav")
except PodxError as e:
    print(f"Error: {e}")
```

**After (v2.0):**
```python
from podx import TranscriptionEngine, TranscriptionError

try:
    engine = TranscriptionEngine()
    result = engine.transcribe("audio.wav")
except TranscriptionError as e:  # More specific!
    print(f"Transcription error: {e}")
```

## New Features to Try

### 1. PodX Studio

Launch the interactive TUI:

```bash
podx-studio
```

### 2. Python SDK

Use PodX as a library with clean imports:

```python
from podx import (
    TranscriptionEngine,
    DeepcastEngine,
    fetch_episode,
    YouTubeEngine,
)

# Everything you need from one import!
```

### 3. Improved Testing

v2.0 has 97% test coverage. Run tests to verify:

```bash
pytest tests/unit/test_core_*.py --cov=podx.core
```

## Compatibility Matrix

| Feature | v1.x | v2.0 |
|---------|------|------|
| CLI commands | ✅ | ✅ |
| Python imports | ✅ | ✅ (enhanced) |
| Config files | ❌ | ✅ |
| Interactive CLI | ✅ | ❌ (use Studio) |
| Python SDK | ⚠️ (limited) | ✅ (full) |
| Unit tests | ⚠️ (partial) | ✅ (97%) |
| TUI app | ❌ | ✅ |

## Getting Help

If you encounter issues during migration:

1. **Check the docs**: [QUICK_START.md](./QUICK_START.md), [CORE_API.md](./CORE_API.md)
2. **File an issue**: https://github.com/evanhourigan/podx/issues
3. **Review examples**: [API_EXAMPLES.md](./API_EXAMPLES.md)

## Summary

**Good news**: Most code will work without changes!

- ✅ All CLI commands are backward compatible
- ✅ Python imports have backward compatibility layer
- ✅ Configuration still uses environment variables
- ⚠️ Replace `--interactive` flags with `podx-studio`
- ✅ New SDK makes Python usage much cleaner

**Bottom line**: Update your imports to use the new SDK for the best experience, but your existing code will mostly work as-is.

---

**Questions?** Open an issue on GitHub or check the [Quick Start Guide](./QUICK_START.md).
