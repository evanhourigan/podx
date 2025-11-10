# Migration Guide: v0.x → v1.0

This guide helps you upgrade from podx v0.x (alpha) to v1.0 (stable).

## Quick Migration Checklist

- [ ] Update `pyproject.toml` or `requirements.txt` to `podx==1.0.0`
- [ ] Update import paths (`podx.schemas` → `podx.domain`)
- [ ] Replace string literals with type-safe enums
- [ ] Update Pydantic v1 API calls to v2
- [ ] Update configuration files if using workflows
- [ ] Run tests to verify compatibility
- [ ] Review new features (plugins, async API, state management)

---

## Breaking Changes

### 1. Pydantic v2 Migration

**Impact**: All data models now use Pydantic v2 API

#### Model Instantiation

```python
# v0.x (Pydantic v1)
from podx.schemas import Transcript
transcript = Transcript.parse_obj(data)
transcript_dict = transcript.dict()
schema = Transcript.schema()

# v1.0 (Pydantic v2)
from podx.domain import Transcript
transcript = Transcript.model_validate(data)
transcript_dict = transcript.model_dump()
schema = Transcript.model_json_schema()
```

#### Validators

```python
# v0.x (Pydantic v1)
from pydantic import BaseModel, validator

class MyModel(BaseModel):
    value: int

    @validator("value")
    def check_value(cls, v):
        if v < 0:
            raise ValueError("must be positive")
        return v

# v1.0 (Pydantic v2)
from pydantic import BaseModel, field_validator

class MyModel(BaseModel):
    value: int

    @field_validator("value")
    @classmethod
    def check_value(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be positive")
        return v
```

#### Configuration

```python
# v0.x (Pydantic v1)
class MyModel(BaseModel):
    class Config:
        extra = "forbid"

# v1.0 (Pydantic v2)
from pydantic import ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

---

### 2. Import Path Changes

**Impact**: Models moved from `podx.schemas` to `podx.domain`

```python
# v0.x
from podx.schemas import (
    EpisodeMeta,
    AudioMeta,
    Transcript,
    Segment,
    DeepcastBrief,
)

# v1.0 (recommended)
from podx.domain import (
    EpisodeMeta,
    AudioMeta,
    Transcript,
    Segment,
    DeepcastBrief,
)

# v1.0 (backward compatible, deprecated in v1.1)
from podx.schemas import (
    EpisodeMeta,  # Still works via re-export
    AudioMeta,
    Transcript,
    Segment,
    DeepcastBrief,
)
```

**Migration Strategy**:
- **Preferred**: Update all imports to `podx.domain`
- **Fallback**: Keep using `podx.schemas` (works in v1.0, removed in v1.1)
- **Automated**: Use find/replace: `from podx.schemas import` → `from podx.domain import`

---

### 3. Type-Safe Enums

**Impact**: String literals replaced with type-safe enums

#### ASR Preset

```python
# v0.x
from podx.api import PodxClient
client = PodxClient()
result = client.transcribe("audio.mp3", preset="precision")

# v1.0
from podx.api import PodxClient
from podx.domain import ASRPreset

client = PodxClient()
result = client.transcribe("audio.mp3", preset=ASRPreset.PRECISION)
```

#### ASR Provider

```python
# v0.x
config = {"provider": "openai", "model": "whisper-1"}

# v1.0
from podx.domain import ASRProvider
config = {"provider": ASRProvider.OPENAI, "model": "whisper-1"}
```

#### Audio Format

```python
# v0.x
transcode(input_path, output_path, fmt="wav16")

# v1.0
from podx.domain import AudioFormat
transcode(input_path, output_path, fmt=AudioFormat.WAV16)
```

#### Analysis Type

```python
# v0.x
run_deepcast(transcript, analysis_type="brief")

