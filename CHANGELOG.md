# Changelog

All notable changes to podx will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.2.2] - 2025-11-25

### ✨ Added

#### 🐍 Python API Additions

New methods to expose the model catalog through the `PodxClient` and `AsyncPodxClient` API:

- **`client.list_models(provider, default_only, capability)`** - List available LLM models with optional filtering
  - Filter by provider (e.g., `"openai"`, `"anthropic"`)
  - Filter by capability (e.g., `"vision"`, `"function-calling"`)
  - Option to show only default CLI models

- **`client.get_model_info(model_id_or_alias)`** - Get detailed model information
  - Case-insensitive lookup with full alias support
  - Returns pricing, context window, capabilities, and more

- **`client.estimate_cost(model, transcript_path, text, token_count)`** - Estimate processing cost
  - Supports transcript files, raw text, or pre-calculated token counts
  - Configurable output/input token ratio
  - Returns detailed cost breakdown

#### 📦 New Response Models

- **`ModelInfo`** - Full model details including pricing, capabilities, and provider
- **`ModelPricingInfo`** - Pricing information with input/output costs per 1M tokens
- **`CostEstimate`** - Cost estimation with token counts and USD costs

#### Example Usage

```python
from podx.api import PodxClient

client = PodxClient()

# List all OpenAI models
for model in client.list_models(provider="openai"):
    print(f"{model.name}: ${model.pricing.input_per_1m}/M")

# Get model info with alias support
model = client.get_model_info("gpt5.1")  # or "gpt-5.1", "GPT-5-1"
print(f"Context: {model.context_window:,} tokens")

# Estimate cost before processing
estimate = client.estimate_cost(
    model="claude-sonnet-4.5",
    transcript_path="transcript.json"
)
print(f"Estimated cost: ${estimate.total_cost_usd:.4f}")
```

---

### 🧪 Testing
- ✅ 25 new unit tests for API model methods
- ✅ All existing tests pass

---

## [3.2.1] - 2025-11-25

### 🔧 Internal Improvements & Quality

A maintenance release focused on internal architecture improvements, updated pricing data, and enhanced user experience.

---

### ✨ Added

#### 🗂️ Centralized Model Catalog
- **New `podx/models/` module** - Single source of truth for all model data
  - `podx/models/catalog.py` - Core loader with query interface
  - `podx/models/__init__.py` - Clean public API
  - Singleton pattern for efficient loading
  - Case-insensitive model lookup
  - Comprehensive alias support (e.g., `gpt-5.1`, `gpt5.1`, `gpt-5-1` all work)
- **43 models across 8 providers** - OpenAI, Anthropic, Google, Meta, DeepSeek, Mistral, Cohere, Ollama
- **Provider configuration** - Centralized API key environment variables and documentation URLs
- **Backward compatible** - Existing code continues to work without changes

#### 💰 Updated Model Pricing (January 2025)
- **New OpenAI models:**
  - GPT-5.1 ($1.25/$10.00 per 1M tokens)
  - GPT-5 ($1.25/$10.00)
  - GPT-5-mini ($0.25/$2.00)
  - GPT-5-nano ($0.05/$0.40)
  - GPT-4.1 family (4.1, 4.1-mini, 4.1-nano)
  - O-series reasoning models (o1, o1-mini, o3, o3-mini, o4-mini)
- **New Anthropic models:**
  - Claude Opus 4.5 ($5.00/$25.00) with prompt caching support
  - Claude Sonnet 4.5 ($3.00/$15.00)
  - Claude Haiku 4.5 ($1.00/$5.00)
- **Updated pricing** for all existing models to January 2025 rates

---

### 🔄 Changed

#### Error Messages
- **Replaced rich-click** with plain Click for UNIX-style error messages
  - Clean `Error: message` format instead of bordered panels
  - Removed fancy formatting for better terminal compatibility
  - Standard Unix tool aesthetics
- **Removed Python stacktraces** from user-facing template errors
  - Uses `click.ClickException` for clean error reporting
  - Stacktraces only shown for actual bugs, not user errors

#### Display Improvements
- **Smarter price formatting** - Shows 2-4 decimal places based on actual precision
- **Conditional columns** - "Est USD" column only shows when `--estimate` flag is used
- **Better model display** - Always shows actual model name (fixes duplicate entries)

---

### 🏗️ Internal Refactoring

#### Architecture
- **Eliminated DRY violations** - Model pricing was duplicated across 48+ files
- **Data-code separation** - All model data now in `podx/data/models.json`
- **Centralized queries** - `get_model()`, `list_models()`, `get_provider()`, `check_api_key()`
- **Easy maintenance** - Add new models by editing JSON, no code changes needed

