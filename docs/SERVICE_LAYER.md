# Service Layer Architecture

This document describes the service layer architecture introduced in Phase 4 of the refactoring plan.

## Overview

The service layer separates business logic from CLI presentation concerns, making the codebase more testable, maintainable, and composable. The architecture follows clean architecture principles with clear separation of concerns.

## Package Structure

```
podx/
├── services/               # Business logic and orchestration
│   ├── __init__.py
│   ├── command_builder.py  # Fluent command construction
│   ├── step_executor.py    # Individual step execution
│   └── pipeline_service.py # High-level orchestration
├── utils/                  # Shared utilities
│   ├── __init__.py
│   └── workflow_presets.py # Fidelity/workflow mappings
├── domain/                 # Domain models and enums (Phase 1)
├── state/                  # State management (Phase 2)
└── ui/                     # UI components (Phase 3)
```

## Core Components

### 1. CommandBuilder (`services/command_builder.py`)

**Purpose**: Fluent interface for constructing CLI commands

**Key Methods**:
- `add_option(flag, value)` - Add option with value
- `add_flag(flag)` - Add boolean flag
- `add_options(**kwargs)` - Add multiple options from keyword args
- `build()` - Return final command list

**Example**:
```python
cmd = (CommandBuilder("podx-fetch")
       .add_option("--show", "The Podcast")
       .add_option("--date", "2024-10-02")
       .add_flag("--interactive")
       .build())
# Returns: ['podx-fetch', '--show', 'The Podcast', '--date', '2024-10-02', '--interactive']
```

**Benefits**:
- Type-safe command construction
- Automatic null value filtering
- Readable and chainable API
- Easy to test

### 2. StepExecutor (`services/step_executor.py`)

**Purpose**: Execute individual pipeline steps via subprocess commands

**Key Methods**:
- `fetch()` - Fetch episode metadata from RSS/YouTube
- `transcode()` - Convert audio to target format
- `transcribe()` - Generate transcript with ASR
- `align()` - Word-level alignment with WhisperX
- `diarize()` - Speaker identification
- `preprocess()` - Clean and restore transcript
- `deepcast()` - AI-powered analysis
- `export()` - Convert to TXT/SRT/VTT/MD formats
- `notion()` - Upload to Notion database

**Example**:
```python
executor = StepExecutor(verbose=True)

# Fetch episode
meta = executor.fetch(show="My Podcast", date="2024-10-01")

# Transcode audio
audio = executor.transcode(meta=meta, fmt="wav16", outdir=Path("./output"))

# Transcribe
transcript = executor.transcribe(audio=audio, model="large-v3", preset="balanced")

# Align
aligned = executor.align(transcript=transcript)
```

**Benefits**:
- Encapsulates subprocess execution logic
- Handles JSON I/O automatically
- Provides typed interfaces for each step
- Centralizes error handling
- Reusable across different orchestrators

### 3. PipelineService (`services/pipeline_service.py`)

**Purpose**: High-level pipeline orchestration with state management

**Key Classes**:

#### `PipelineConfig`
Dataclass holding all pipeline configuration:
- Source settings (show, rss_url, youtube_url, date, etc.)
- Audio settings (fmt)
- Transcription settings (model, compute, asr_provider, preset)
- Pipeline flags (align, diarize, preprocess, restore, deepcast, dual)
- Deepcast settings (model, temperature, analysis_type)
- Notion settings (database_id, property names)
- Execution flags (verbose, clean, no_keep_audio)

#### `PipelineResult`
Dataclass holding execution results:
- `workdir` - Working directory path
- `steps_completed` - List of completed step names
- `artifacts` - Dictionary mapping artifact names to file paths
- `duration` - Total execution time
- `errors` - List of error messages

#### `PipelineService`
Main orchestration service:
- `execute()` - Run the complete pipeline
- Private methods for each step (e.g., `_execute_fetch()`, `_execute_transcribe()`)

**Example**:
```python
from podx.services import PipelineConfig, PipelineService

# Create configuration
config = PipelineConfig(
    show="My Podcast",
    date="2024-10-01",
    align=True,
    deepcast=True,
    deepcast_model="gpt-4",
)

# Execute pipeline
service = PipelineService(config)
result = service.execute(
    skip_completed=True,
    progress_callback=lambda step, status: print(f"{step}: {status}")
)

# Access results
print(f"Completed in {result.duration:.1f}s")
print(f"Artifacts: {result.artifacts}")
```