# v1.0
from podx.domain import AnalysisType
run_deepcast(transcript, analysis_type=AnalysisType.BRIEF)
```

**All Enums**:
```python
from podx.domain import (
    PipelineStep,    # FETCH, TRANSCODE, TRANSCRIBE, ALIGN, DIARIZE, etc.
    AnalysisType,    # BRIEF, SUMMARY, OUTLINE, QUOTES, THEMES
    ASRProvider,     # AUTO, LOCAL, OPENAI, HF
    ASRPreset,       # BALANCED, PRECISION, RECALL
    AudioFormat,     # WAV16, MP3, AAC
)
```

**Migration Strategy**:
- Import enums from `podx.domain`
- Replace string literals with enum members
- Use IDE autocomplete for enum values

---

### 4. Configuration Schema Changes

#### PipelineConfig (NEW)

```python
# v0.x (no PipelineConfig, used dict)
config = {
    "show": "My Podcast",
    "align": True,
    "deepcast": True,
}

# v1.0 (type-safe PipelineConfig)
from podx.domain import PipelineConfig, ASRPreset

config = PipelineConfig(
    show="My Podcast",
    align=True,
    deepcast=True,
    preset=ASRPreset.PRECISION,
)

# Validate before use
config.model_validate(config.model_dump())
```

#### Workflow Presets

```python
# v0.x (returned dict)
from podx.workflow_presets import get_workflow
config = get_workflow("comprehensive")  # dict

# v1.0 (returns PipelineConfig object)
from podx.domain import PipelineConfig

config = PipelineConfig.from_workflow("comprehensive")  # PipelineConfig
print(config.align)  # True
print(config.deepcast)  # True
```

---

## New Features (Non-Breaking)

### 1. High-Level API (`podx.api`)

```python
# v1.0 NEW: PodxClient for programmatic access
from podx.api import PodxClient, ClientConfig
from podx.domain import PipelineConfig, ASRPreset

# Configure client
config = ClientConfig(
    default_model="large-v3-turbo",
    cache_enabled=True,
)
client = PodxClient(config=config)

# Simple transcription
result = client.transcribe("audio.mp3")
print(result.transcript_path)

# Full pipeline
pipeline_config = PipelineConfig(
    show="My Podcast",
    preset=ASRPreset.PRECISION,
    align=True,
    deepcast=True,
)
result = client.run(pipeline_config)
print(result.deepcast_paths)
```

### 2. Async/Await Support

```python
# v1.0 NEW: AsyncPipelineService for concurrent execution
import asyncio
from podx.services import AsyncPipelineService, PipelineConfig

async def process_podcasts():
    configs = [
        PipelineConfig(show=f"Podcast {i}", deepcast=True)
        for i in range(10)
    ]

    # Process up to 3 podcasts concurrently
    results = await AsyncPipelineService.process_batch(
        configs,
        max_concurrent=3,
    )

    for result in results:
        print(f"Processed: {result.transcript_path}")

# Run async code
asyncio.run(process_podcasts())
```

### 3. State Management & Resume

```python
# v1.0 NEW: Automatic resume from existing artifacts
from podx.state import RunState, ArtifactDetector
from pathlib import Path

working_dir = Path("/path/to/episode")

# Detect existing artifacts
detector = ArtifactDetector(working_dir)
completed_steps = detector.detect_completed_steps()

# Load or create run state
state = RunState.load(working_dir)
if state.is_completed(PipelineStep.TRANSCRIBE):
    print("Transcription already done, skipping...")

# Mark step as completed
state.mark_completed(PipelineStep.TRANSCRIBE)
state.save()
```

### 4. Plugin System

```python
# v1.0 NEW: Extensible plugin system
from podx.plugins import PluginManager, PluginType

manager = PluginManager()
manager.discover_plugins()

# Get available plugins
plugins = manager.get_available_plugins(PluginType.SOURCE)
for name, metadata in plugins.items():
    print(f"{name}: {metadata.description}")

# Execute plugin
result = manager.execute_plugin(
    "youtube-source",
    "fetch_episode",
    query="https://youtube.com/watch?v=..."
)
```

---

## Dependency Updates

### Required Version Bumps

Update your `requirements.txt` or `pyproject.toml`:

```toml
# v0.x
pydantic>=2.0.0
structlog>=24.1.0
openai>=1.40.0

# v1.0 (pinned for stability)
pydantic~=2.12.0
structlog~=25.4.0
openai~=2.2.0
```

### Install v1.0

```bash
# Upgrade podx
pip install --upgrade podx==1.0.0