#### Files Modified
- `podx/cli/models.py` - Now uses centralized catalog
- `podx/cli/templates.py` - Now uses centralized catalog for cost estimation
- `podx/pricing.py` - Ready for future migration to catalog
- `podx/cli/orchestrate.py` - Removed rich-click dependency

---

### 📝 Documentation
- Updated `.ai-docs/MODEL_CATALOG_REFACTORING.md` - Complete refactoring documentation
- All changes maintain backward compatibility

---

### 🧪 Testing
- ✅ All existing tests pass
- ✅ Verified `podx models` command works correctly
- ✅ Verified `podx templates preview --cost` works with model aliases
- ✅ Confirmed no regressions in functionality

---

## [3.2.0] - 2025-11-24

### 🎯 Enhanced Template System

A feature release introducing **10 new format-based analysis templates** with length-adaptive scaling, preview mode, and comprehensive template management.

---

### ✨ Added

#### 📝 Format-Based Templates (NEW!)
- **10 specialized templates** optimized for different podcast formats:
  - `solo-commentary` - Single host sharing thoughts, analysis, or storytelling
  - `interview-1on1` - Host interviewing a single guest
  - `panel-discussion` - Multiple co-hosts or guests discussing topics
  - `lecture-presentation` - Educational content with structured teaching
  - `debate-roundtable` - Structured debates with opposing viewpoints
  - `news-analysis` - Analysis and discussion of current events
  - `case-study` - Deep analysis of specific companies, events, or cases
  - `technical-deep-dive` - In-depth technical discussions of technology/science
  - `business-strategy` - Discussion of business strategy and market analysis
  - `research-review` - Discussion and analysis of academic research papers

**Key Features:**
- **Length-adaptive scaling** - Output automatically adjusts to episode duration (<30min, 30-60min, 60-90min, 90+min)
- **Format field** - Templates organized by podcast structure (not content category)
- **Example podcasts** - Each template includes well-known podcast examples
- **DRY-compliant design** - Scaling guidance defined once in system prompt

#### 🔧 Template Management CLI
**New `podx templates` command group:**
- `podx templates list` - List all available templates (table or JSON format)
- `podx templates show <name>` - Show detailed template information
- `podx templates preview <name>` - Preview template output without LLM calls (dry-run mode)
- `podx templates export <name>` - Export template to YAML file
- `podx templates import <source>` - Import template from file or URL
- `podx templates delete <name>` - Delete user templates (built-ins protected)

**Preview Mode Features:**
- Sample data generation for testing
- Multiple input methods (CLI flags, JSON file, sample data)
- Cost estimation with token counting (using tiktoken)
- GPT-4o pricing estimates ($2.50/1M input, $10/1M output)

#### 📚 Documentation
- **`docs/TEMPLATES.md`** - Comprehensive 575-line guide covering:
  - Overview of all 10 templates with example podcasts
  - Length-adaptive scaling explanation
  - Complete CLI usage examples
  - Custom template creation guide
  - Cost estimation guide
  - Template selection decision tree
  - Format vs Category explanation
  - Python API reference
  - Troubleshooting section
  - Migration guide from v3.1.0

#### ✅ Testing
- **40 new tests** for template system (19 unit + 21 CLI tests)
- Tests for all 10 template formats
- CLI command tests (list, show, preview, export, import, delete)
- Template rendering and variable substitution tests
- Scaling guidance validation
- Export/import roundtrip tests

---

### 🔄 Changed

#### Template System
- **Replaced 5 basic templates** with 10 format-based templates
  - Old: `default`, `interview`, `tech-talk`, `storytelling`, `minimal`
  - New: See "Format-Based Templates" above
- **Added `format` field** to `DeepcastTemplate` model
- **Improved template prompts** - More comprehensive and structured output

#### Migration from v3.1.0
| Old Template | New Template(s) |
|-------------|-----------------|
| `default` | Use `interview-1on1` or `solo-commentary` |
| `interview` | `interview-1on1` |
| `tech-talk` | `technical-deep-dive` |
| `storytelling` | `solo-commentary` or `case-study` |
| `minimal` | Use any template with short episodes (<30 min) |

---

### 📦 Dependencies

**Optional dependencies** (for cost estimation in preview mode):
- `tiktoken` - Token counting for cost estimates (included in `llm` extras)

Install with: `pip install 'podx[llm]'`

---

### 🎓 Learn More

- **Templates Guide**: `docs/TEMPLATES.md`
- **Quick Start**: `podx templates list` to see all available templates
- **Try Preview**: `podx templates preview interview-1on1 --sample --cost`

---

## [3.0.0] - 2025-11-18

### 🚀 Major Release - Web API Server & CLI Restructure

A major release introducing a **production-grade Web API Server** with FastAPI, SSE streaming, and Docker support, plus a **breaking CLI restructure** that improves discoverability and aligns with modern CLI design patterns.