**Benefits**:
- Clean separation of business logic from CLI
- Testable without click/CLI dependencies
- Supports progress callbacks for UI integration
- Handles artifact detection and step resumption
- Can be used programmatically or from CLI
- Easy to extend with new steps

### 4. Workflow Presets (`utils/workflow_presets.py`)

**Purpose**: Apply fidelity and workflow preset mappings

**Key Functions**:

#### `apply_fidelity_preset(fidelity, current_preset, interactive)`
Maps fidelity level (1-5) to pipeline flags:
- **Fidelity 1**: Deepcast only (fastest)
- **Fidelity 2**: Recall + preprocess + restore + deepcast
- **Fidelity 3**: Precision + preprocess + restore + deepcast
- **Fidelity 4**: Balanced + preprocess + restore + deepcast (recommended)
- **Fidelity 5**: Dual QA (precision + recall) + preprocess + restore (best quality)

#### `apply_workflow_preset(workflow)`
Maps workflow name to pipeline flags:
- **quick**: Minimal processing (transcribe only)
- **analyze**: Transcribe + align + deepcast + markdown
- **publish**: Transcribe + align + deepcast + markdown + Notion

**Example**:
```python
from podx.utils import apply_fidelity_preset, apply_workflow_preset

# Apply fidelity preset
flags = apply_fidelity_preset("4", current_preset="balanced", interactive=False)
# Returns: {
#     "preset": "balanced",
#     "preprocess": True,
#     "restore": True,
#     "deepcast": True,
#     "dual": False
# }

# Apply workflow preset
flags = apply_workflow_preset("publish")
# Returns: {
#     "align": True,
#     "diarize": False,
#     "deepcast": True,
#     "extract_markdown": True,
#     "notion": True
# }
```

## Integration with Existing Code

### Phase 4 Goals

The service layer was created to:
1. **Extract business logic** from the 1,571-line `orchestrate.py::run()` function
2. **Enable programmatic usage** without CLI dependencies
3. **Improve testability** by separating concerns
4. **Support multiple frontends** (CLI, API, web UI, etc.)

### Current State

Phase 4 has established the **foundation** for service layer extraction:
- ✅ Created `services/` package with CommandBuilder, StepExecutor, PipelineService
- ✅ Created `utils/` package with workflow preset logic
- ✅ All components are fully typed and documented
- ✅ Tests confirm no breaking changes

### Future Work

The next steps would involve:
1. **Refactor orchestrate.py** to use PipelineService internally
2. **Extract interactive selection UI** to separate module
3. **Migrate dual mode logic** to PipelineService
4. **Add comprehensive unit tests** for service layer
5. **Create integration examples** for programmatic usage

## Benefits of Service Layer

### 1. Testability
```python
# Easy to test without subprocess execution
def test_pipeline_config():
    config = PipelineConfig(show="Test", align=True)
    assert config.align == True
    assert config.deepcast == False
```

### 2. Reusability
```python
# Reuse executor across different contexts
executor = StepExecutor(verbose=False)
meta1 = executor.fetch(show="Podcast A")
meta2 = executor.fetch(show="Podcast B")
```

### 3. Composability
```python
# Compose pipeline steps programmatically
executor = StepExecutor()
meta = executor.fetch(show="My Podcast")
audio = executor.transcode(meta, fmt="wav16")
transcript = executor.transcribe(audio, model="large-v3")
aligned = executor.align(transcript)
```

### 4. Extensibility
```python
# Easy to add custom steps or modify behavior
class CustomStepExecutor(StepExecutor):
    def custom_step(self, input_data):
        # Add custom processing
        return self._run(["my-custom-tool"], stdin_payload=input_data)
```

### 5. Multiple Frontends
```python
# CLI frontend (current)
@click.command()
def run_cli(...):
    config = PipelineConfig(...)
    service = PipelineService(config)
    result = service.execute()

# API frontend (future)
@app.post("/pipeline/run")
def run_api(request: PipelineRequest):
    config = PipelineConfig(**request.dict())
    service = PipelineService(config)
    result = service.execute()
    return result.to_dict()

# Web UI frontend (future)
def run_web_ui(form_data):
    config = PipelineConfig(**form_data)
    service = PipelineService(config)
    result = service.execute(progress_callback=update_progress_bar)
```

## Design Principles