# Or with extras
pip install --upgrade podx[asr,llm,notion]==1.0.0

# Verify version
podx --version  # Should show 1.0.0
```

---

## CLI Changes

### New Commands

```bash
# v1.0 NEW: Unified orchestration
podx run --show "My Podcast" --deepcast

# v1.0 NEW: Plugin management
podx-list plugins
```

### Updated Flags

```bash
# v0.x
podx-transcribe --preset precision

# v1.0 (same, but enum-backed)
podx-transcribe --preset precision  # Still works!
```

**No CLI breaking changes** - all existing scripts continue to work.

---

## Testing Migration

### Update Test Imports

```python
# v0.x
from podx.schemas import Transcript

def test_transcript_parsing():
    data = {"language": "en", "text": "Test", "segments": []}
    transcript = Transcript.parse_obj(data)
    assert transcript.language == "en"

# v1.0
from podx.domain import Transcript

def test_transcript_parsing():
    data = {"language": "en", "text": "Test", "segments": []}
    transcript = Transcript.model_validate(data)
    assert transcript.language == "en"
```

### Update Mocks

```python
# v0.x
from unittest.mock import Mock

mock_config = Mock()
mock_config.preset = "precision"

# v1.0
from unittest.mock import Mock
from podx.domain import ASRPreset

mock_config = Mock()
mock_config.preset = ASRPreset.PRECISION
```

---

## Gradual Migration Strategy

### Phase 1: Update Dependencies (1 hour)
1. Update `pyproject.toml` to `podx==1.0.0`
2. Run `pip install --upgrade podx==1.0.0`
3. Run existing tests - note Pydantic deprecation warnings

### Phase 2: Fix Pydantic API (2-4 hours)
1. Find/replace: `.parse_obj(` → `.model_validate(`
2. Find/replace: `.dict(` → `.model_dump(`
3. Find/replace: `@validator` → `@field_validator`
4. Add `@classmethod` to field validators
5. Run tests, fix type errors

### Phase 3: Update Imports (1 hour)
1. Find/replace: `from podx.schemas import` → `from podx.domain import`
2. Run tests, verify no import errors

### Phase 4: Add Enums (2-4 hours)
1. Import enums: `from podx.domain import ASRPreset, ASRProvider, etc.`
2. Replace string literals with enum members
3. Use IDE autocomplete to discover enum values
4. Run tests, fix type errors

### Phase 5: Adopt New Features (optional)
1. Try `PodxClient` for high-level API
2. Experiment with async API for concurrent processing
3. Use plugin system for custom integrations

**Total Time**: 6-10 hours for typical codebase

---

## Troubleshooting

### Pydantic ValidationError

**Error**:
```python
pydantic_core._pydantic_core.ValidationError: 1 validation error for Transcript
audio_path
  Value error, Audio file not found: /path/to/audio.mp3
```

**Solution**:
```python
# v1.0 validates that audio files exist
# Either create the file or pass None/omit the field

# Option 1: Create dummy file (tests)
audio_file = tmp_path / "audio.mp3"
audio_file.write_bytes(b"fake audio")

# Option 2: Don't provide audio_path
transcript = Transcript(language="en", text="Test", segments=[])
```

### Enum Type Errors

**Error**:
```
TypeError: expected ASRPreset but got str
```

**Solution**:
```python
# Don't use strings
preset = "precision"  # Wrong

# Use enum members
from podx.domain import ASRPreset
preset = ASRPreset.PRECISION  # Correct
```

### Import Errors

**Error**:
```
ImportError: cannot import name 'PipelineConfig' from 'podx.schemas'
```

**Solution**:
```python
# Use new import path
from podx.domain import PipelineConfig  # Correct
```

---

## Getting Help

- **GitHub Issues**: https://github.com/yourusername/podx/issues
- **Discussions**: https://github.com/yourusername/podx/discussions
- **Security**: See `SECURITY.md` for vulnerability reporting

---

## Rollback Plan

If migration fails, rollback to v0.x:

```bash
# Rollback to last working version
pip install podx==0.2.0a1

# Restore old code
git checkout previous-version

# Verify tests pass
pytest
```

---

**Migration completed?** Check out `CHANGELOG.md` to see all v1.0 improvements!
