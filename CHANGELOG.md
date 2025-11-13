# Changelog

All notable changes to podx will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **URL-safe directory naming** - Episode directories now use slugified names: `show_name/YYYY-MM-DD-title-slug`
  - Show names use underscores, titles use hyphens
  - Titles truncated to ~20 chars for manageable paths
  - Handles special characters (é → e, spaces → hyphens, etc.)
  - Example: `lex_fridman_podcast/2024-10-15-yann-lecun-meta-ai`

### Changed
- **Major code organization improvements** - Decomposed large modules for better maintainability
  - orchestrate.py reduced from ~1,214 lines, extracted to commands/ and services/
  - api/client.py split into sync_client.py, async_client.py, and config.py
  - notion.py reduced from 1,385 to 633 lines (extracted to notion_services/)
  - deepcast.py reduced from 1,007 to 794 lines (extracted to deepcast_services/)
  - episode_browser_tui.py reduced from ~1,696 lines (extracted to ui/apps/)
  - Better adherence to Single Responsibility Principle
  - Foundation for future Phase 6 refactorings

## [2.0.0] - 2025-01-19

### 🎉 First Stable Release

podx v2.0.0 marks the first production-ready release with **stable public APIs**, comprehensive test coverage (332 tests, 100% passing), and significant performance improvements (4x-20x faster).

---

### ✨ Added

#### Public API Layer (`podx.api`)
- **NEW**: High-level `PodxClient` for programmatic access
- **NEW**: `ClientConfig` for type-safe client configuration
- **NEW**: Response models: `TranscribeResponse`, `DeepcastResponse`, `ExistsCheckResponse`
- **NEW**: `APIError` exception for standardized error handling
- **NEW**: `ValidationResult` for input validation feedback

#### Domain Layer (`podx.domain`)
- **NEW**: Type-safe enums: `PipelineStep`, `AnalysisType`, `ASRProvider`, `ASRPreset`, `AudioFormat`
- **NEW**: `PipelineConfig` for declarative pipeline configuration
- **NEW**: `PipelineResult` for structured execution results
- **NEW**: Pydantic v2 models with comprehensive validation
- **NEW**: Field validators for business logic (e.g., audio file existence checks)

#### Service Layer (`podx.services`)
- **NEW**: `PipelineService` for synchronous pipeline orchestration
- **NEW**: `AsyncPipelineService` for concurrent pipeline execution with asyncio
- **NEW**: `CommandBuilder` fluent API for CLI command construction
- **NEW**: `StepExecutor` and `AsyncStepExecutor` for command execution
- **NEW**: Batch processing with concurrency control

#### State Management (`podx.state`)
- **NEW**: `RunState` for pipeline state persistence and crash recovery
- **NEW**: `ArtifactDetector` for intelligent resume from existing artifacts
- **NEW**: `EpisodeArtifacts` dataclass for artifact tracking

#### Plugin System (`podx.plugins`)
- **NEW**: Extensible plugin architecture with discovery mechanism
- **NEW**: `PluginManager` for plugin lifecycle management
- **NEW**: Builtin plugins: YouTube source, Anthropic analysis, Slack/Discord/Webhook publishing
- **NEW**: `create_plugin_template()` for rapid plugin development

#### Testing
- **NEW**: 332 comprehensive tests (100% passing)
  - 313 unit tests
  - 19 integration tests
  - 40 optimization-specific tests

---

### 🚀 Performance Improvements

#### 20x Speedup - Batch LLM Restore (`podx-preprocess`)
- Batched API processing (100 segments: ~200s → ~10s)
- Implementation: `_semantic_restore_segments()` with configurable `batch_size`

#### 10x Speedup - Export Manifest Caching (`podx-export`)
- Single-pass scanning + episode metadata caching (100 episodes: ~50s → ~5s)
- Implementation: `_scan_export_rows()` with in-memory cache

#### 4x Speedup - Parallel Deepcast Processing (`podx-deepcast`)
- Concurrent async processing (10 chunks: ~40s → ~10s)
- Implementation: `asyncio.gather()` with semaphore rate limiting

---

### 🔒 Security

- **NEW**: Comprehensive security audit (PASS - see `SECURITY_AUDIT_v1.0.md`)
- **NEW**: Security policy for vulnerability reporting (`SECURITY.md`)
- **NEW**: Environment variable validation via Pydantic
- **NEW**: Safe subprocess execution (no `shell=True`)
- **NEW**: Input validation with field validators
- **NEW**: Structured logging with secret filtering

---

### 🔧 Changed

#### Breaking Changes

##### Pydantic v2 Migration
- **BREAKING**: All models use Pydantic v2 API
  - `parse_obj()` → `model_validate()`
  - `dict()` → `model_dump()`
  - `@validator` → `@field_validator`

##### Type-Safe Enums
- **BREAKING**: String literals replaced with enums
  - `preset="precision"` → `preset=ASRPreset.PRECISION`
  - `provider="openai"` → `provider=ASRProvider.OPENAI`

##### Import Paths
- **BREAKING**: Models moved from `podx.schemas` to `podx.domain`
  - Backward compatibility via `podx.schemas` re-exports (deprecated in v1.1)

#### Non-Breaking Changes

- **Improved**: CLI output with rich tables and better formatting
- **Improved**: Error messages more actionable
- **Improved**: Type coverage to 100% with MyPy strict mode

---

### 📦 Dependencies

All dependencies now pinned with `~=` for compatible releases:
- `pydantic~=2.12.0` (upgraded from 2.0.0)
- `structlog~=25.4.0` (upgraded from 24.1.0)
- `openai~=2.2.0` (upgraded from 1.40.0)
- See `pyproject.toml` for full list

---

### 🐛 Fixed

#### Critical Bugs
- **Fixed**: Undefined variable bugs in `orchestrate.py`
- **Fixed**: Enum-to-string conversion for pipeline config (11 locations)
- **Fixed**: Latest transcript assignment when reusing

#### High Priority
- **Fixed**: Flaky `test_select_plugin` test (shared registry state)
- **Fixed**: CLI flag inconsistencies across commands
- **Fixed**: Misaligned table rows from special characters

---

### 📝 Documentation

- **NEW**: `API_STABILITY.md` - Semantic versioning guarantees
- **NEW**: `SECURITY.md` - Vulnerability reporting policy
- **NEW**: `SECURITY_AUDIT_v1.0.md` - Security audit report
- **NEW**: `MIGRATION.md` - Upgrade guide from v0.x
- **Improved**: README with architecture diagram and benchmarks

---

## [0.2.0a1] - 2024-12-XX

### Added
- ASR provider abstraction (local/openai/hf)
- Presets and expert flags for transcribe
- Schema: asr_provider, preset, decoder_options
- Preprocess stage with optional restore
- Agreement check CLI

---

## Upgrading from v0.x

**See `MIGRATION.md` for detailed upgrade guide.**

Quick migration:
1. Update imports: `podx.schemas` → `podx.domain`
2. Use enums: `preset="precision"` → `preset=ASRPreset.PRECISION`
3. Update Pydantic: `parse_obj()` → `model_validate()`

---

## Semantic Versioning (v1.0+)

- **MAJOR** (1.x.x → 2.x.x): Breaking API changes
- **MINOR** (1.0.x → 1.1.x): New features (backward compatible)
- **PATCH** (1.0.0 → 1.0.1): Bug fixes (backward compatible)

See `API_STABILITY.md` for guarantees.

---

[1.0.0]: https://github.com/yourusername/podx/releases/tag/v1.0.0
[0.2.0a1]: https://github.com/yourusername/podx/releases/tag/v0.2.0a1