### 1. Separation of Concerns
- **CLI layer** (`orchestrate.py`): Click decorators, user interaction, progress display
- **Service layer** (`services/`): Business logic, orchestration, step execution
- **Domain layer** (`domain/`): Models, enums, constants
- **State layer** (`state/`): Artifact detection, state management
- **UI layer** (`ui/`): Reusable UI components

### 2. Dependency Injection
- StepExecutor can be injected into PipelineService
- Enables mocking for tests
- Supports custom implementations

### 3. Immutable Configuration
- PipelineConfig is a dataclass (immutable by convention)
- Configuration validated at construction time
- No hidden state changes during execution

### 4. Type Safety
- Full type hints throughout service layer
- Mypy-compatible
- IDE autocomplete support

### 5. Error Handling
- ValidationError for configuration errors
- Proper error propagation
- Errors collected in PipelineResult

## Usage Patterns

### Pattern 1: Simple Pipeline Execution
```python
from podx.services import PipelineConfig, PipelineService

config = PipelineConfig(show="My Podcast", align=True, deepcast=True)
service = PipelineService(config)
result = service.execute()
print(f"Artifacts: {result.artifacts}")
```

### Pattern 2: Custom Progress Tracking
```python
def progress_callback(step_name, status):
    if status == "started":
        print(f"🔄 {step_name}...")
    elif status == "completed":
        print(f"✅ {step_name}")
    elif status == "skipped":
        print(f"⏭️  {step_name} (skipped)")

service = PipelineService(config)
result = service.execute(progress_callback=progress_callback)
```

### Pattern 3: Step-by-Step Execution
```python
from podx.services import StepExecutor

executor = StepExecutor(verbose=True)

# Fetch
meta = executor.fetch(show="My Podcast")

# Transcode
audio = executor.transcode(meta, fmt="wav16", outdir=Path("./output"))

# Transcribe with custom settings
transcript = executor.transcribe(
    audio,
    model="large-v3",
    preset="precision",
    asr_provider="openai"
)

# Align
aligned = executor.align(transcript)

# Custom post-processing
# ... your custom logic here ...
```

### Pattern 4: Batch Processing
```python
shows = ["Podcast A", "Podcast B", "Podcast C"]

for show in shows:
    config = PipelineConfig(show=show, align=True, deepcast=True)
    service = PipelineService(config)
    try:
        result = service.execute()
        print(f"✅ {show}: {len(result.steps_completed)} steps")
    except Exception as e:
        print(f"❌ {show}: {e}")
```

## Migration Guide

### For CLI Users
No changes required - existing `podx run` commands work as before.

### For Developers
To use the new service layer programmatically:

1. **Install podx**:
   ```bash
   pip install -e .
   ```

2. **Import service layer**:
   ```python
   from podx.services import PipelineConfig, PipelineService, StepExecutor
   ```

3. **Create configuration**:
   ```python
   config = PipelineConfig(
       show="Your Podcast",
       align=True,
       deepcast=True,
       deepcast_model="gpt-4",
   )
   ```

4. **Execute pipeline**:
   ```python
   service = PipelineService(config)
   result = service.execute()
   ```

5. **Access results**:
   ```python
   print(f"Workdir: {result.workdir}")
   print(f"Steps: {result.steps_completed}")
   print(f"Artifacts: {result.artifacts}")
   ```

## Performance Considerations

### Command Execution
- StepExecutor uses subprocess for each step
- JSON I/O overhead is minimal
- Steps are executed sequentially (no parallel execution yet)

### State Management
- Artifact detection scans working directory
- RunState persists to JSON for crash recovery
- Minimal overhead for state operations

### Memory Usage
- JSON files loaded into memory during execution
- Large transcripts (>1 hour) can use significant memory
- Consider streaming for very long audio files

## Future Enhancements

### Short Term (Phase 5-6)
1. Refactor orchestrate.py to use PipelineService
2. Add comprehensive unit tests for service layer
3. Extract interactive selection to separate UI module
4. Migrate dual mode logic to PipelineService

### Medium Term (Phase 7-8)
1. Add parallel step execution support
2. Implement step dependencies and DAG execution
3. Add plugin system for custom steps
4. Create API server using service layer

### Long Term (Phase 9-10)
1. Add distributed execution support
2. Implement caching and incremental processing
3. Create web UI using service layer
4. Add advanced monitoring and observability

## Conclusion

The service layer provides a clean, testable, and extensible foundation for pipeline orchestration. It separates business logic from CLI concerns, enabling programmatic usage and multiple frontend interfaces.

For questions or contributions, see the main REFACTORING_PLAN.md document.
