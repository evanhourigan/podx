# API Stability Guarantee (v1.0+)

This document defines the stable public API surface for podx v1.0 and semantic versioning guarantees.

## Semantic Versioning Commitment

Starting with v1.0.0, podx follows [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** (1.x.x → 2.x.x): Breaking changes to public APIs
- **MINOR** (1.0.x → 1.1.x): New features, backward compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backward compatible

## Public API Surface

The following modules constitute the **stable public API** and are covered by semantic versioning guarantees:

### 1. High-Level Client API (`podx.api`)

**Status**: ✅ Stable

```python
from podx.api import (
    PodxClient,          # Main client for podcast processing
    ClientConfig,        # Client configuration
    TranscribeResponse,  # Transcription results
    DeepcastResponse,    # Analysis results
    ExistsCheckResponse, # Artifact existence checks
    APIError,            # API error exceptions
    ValidationResult,    # Input validation results
)
```

**Guarantees**:
- Method signatures will not change in breaking ways
- New optional parameters may be added (backward compatible)
- Response objects may gain new fields (backward compatible)
- Existing fields will not be removed or change types

### 2. Domain Models (`podx.domain`)

**Status**: ✅ Stable

```python
from podx.domain import (
    # Enums
    PipelineStep,      # Pipeline execution steps
    AnalysisType,      # Deepcast analysis types
    ASRProvider,       # ASR backend providers
    ASRPreset,         # ASR quality presets
    AudioFormat,       # Audio format types

    # Data Models
    EpisodeMeta,       # Episode metadata
    AudioMeta,         # Audio metadata
    Transcript,        # Full transcript with segments
    Segment,           # Transcript segment
    Word,              # Word-level timing
    AlignedSegment,    # Segment with word alignment
    DiarizedSegment,   # Segment with speaker info
    DeepcastQuote,     # Deepcast quote
    DeepcastOutlineItem, # Deepcast outline item
    DeepcastBrief,     # Deepcast brief analysis
    PipelineConfig,    # Pipeline configuration
    PipelineResult,    # Pipeline execution result
)
```

**Guarantees**:
- Pydantic model schemas are stable
- New optional fields may be added (backward compatible)
- Required fields will not be removed
- Field types will not change
- Validation logic may become stricter (with MINOR version bump)

### 3. Service Layer (`podx.services`)

**Status**: ✅ Stable

```python
from podx.services import (
    PipelineService,      # Sync pipeline orchestration
    AsyncPipelineService, # Async pipeline orchestration
    StepExecutor,         # Sync step execution
    AsyncStepExecutor,    # Async step execution
    CommandBuilder,       # CLI command builder
)
```

**Guarantees**:
- Public method signatures are stable
- New methods may be added (backward compatible)
- Private methods (prefixed with `_`) are not covered by guarantees

## Unstable/Experimental APIs

The following are **NOT** covered by stability guarantees and may change in MINOR versions:

### Internal Modules

- `podx.orchestrate` - CLI orchestration (use `podx.services` instead)
- `podx.fetch`, `podx.transcribe`, etc. - Individual CLI tools (use `podx.api.PodxClient` instead)
- `podx.config` - Internal configuration (use `podx.api.ClientConfig` instead)
- `podx.utils.*` - Internal utilities
- `podx.ui.*` - CLI UI components
- `podx.state.*` - Internal state management
- `podx.builtin_plugins.*` - Plugin internals (plugin interface is stable)

### Plugin System

**Status**: ⚠️ Beta (stabilizing in v1.1)

```python
from podx.plugins import (
    PluginInterface,   # Plugin base class
    PluginRegistry,    # Plugin registry
    PluginManager,     # Plugin discovery/execution
    PluginMetadata,    # Plugin metadata
)
```

The plugin system is functional but may undergo refinement in v1.1.

## Deprecation Policy

When deprecating public APIs:

1. **Deprecation Warning**: Mark as deprecated in MINOR version
   - Add `DeprecationWarning` in code
   - Document in CHANGELOG and migration guide
   - Maintain backward compatibility

2. **Removal**: Remove in next MAJOR version
   - Minimum 6 months after deprecation warning
   - Clear migration path documented

## CLI Stability

Command-line interfaces follow looser stability:

- **Stable**: `podx run` (main orchestrator)
- **Beta**: Individual commands (`podx transcribe`, etc.)
- **Options**: May add new options (backward compatible)
- **Output Format**: JSON output schemas are stable (follow domain model guarantees)

## Configuration Stability

Configuration file formats (`.podx.yaml`, `podcast-config.yaml`) are stable:

- New fields may be added (backward compatible)
- Existing fields will not be removed
- Default values may change (documented in CHANGELOG)

## File Format Stability

Artifact file formats are stable:

- `episode-meta.json` - EpisodeMeta schema
- `transcript*.json` - Transcript schema
- `deepcast*.json` - Deepcast schema
- File naming conventions are stable

## Example: Stable Usage Pattern

```python
# This code will work across all v1.x.x releases
from podx.api import PodxClient, ClientConfig
from podx.domain import PipelineConfig, ASRPreset

config = ClientConfig(default_model="large-v3-turbo")
client = PodxClient(config=config)

pipeline_config = PipelineConfig(
    show="My Podcast",
    preset=ASRPreset.PRECISION,
    align=True,
    deepcast=True,
)

result = client.run(pipeline_config)
print(result.transcript_path)
```

## Breaking Changes in v1.0

v1.0 represents the **first stable release**. Changes from v0.x:

- **Pydantic v2 Migration**: All models use Pydantic v2 API
- **Enum Standardization**: Type-safe enums instead of string literals
- **Service Layer**: New `podx.services` for programmatic access
- **Domain Layer**: Clean separation of data models in `podx.domain`

See `MIGRATION.md` for detailed upgrade guide.

## Questions?

For API stability questions or feature requests, please open an issue at:
https://github.com/yourusername/podx/issues
