# Changelog

All notable changes to podx will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2025-11-15

### 🎉 Feature Bonanza - 8 Major Enhancements!

A massive release with **30,280 lines added** across **8 major features** to supercharge your podcast workflow!

### ✨ Added

#### 🔍 Transcript Search & Analysis (Part B.4)
- **Full-text search** with SQLite FTS5 (BM25 ranking, blazing fast keyword search)
- **Semantic search** with sentence transformers and FAISS (meaning-based search)
- **Quote extraction** with quality scoring (0-1 scale, heuristic-based)
- **Highlight detection** (temporal clustering of high-quality quotes)
- **Topic clustering** with K-means (organize content by themes)
- **Speaker analytics** (segment count, duration, word count, percentages)
- New commands: `podx-search` (index, query, list, stats), `podx-analyze` (quotes, highlights, topics, speakers)
- Optional dependencies: `sentence-transformers~=2.2.0`, `faiss-cpu>=1.8.0`, `scikit-learn~=1.3.0`

#### 🎨 Export Formats (Part B.1)
- **PDF export** with ReportLab (speaker colors, timestamps, metadata, page numbers)
- **HTML export** with dark mode toggle, real-time search, speaker legend, click-to-copy timestamps (self-contained, zero external deps)
- Updated `podx-export` to support `--formats pdf,html`

#### ⚡ Batch Processing (Part B.2)
- **Parallel processing** with ThreadPoolExecutor (configurable workers: `--parallel N`)
- **Auto-detect episodes** from directory structure (episode-meta.json, audio files)
- **Pattern matching** and filtering (show name, date range, duration, status)
- **Retry logic** with exponential backoff (`--max-retries`, `--retry-delay`)
- **Status tracking** for each pipeline step (persistent storage in ~/.podx/batch-status.json)
- New commands: `podx-batch-transcribe`, `podx-batch-pipeline`, `podx-batch-status`

#### 🎛️ Configuration Profiles (Part B.3)
- **Named presets** for common workflows (saved in ~/.podx/profiles/)
- **Built-in profiles**: `quick` (fast), `standard` (balanced), `high-quality` (best)
- **Profile management**: save, load, list, delete, export, import
- **API key management**: `podx-config set-key`, `list-keys`, `remove-key` (secure storage in ~/.podx/.env)
- New command: `podx-config` with subcommands for profiles and keys

#### 🎤 Audio Quality Analysis (Part B.5)
- **Quality metrics**: SNR (high-pass filtering), dynamic range, clipping detection, silence ratio, speech ratio
- **Model recommendations** based on audio quality (base/medium/large-v3)
- **Auto-optimize flag** for adaptive processing
- New command: `podx-analyze-audio`
- Optional dependency: `librosa~=0.10.0`

#### 💰 Cost Estimation (Part B.6)
- **Token & cost estimation** before API calls (OpenAI, Anthropic, OpenRouter)
- **Pricing data** (updated Nov 2025) for all major LLM providers
- **Full pipeline estimation** with map-reduce overhead calculation
- **JSON output** for scripting integration
- New command: `podx-estimate`

#### 🧙 Interactive Setup Wizard (Part B.8)
- **First-time setup** guide (API keys, defaults, optional features)
- **Step-by-step flow**: Welcome → API Keys → Defaults → Optional Features → Summary → Save
- **Rich UI** with panels, prompts, masked input for API keys
- **Secure storage** (~/.podx/.env with 0600 permissions)
- New command: `podx-init`

#### ⚙️ CLI Improvements (Part B.7)
- **Error helpers** with smart suggestions (file not found, missing API keys, invalid models)
- **Command aliases**: `podx-quick` (fast), `podx-full` (complete), `podx-hq` (high-quality)
- **Shell completion** for bash/zsh/fish
- **Better help text** with examples and user-friendly descriptions
- New command: `podx-completion`

#### 🔧 Phase 6.1: LLM Provider Enhancements
- **API key configuration wizard** (`podx-models --configure`)
- **Status display** (`podx-models --status`) showing configured providers
- **Interactive setup** with masked password input
- **Environment variable exports** for shell profiles

### 🐛 Fixed
- SNR calculation for pure sine waves (now uses high-pass filtering at 6kHz)
- Temporal quote clustering (now sorts by timestamp before grouping)
- TUI navigation and display improvements
- Better error handling throughout

### 📚 Documentation
- Added Search & Analysis section to README.md
- Updated CORE_API.md with Batch Processing and Audio Quality modules (660+ lines)
- Enhanced examples and CLI help text

### 📊 Stats
- **30,280** lines added since v2.0.0
- **178** files changed
- **100+** new tests (all passing)
- **12** new CLI commands
- **8** major features delivered
- **0** breaking changes

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