---

### ⚡ Breaking Changes

#### CLI Command Structure
**All `podx-verb` commands are now `podx verb` subcommands.**

This change improves discoverability, reduces namespace pollution, and aligns with modern CLI design patterns (like `git`, `docker`, `kubectl`).

**Migration:**
- `podx-run` → `podx run`
- `podx-transcribe` → `podx transcribe`
- `podx-diarize` → `podx diarize`
- `podx-deepcast` → `podx deepcast`
- `podx-export` → `podx export`
- `podx-batch-transcribe` → `podx batch transcribe`
- `podx-search` → `podx search`
- `podx-analyze` → `podx analyze`
- And all other commands...

**Quick workflow aliases replaced with `--profile` flag:**
- `podx-quick` → `podx run --profile quick`
- `podx-full` → `podx run --profile standard`
- `podx-hq` → `podx run --profile high-quality`

See `MIGRATION_V3.md` for complete migration guide with automated scripts.

---

### ✨ Added

#### 🌐 Web API Server (NEW!)
- **Production-grade REST API** with FastAPI framework
- **SSE streaming** for real-time progress updates during long-running operations
- **Background job management** with SQLite persistence and status tracking
- **Health checks & metrics** for monitoring (Prometheus-compatible)
- **Docker support** with multi-stage builds and docker-compose
- **Interactive API docs** at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- **Authentication** with API key support (optional)
- **Rate limiting** and request validation
- **Comprehensive test coverage** (90%+ for server code)

**New commands:**
- `podx server start` - Start the API server
- `podx server stop` - Stop the running server
- `podx server status` - Check server status
- `podx server logs` - View server logs

**API Endpoints:**
- `POST /transcribe` - Transcribe audio with optional streaming
- `POST /diarize` - Diarize audio
- `POST /deepcast` - Generate show notes
- `POST /pipeline/run` - Run full pipeline
- `GET /jobs/{job_id}` - Get job status
- `GET /jobs/{job_id}/stream` - Stream job progress (SSE)
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

**Docker:**
- Multi-stage Dockerfile (optimized for size)
- docker-compose.yml for easy deployment
- Volume mounting for audio files and config
- Environment-based configuration

#### 🔧 Quality Improvements
- **Test coverage** improved from 33% to 40% (excluding UI)
- **18 tests fixed** from previous skipped state
- **838 total tests** (all passing)
- **Coverage configuration** with realistic targets (50% project, 60% patch)
- **CI/CD integration** with codecov

---

### 🔧 Changed

- **CLI entry points**: Single `podx` entry point with subcommands (see Breaking Changes)
- **Python API**: No changes (fully backward compatible)
- **Configuration**: No changes (same config files, same structure)
- **Command options**: No changes (all flags and options work the same)

---

### 📦 Dependencies

**New dependencies for Web API Server:**
- `fastapi~=0.115.0` - Web framework
- `uvicorn[standard]~=0.34.0` - ASGI server
- `sqlalchemy~=2.0.36` - Job persistence
- `aiosqlite~=0.20.0` - Async SQLite
- `sse-starlette~=2.2.1` - Server-Sent Events
- `prometheus-client~=0.21.0` - Metrics (optional)

Install with: `pip install podx[server]`

---

### 🐛 Fixed

- **18 skipped tests** now passing (export optimizations + state management)
- **Deepcast artifact detection** now finds both base files and suffixed variants
- **Export scanning** 10x faster with single-pass directory scanning
- **Coverage exclusions** properly configured for UI code

---

### 📚 Documentation

- **NEW**: `MIGRATION_V3.md` - Complete migration guide with automated scripts
- **NEW**: Web API Server section in README.md
- **Updated**: All command examples to use new `podx verb` syntax
- **Updated**: Docker deployment documentation
- **Updated**: CHANGELOG.md with v3.0.0 release notes

---

### 📊 Stats

- **40% test coverage** (up from 33%, excluding UI)
- **838 tests** (all passing)
- **90%+ coverage** for Web API Server code
- **18 tests fixed** (export + state management)
- **11,610 total lines** of code
- **4,678 covered lines**
- **Major version bump**: 2.x.x → 3.0.0

---

### 🔄 Migration Guide

See `MIGRATION_V3.md` for:
- Complete command mapping table
- Automated sed scripts for shell files
- CI/CD pipeline migration examples (GitHub Actions, GitLab CI)
- What hasn't changed (Python API, config, options)
- Testing and rollback instructions

**Quick migration:**
```bash
# Update shell scripts (macOS)
sed -i '' 's/podx-run/podx run/g' script.sh
sed -i '' 's/podx-transcribe/podx transcribe/g' script.sh

# Update CI/CD
- run: podx-transcribe episode.mp3
+ run: podx transcribe episode.mp3
```

---

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
