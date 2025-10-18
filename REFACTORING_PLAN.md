# Podx Codebase Comprehensive Refactoring Plan

**Version:** 1.0
**Date:** 2025-10-18
**Codebase Version:** 0.2.0a1
**Total LOC:** ~15,164 lines across 37+ modules

---

## Executive Summary

### Current State Assessment

**Overall Quality: 6.5/10** - Well-architected foundation with good separation of concerns at the CLI level, but suffering from monolithic function syndrome in key orchestration modules.

**Key Strengths:**
- Clean CLI composability (Unix philosophy)
- Strong type safety with Pydantic
- Extensible plugin architecture
- Comprehensive documentation
- Good test coverage for integration scenarios
- Structured logging and error handling

**Critical Issues:**
- `orchestrate.py::run()` is 1,571 lines (P0 - severe technical debt)
- Undefined variable bugs in orchestrate.py (P0 - will cause crashes)
- Large monolithic files: orchestrate.py (2,725), deepcast.py (1,369), notion.py (1,575)
- Mixed concerns in orchestrator (CLI + UI + business logic + state management)
- Limited unit test coverage (mostly integration tests)
- Configuration complexity spread across 3 modules

**Refactoring Scope:** ~6-10 weeks of focused effort
**Risk Level:** Medium (well-tested, but large changes needed)
**Breaking Changes:** Minimal (internal refactoring, preserve public APIs)

---

## Strategic Goals

### 1. Maintainability
- Reduce cognitive load: functions <100 LOC, cyclomatic complexity <10
- Improve code discoverability: clear module boundaries
- Enable new developer onboarding in days, not weeks

### 2. Testability
- Achieve 80%+ unit test coverage
- Enable fast isolated testing without subprocess mocking
- Support test-driven development for new features

### 3. Extensibility
- Enhance plugin system with better examples
- Support alternative interfaces (API, library, GUI)
- Enable feature flags and A/B testing

### 4. Performance
- Enable parallel processing where appropriate
- Optimize file I/O with caching
- Support incremental pipeline execution

### 5. Production Readiness
- Eliminate all P0 bugs
- Add comprehensive error recovery
- Support graceful degradation
- Enable observability and monitoring

---

## Guiding Principles

1. **Preserve User-Facing APIs**: CLI commands, JSON schemas, config files should remain compatible
2. **Incremental Migration**: Each phase should be deployable independently
3. **Test-First Refactoring**: Write tests before refactoring, ensure they pass after
4. **Extract, Don't Rewrite**: Preserve business logic while improving structure
5. **Document as You Go**: Update docs alongside code changes
6. **Backward Compatibility**: Support legacy configs/workflows for 1-2 versions

---

## Phased Refactoring Roadmap

### Phase 0: Foundation & Bug Fixes (Week 1)
**Goal:** Stabilize current codebase, fix critical bugs
**Effort:** 1 week
**Risk:** Low

#### Tasks
1. **Fix Undefined Variable Bugs (P0)**
   - `orchestrate.py:710-711`: Initialize `resume_state`, `resume_config`
   - `orchestrate.py:763`: Initialize `chosen_type`
   - `orchestrate.py:824,927,958`: Initialize `selected`
   - `orchestrate.py:765`: Initialize `preview`

2. **Add Missing Type Hints**
   - Complete type annotations for all helper functions
   - Run mypy in strict mode, fix all errors
   - Add return type annotations to nested functions

3. **Extract Magic Numbers to Constants**
   ```python
   # Before
   per_page = 10
   fixed_cols = 4 + 18 + 12 + 4 + 4 + 4 + 4 + 3 + 5 + 16

   # After
   class TableConfig:
       EPISODES_PER_PAGE = 10
       EPISODE_NUM_WIDTH = 4
       DATE_WIDTH = 12
       # ... etc
   ```

4. **Eliminate Code Duplication**
   - Extract fidelity mapping logic (appears in 2 places)
   - Create shared command builder utility
   - Consolidate file existence checks

5. **Add Comprehensive Docstrings**
   - Document all public functions with Args/Returns/Raises
   - Add module-level docstrings
   - Document complex state transitions

**Deliverables:**
- Bug-free orchestrate.py
- 100% type hint coverage
- Constants module created
- Documentation updated

**Success Metrics:**
- 0 P0 bugs remaining
- mypy --strict passes
- All existing tests pass

---

### Phase 1: Extract Domain Models (Week 2)
**Goal:** Create clear data models and separate domain logic
**Effort:** 1 week
**Risk:** Low

#### New Structure
```
podx/
├── domain/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── episode.py          # EpisodeMeta, AudioMeta
│   │   ├── transcript.py       # Transcript, Segment, Word
│   │   ├── analysis.py         # DeepcastBrief, Analysis result models
│   │   ├── pipeline.py         # PipelineConfig, PipelineResult, PipelineStep
│   │   └── notion_page.py      # NotionPageConfig
│   ├── enums.py                # PipelineStep, AnalysisType, ASRProvider, etc.
│   └── constants.py            # All magic numbers, default values
```

#### Tasks

1. **Create PipelineConfig Model**
   ```python
   @dataclass
   class PipelineConfig:
       """Complete pipeline configuration"""
       # Source
       source_type: SourceType
       show: Optional[str] = None
       rss_url: Optional[str] = None
       youtube_url: Optional[str] = None

       # Audio
       audio_format: AudioFormat = AudioFormat.WAV16

       # ASR
       asr_provider: ASRProvider = ASRProvider.LOCAL
       asr_model: str = "medium.en"
       asr_preset: Optional[str] = None

       # Enhancement
       align: bool = False
       diarize: bool = False
       preprocess: bool = False

       # Analysis
       deepcast: bool = False
       deepcast_model: str = "gpt-4"
       deepcast_type: Optional[AnalysisType] = None

       # Export/Publish
       extract_markdown: bool = False
       deepcast_pdf: bool = False
       notion: bool = False

       @classmethod
       def from_fidelity(cls, level: int) -> "PipelineConfig":
           """Create config from fidelity preset (1-5)"""

       @classmethod
       def from_workflow(cls, workflow: str) -> "PipelineConfig":
           """Create config from workflow preset"""

       def validate(self) -> List[str]:
           """Validate configuration, return list of errors"""
   ```

2. **Create PipelineStep Enum**
   ```python
   class PipelineStep(str, Enum):
       FETCH = "fetch"
       TRANSCODE = "transcode"
       TRANSCRIBE = "transcribe"
       ALIGN = "align"
       DIARIZE = "diarize"
       PREPROCESS = "preprocess"
       DEEPCAST = "deepcast"
       EXPORT = "export"
       NOTION = "notion"
   ```

3. **Extract Analysis Models**
   - Move DeepcastBrief to domain/models/analysis.py
   - Create AnalysisRequest, AnalysisResponse models
   - Define clear interfaces for analysis plugins

4. **Consolidate Schemas**
   - Move existing schemas.py models into domain/models/
   - Ensure all models use Pydantic v2 properly
   - Add custom validators and serializers

**Deliverables:**
- domain/ package with all models
- Enums for all string-based state
- Constants module with all magic numbers
- Updated imports across codebase

**Success Metrics:**
- No string-based enums remaining
- All models have comprehensive validation
- 100% test coverage for domain models

---

### Phase 2: Extract State Management (Week 3)
**Goal:** Centralize pipeline state tracking and resumption logic
**Effort:** 1 week
**Risk:** Medium

#### New Structure
```
podx/
├── state/
│   ├── __init__.py
│   ├── run_state.py            # RunState class for state persistence
│   ├── artifact_detector.py    # Detect completed steps from artifacts
│   └── state_store.py          # Abstract interface for state storage
```

#### Tasks

1. **Create RunState Class**
   ```python
   class RunState:
       """Manages pipeline execution state and resumption"""

       def __init__(self, working_dir: Path):
           self.working_dir = working_dir
           self.config: PipelineConfig
           self.completed_steps: Set[PipelineStep] = set()
           self.metadata: Dict[str, Any] = {}
           self.created_at: datetime
           self.updated_at: datetime

       @classmethod
       def load(cls, working_dir: Path) -> Optional["RunState"]:
           """Load saved state from run-state.json"""

       def save(self) -> None:
           """Persist state to disk"""

       def mark_completed(self, step: PipelineStep) -> None:
           """Mark step as completed"""

       def is_completed(self, step: PipelineStep) -> bool:
           """Check if step is completed"""

       def get_artifact_path(self, step: PipelineStep) -> Optional[Path]:
           """Get path to step's output artifact"""

       def detect_completed_steps(self) -> Set[PipelineStep]:
           """Scan working directory for artifacts"""
   ```

2. **Create ArtifactDetector**
   ```python
   class ArtifactDetector:
       """Detect completed pipeline steps from artifacts"""

       ARTIFACT_PATTERNS = {
           PipelineStep.FETCH: ["episode-meta.json"],
           PipelineStep.TRANSCODE: ["audio-meta.json"],
           PipelineStep.TRANSCRIBE: ["transcript-*.json"],
           # ... etc
       }

       def __init__(self, working_dir: Path):
           self.working_dir = working_dir

       def detect(self) -> Set[PipelineStep]:
           """Detect all completed steps"""

       def get_artifact(self, step: PipelineStep) -> Optional[Path]:
           """Get path to step's primary artifact"""

       def get_transcripts(self) -> List[TranscriptArtifact]:
           """List all available transcript artifacts"""
   ```

3. **Migrate State Logic**
   - Extract state detection from orchestrate.py (lines 2768-2809)
   - Move run-state.json handling to RunState class
   - Create clean interface for state queries

**Deliverables:**
- state/ package with RunState, ArtifactDetector
- Migrated state logic from orchestrate.py
- Unit tests for state management (80%+ coverage)

**Success Metrics:**
- State logic <200 LOC per module
- 100% test coverage for state detection
- State files remain compatible with current format

---

### Phase 3: Extract Interactive UI Layer (Week 4)
**Goal:** Separate interactive UI from business logic
**Effort:** 1 week
**Risk:** Low

#### New Structure
```
podx/
├── ui/
│   ├── __init__.py
│   ├── episode_selector.py     # Interactive episode browser
│   ├── transcript_selector.py  # Interactive transcript selection
│   ├── confirmation.py         # Yes/no prompts, proceed checks
│   ├── table_builder.py        # Table rendering utilities
│   └── formatters.py           # Cell formatting, sanitization
```

#### Tasks

1. **Create EpisodeSelector**
   ```python
   class EpisodeSelector:
       """Interactive episode selection with pagination"""

       def __init__(self, console: Console):
           self.console = console

       def select_episode(
           self,
           scan_dir: Path,
           show_filter: Optional[str] = None,
           per_page: int = 10
       ) -> Optional[EpisodeSelection]:
           """Display paginated episode list, return selection"""

       def _scan_episodes(self, scan_dir: Path) -> List[EpisodeInfo]:
           """Scan directory for episode metadata"""

       def _render_table(
           self,
           episodes: List[EpisodeInfo],
           page: int,
           total_pages: int
       ) -> Table:
           """Render episode table for current page"""

       def _handle_input(self, choice: str, episodes: List) -> SelectionAction:
           """Process user input (number, N/P, F, keyword, Q)"""
   ```

2. **Create ConfirmationPrompts**
   ```python
   class Confirmation:
       """Reusable yes/no/quit prompts"""

       @staticmethod
       def yes_no(prompt: str, default: bool = False) -> bool:
           """Ask yes/no question with strict validation"""

       @staticmethod
       def yes_no_quit(prompt: str) -> Optional[bool]:
           """Ask yes/no/quit question, return None if quit"""

       @staticmethod
       def proceed_or_exit(message: str) -> None:
           """Show message and ask to proceed or exit"""
   ```

3. **Extract Table Building**
   - Move table rendering logic from orchestrate.py
   - Create reusable TableBuilder class
   - Extract cell sanitization (_clean_cell)

**Deliverables:**
- ui/ package with interactive components
- Extracted UI logic from orchestrate.py
- Reusable UI components for other modules

**Success Metrics:**
- UI logic <300 LOC per module
- No UI logic in orchestrate.py business logic
- UI components reusable across fetch/transcode/transcribe

---

### Phase 4: Refactor Orchestration Service (Weeks 5-6)
**Goal:** Extract business logic into testable service layer
**Effort:** 2 weeks
**Risk:** High (largest refactoring)

#### New Structure
```
podx/
├── services/
│   ├── __init__.py
│   ├── pipeline_service.py     # Core orchestration service
│   ├── step_executor.py        # Execute individual steps
│   ├── command_builder.py      # Build CLI commands
│   └── workflow_presets.py     # Fidelity/workflow logic
├── adapters/
│   ├── __init__.py
│   ├── subprocess_executor.py  # Execute subprocess commands
│   ├── file_manager.py         # File I/O operations
│   └── progress_tracker.py     # Progress display adapter
```

#### Tasks

1. **Create PipelineService (Core Business Logic)**
   ```python
   class PipelineService:
       """Orchestrate complete pipeline execution"""

       def __init__(
           self,
           executor: CommandExecutor,
           file_manager: FileManager,
           progress_tracker: ProgressTracker,
           state_manager: StateManager
       ):
           self.executor = executor
           self.files = file_manager
           self.progress = progress_tracker
           self.state = state_manager

       def execute(
           self,
           config: PipelineConfig,
           working_dir: Path,
           resume: bool = False
       ) -> PipelineResult:
           """Execute complete pipeline with given configuration"""

           # Load or create state
           state = self._initialize_state(working_dir, resume)

           # Execute pipeline steps
           if self._should_execute(PipelineStep.FETCH, state):
               self._execute_fetch(config, state)

           if self._should_execute(PipelineStep.TRANSCODE, state):
               self._execute_transcode(config, state)

           # ... etc for each step

           return PipelineResult(
               working_dir=working_dir,
               completed_steps=state.completed_steps,
               artifacts=state.artifacts
           )

       def _execute_fetch(
           self,
           config: PipelineConfig,
           state: RunState
       ) -> EpisodeMeta:
           """Execute fetch step"""

       def _execute_transcode(
           self,
           config: PipelineConfig,
           state: RunState
       ) -> AudioMeta:
           """Execute transcode step"""
   ```

2. **Create StepExecutor**
   ```python
   class StepExecutor:
       """Execute individual pipeline steps via CLI commands"""

       def __init__(self, executor: CommandExecutor):
           self.executor = executor

       def fetch(
           self,
           config: PipelineConfig,
           output_path: Path
       ) -> EpisodeMeta:
           """Execute podx-fetch command"""
           cmd = CommandBuilder("podx-fetch")
           if config.show:
               cmd.add_option("--show", config.show)
           # ... build complete command
           result = self.executor.execute(cmd.build())
           return EpisodeMeta.parse_obj(result)

       def transcribe(
           self,
           audio_meta: AudioMeta,
           config: PipelineConfig,
           output_path: Path
       ) -> Transcript:
           """Execute podx-transcribe command"""
   ```

3. **Create CommandBuilder**
   ```python
   class CommandBuilder:
       """Fluent interface for building CLI commands"""

       def __init__(self, base_cmd: str):
           self.cmd = [base_cmd]

       def add_option(
           self,
           flag: str,
           value: Optional[str] = None
       ) -> "CommandBuilder":
           """Add option to command"""
           if value is not None:
               self.cmd.extend([flag, value])
           return self

       def add_flag(self, flag: str) -> "CommandBuilder":
           """Add boolean flag"""
           self.cmd.append(flag)
           return self

       def build(self) -> List[str]:
           """Return final command list"""
           return self.cmd
   ```

4. **Create Adapter Interfaces**
   ```python
   class CommandExecutor(ABC):
       """Abstract interface for command execution"""

       @abstractmethod
       def execute(
           self,
           cmd: List[str],
           input_json: Optional[Dict] = None
       ) -> Dict[str, Any]:
           """Execute command and return JSON output"""

   class SubprocessExecutor(CommandExecutor):
       """Production implementation using subprocess"""

       def execute(
           self,
           cmd: List[str],
           input_json: Optional[Dict] = None
       ) -> Dict[str, Any]:
           # Real subprocess execution

   class MockExecutor(CommandExecutor):
       """Test implementation for mocking"""

       def execute(
           self,
           cmd: List[str],
           input_json: Optional[Dict] = None
       ) -> Dict[str, Any]:
           # Return mocked responses
   ```

5. **Refactor orchestrate.py::run()**
   ```python
   # Before: 1,571 lines

   # After: ~200 lines
   @main.command("run")
   @click.option(...)  # All existing options preserved
   def run(...):  # All existing parameters preserved
       """Orchestrate the complete podcast processing pipeline."""

       # 1. Build configuration from CLI args
       config = _build_pipeline_config(
           align=align,
           diarize=diarize,
           deepcast=deepcast,
           # ... all args
       )

       # 2. Handle interactive episode selection
       working_dir, resume_state = _handle_interactive_mode(
           interactive_select=interactive_select,
           scan_dir=scan_dir,
           show=show,
           workdir=workdir
       )

       # 3. Execute pipeline through service
       service = PipelineService(
           executor=SubprocessExecutor(),
           file_manager=FileManager(),
           progress_tracker=ConsoleProgressTracker(),
           state_manager=StateManager(working_dir)
       )

       result = service.execute(
           config=config,
           working_dir=working_dir,
           resume=resume_state is not None
       )

       # 4. Display results
       _display_results(result, console)

       # 5. Output JSON
       print(json.dumps(result.to_dict(), indent=2))
   ```

6. **Extract Helper Functions to Utilities**
   ```python
   # podx/utils/fidelity.py
   def apply_fidelity_preset(level: int) -> PipelineConfig:
       """Apply fidelity preset and return configuration"""

   # podx/utils/validation.py
   def validate_pipeline_inputs(config: PipelineConfig) -> List[str]:
       """Validate pipeline configuration"""

   # podx/utils/file_utils.py
   def sanitize_filename(name: str) -> str:
       """Sanitize filename for safe file system usage"""
   ```

**Deliverables:**
- services/ package with PipelineService, StepExecutor
- adapters/ package with clean interfaces
- Refactored orchestrate.py::run() (~200 LOC)
- Helper functions extracted to utils/

**Success Metrics:**
- orchestrate.py::run() <250 LOC
- PipelineService fully unit testable
- 80%+ test coverage for service layer
- All existing CLI tests pass

---

### Phase 5: Configuration Consolidation (Week 7)
**Goal:** Unify configuration management into single cohesive system
**Effort:** 1 week
**Risk:** Medium

#### New Structure
```
podx/
├── config/
│   ├── __init__.py
│   ├── manager.py              # Unified config manager
│   ├── loader.py               # Load from YAML/JSON/env
│   ├── validator.py            # Config validation
│   ├── podcast_mappings.py     # Podcast-specific configs
│   └── migrations.py           # Config version migrations
```

#### Tasks

1. **Create Unified ConfigManager**
   ```python
   class ConfigManager:
       """Unified configuration management"""

       def __init__(self):
           self.env_config = PodxConfig()  # From env vars
           self.yaml_config = None         # From YAML
           self.podcast_configs = {}       # Podcast mappings

       def load(self, yaml_path: Optional[Path] = None) -> None:
           """Load configuration from all sources"""

       def get_pipeline_config(
           self,
           cli_overrides: Dict[str, Any],
           show_name: Optional[str] = None
       ) -> PipelineConfig:
           """Build final config with precedence: CLI > YAML > Env"""

       def get_podcast_config(
           self,
           show_name: str
       ) -> Optional[PodcastAnalysisConfig]:
           """Get podcast-specific configuration"""

       def get_notion_database(
           self,
           database_key: str = "default"
       ) -> NotionDatabaseConfig:
           """Get Notion database configuration"""
   ```

2. **Consolidate Existing Modules**
   - Merge config.py, yaml_config.py, podcast_config.py
   - Preserve all functionality
   - Add proper versioning and migrations

3. **Add Configuration Validation**
   ```python
   class ConfigValidator:
       """Validate configuration at load time"""

       def validate_yaml(self, config: Dict) -> List[str]:
           """Validate YAML structure"""

       def validate_podcast_mapping(
           self,
           mapping: Dict
       ) -> List[str]:
           """Validate podcast mapping structure"""
   ```

**Deliverables:**
- config/ package with unified manager
- Deprecated old config modules (with warnings)
- Migration guide for config files
- Schema validation for YAML configs

**Success Metrics:**
- Single entry point for all config operations
- All config tests pass
- Config loading <100ms

---

### Phase 6: Enhanced Testing (Week 8)
**Goal:** Achieve comprehensive test coverage
**Effort:** 1 week
**Risk:** Low

#### New Structure
```
tests/
├── unit/
│   ├── domain/
│   │   ├── test_models.py
│   │   └── test_enums.py
│   ├── services/
│   │   ├── test_pipeline_service.py
│   │   └── test_step_executor.py
│   ├── state/
│   │   ├── test_run_state.py
│   │   └── test_artifact_detector.py
│   ├── config/
│   │   └── test_config_manager.py
│   └── ui/
│       └── test_episode_selector.py
├── integration/
│   ├── test_pipeline_e2e.py
│   ├── test_cli_commands.py
│   └── test_plugin_system.py
├── fixtures/
│   ├── sample_episodes/
│   ├── sample_transcripts/
│   └── sample_configs/
└── conftest.py
```

#### Tasks

1. **Add Unit Tests for New Modules**
   - domain/ models: 100% coverage
   - state/ management: 95% coverage
   - services/ layer: 90% coverage
   - ui/ components: 85% coverage
   - config/ manager: 90% coverage

2. **Refactor Integration Tests**
   - Keep existing integration tests
   - Add integration tests for new service layer
   - Add end-to-end pipeline tests

3. **Create Test Fixtures**
   - Sample episode metadata
   - Sample transcripts (aligned, diarized)
   - Sample configurations (YAML, JSON)
   - Mock API responses

4. **Add Performance Tests**
   ```python
   def test_large_transcript_performance():
       """Ensure large transcripts process in <5s"""
       transcript = generate_large_transcript(hours=3)
       start = time.time()
       result = deepcast.analyze(transcript)
       assert time.time() - start < 5.0
   ```

**Deliverables:**
- 80%+ unit test coverage
- Preserved integration test coverage
- Performance benchmarks
- Test documentation

**Success Metrics:**
- pytest runs in <30s (unit tests)
- 80%+ code coverage (pytest-cov)
- 0 flaky tests

---

### Phase 7: API & Integration Layer Enhancement (Week 9)
**Goal:** Expand REST API and enable programmatic usage
**Effort:** 1 week
**Risk:** Low

#### New Structure
```
podx/
├── api/
│   ├── __init__.py
│   ├── server.py               # FastAPI/Flask app
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Pipeline execution endpoints
│   │   ├── episodes.py         # Episode management
│   │   └── config.py           # Configuration endpoints
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── requests.py         # Request models
│   │   └── responses.py        # Response models
│   └── middleware/
│       ├── __init__.py
│       └── error_handler.py
├── sdk/
│   ├── __init__.py
│   └── client.py               # Python SDK for API
```

#### Tasks

1. **Expand REST API**
   ```python
   # POST /api/v1/pipeline/execute
   {
       "config": {
           "show": "The Podcast",
           "date": "2024-10-02",
           "align": true,
           "deepcast": true
       }
   }

   # Response: Job ID for async execution
   {"job_id": "xxx-xxx-xxx"}

   # GET /api/v1/jobs/{job_id}
   # Response: Job status and results
   ```

2. **Create Python SDK**
   ```python
   from podx import PodxClient

   client = PodxClient(api_key="...")

   # Execute pipeline
   job = client.execute_pipeline(
       show="The Podcast",
       date="2024-10-02",
       align=True,
       deepcast=True
   )

   # Wait for completion
   result = job.wait()

   # Access results
   print(result.deepcast_brief)
   ```

3. **Add WebSocket Support**
   - Real-time progress updates
   - Streaming logs
   - Pipeline status events

**Deliverables:**
- Expanded REST API with CRUD operations
- Python SDK for programmatic access
- WebSocket support for real-time updates
- API documentation (OpenAPI/Swagger)

**Success Metrics:**
- 100% API endpoint coverage
- SDK examples in documentation
- <100ms API response time (non-pipeline endpoints)

---

### Phase 8: Plugin System Enhancement (Week 10)
**Goal:** Improve plugin system with better examples and documentation
**Effort:** 1 week
**Risk:** Low

#### Tasks

1. **Enhance Plugin Discovery**
   ```python
   # podx/plugins/registry.py
   class PluginRegistry:
       """Centralized plugin registry"""

       def __init__(self):
           self.plugins: Dict[PluginType, List[PluginInterface]] = {}

       def register(
           self,
           plugin_type: PluginType,
           plugin: PluginInterface
       ) -> None:
           """Register a plugin"""

       def discover(self) -> None:
           """Auto-discover plugins from entry points"""

       def get_plugin(
           self,
           plugin_type: PluginType,
           name: str
       ) -> Optional[PluginInterface]:
           """Get plugin by type and name"""
   ```

2. **Add More Builtin Plugins**
   - Dropbox source plugin
   - Google Drive source plugin
   - Discord publish plugin
   - Webhook publish plugin

3. **Create Plugin Development Kit**
   - Plugin template generator
   - Plugin validation CLI
   - Plugin testing utilities

4. **Improve Plugin Documentation**
   - Step-by-step plugin creation guide
   - API reference for each plugin type
   - Example plugins with full source

**Deliverables:**
- Enhanced plugin registry
- 3+ new builtin plugins
- Plugin development kit
- Comprehensive plugin documentation

**Success Metrics:**
- Plugin registration <10ms
- Plugin validation CLI available
- 5+ example plugins

---

### Phase 9: Performance Optimization (Optional - Week 11)
**Goal:** Optimize performance for large workloads
**Effort:** 1 week
**Risk:** Low

#### Tasks

1. **Enable Parallel Processing**
   ```python
   # Parallel dual transcription
   with concurrent.futures.ThreadPoolExecutor() as executor:
       precision_future = executor.submit(
           step_executor.transcribe,
           audio_meta,
           config_precision
       )
       recall_future = executor.submit(
           step_executor.transcribe,
           audio_meta,
           config_recall
       )

       precision = precision_future.result()
       recall = recall_future.result()
   ```

2. **Add Caching Layer**
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def _load_transcript(path: Path) -> Transcript:
       """Cached transcript loading"""
   ```

3. **Optimize File I/O**
   - Batch file operations
   - Use memory-mapped files for large transcripts
   - Add streaming JSON parsing

4. **Add Performance Monitoring**
   - Track step execution times
   - Memory usage monitoring
   - Generate performance reports

**Deliverables:**
- Parallel processing for dual mode
- Caching layer for file operations
- Performance monitoring dashboard
- Optimization documentation

**Success Metrics:**
- 30%+ reduction in dual mode execution time
- 20%+ reduction in file I/O time
- Memory usage <500MB for typical workloads

---

## Detailed Module Refactoring Plan

### orchestrate.py (2,725 LOC → ~400 LOC)

**Current Issues:**
- 1,571-line `run()` function
- Mixed concerns (CLI, UI, business logic, state)
- Undefined variables (P0 bugs)
- Deep nesting (6-7 levels)
- Extensive code duplication

**Target State:**
- orchestrate.py: CLI layer only (~400 LOC)
- services/pipeline_service.py: Business logic (~500 LOC)
- ui/episode_selector.py: Interactive UI (~200 LOC)
- state/run_state.py: State management (~200 LOC)

**Migration Strategy:**
1. Fix P0 bugs first (undefined variables)
2. Extract state management to state/
3. Extract UI to ui/
4. Extract business logic to services/
5. Refactor run() to thin CLI wrapper

**Breaking Changes:** None (internal only)

---

### deepcast.py (1,369 LOC → ~800 LOC)

**Current Issues:**
- Large file handling multiple concerns
- Chunking logic mixed with analysis
- Prompt template handling embedded

**Target State:**
- deepcast.py: Core analysis logic (~400 LOC)
- services/deepcast_chunker.py: Map-reduce chunking (~200 LOC)
- services/deepcast_formatter.py: Output formatting (~150 LOC)
- domain/models/analysis.py: Analysis models (~150 LOC)

**Migration Strategy:**
1. Extract chunking logic
2. Move models to domain/
3. Extract formatters
4. Simplify main file

**Breaking Changes:** None (internal only)

---

### notion.py (1,575 LOC → ~600 LOC)

**Current Issues:**
- Complex page building logic
- Database management mixed with creation
- Large block builder methods

**Target State:**
- notion.py: Main Notion integration (~300 LOC)
- services/notion_builder.py: Page building (~200 LOC)
- services/notion_formatter.py: Block formatting (~150 LOC)

**Migration Strategy:**
1. Extract page builder
2. Extract block formatters
3. Simplify database management

**Breaking Changes:** None (internal only)

---

### Configuration Modules (config.py + yaml_config.py + podcast_config.py → unified config/)

**Current Issues:**
- Configuration spread across 3 modules
- Unclear precedence
- Difficult to test

**Target State:**
- config/manager.py: Unified config management (~300 LOC)
- config/loader.py: Multi-source loading (~200 LOC)
- config/podcast_mappings.py: Podcast-specific configs (~150 LOC)

**Migration Strategy:**
1. Create unified ConfigManager
2. Migrate YAML logic
3. Migrate podcast configs
4. Deprecate old modules (with warnings)
5. Update all imports

**Breaking Changes:**
- Import paths change (with deprecation warnings)
- Config file format remains compatible

---

## Migration & Rollout Strategy

### 1. Branch Strategy
```
main
├── refactor/phase-0-bugs          # Phase 0: Bug fixes
├── refactor/phase-1-models        # Phase 1: Domain models
├── refactor/phase-2-state         # Phase 2: State management
├── refactor/phase-3-ui            # Phase 3: UI layer
├── refactor/phase-4-services      # Phase 4: Service layer
└── refactor/complete              # Final merge branch
```

### 2. Testing Strategy
- Each phase must pass all existing tests
- Add new tests for extracted modules
- Run integration tests after each merge
- Performance regression tests

### 3. Backward Compatibility
- Preserve all CLI commands and arguments
- Maintain JSON schema compatibility
- Support legacy config files for 2 versions
- Add deprecation warnings, not errors

### 4. Documentation Updates
- Update documentation alongside code
- Add migration guides for each phase
- Create video walkthroughs for major changes
- Update examples in README

### 5. Rollout Plan
- Phase 0: Emergency release (bug fixes)
- Phases 1-3: Combined release (v0.3.0)
- Phases 4-5: Major release (v0.4.0)
- Phases 6-8: Feature release (v0.5.0)
- Phase 9: Performance release (v0.6.0)

---

## Risk Management

### High-Risk Areas

1. **orchestrate.py Refactoring (Phase 4)**
   - **Risk:** Breaking existing workflows
   - **Mitigation:**
     - Comprehensive integration tests
     - Beta testing with real workloads
     - Gradual extraction with feature flags
     - Keep old code path until verified

2. **Configuration Consolidation (Phase 5)**
   - **Risk:** Config file incompatibility
   - **Mitigation:**
     - Version-based migrations
     - Support legacy formats indefinitely
     - Clear migration documentation
     - Auto-migration tool

3. **State Management Changes (Phase 2)**
   - **Risk:** Resume functionality breaking
   - **Mitigation:**
     - Maintain run-state.json format
     - Add state migration logic
     - Extensive testing of resume scenarios

### Medium-Risk Areas

1. **Service Layer Extraction**
   - Extensive testing required
   - Careful interface design

2. **Plugin System Changes**
   - Maintain plugin compatibility
   - Version plugin interfaces

### Low-Risk Areas

1. **Domain Model Extraction** - Mostly additive
2. **UI Extraction** - Isolated functionality
3. **Testing Addition** - No production impact
4. **API Enhancement** - New functionality

---

## Success Metrics & KPIs

### Code Quality Metrics

| Metric | Current | Target | Phase |
|--------|---------|--------|-------|
| **Largest Function** | 1,571 LOC | <100 LOC | Phase 4 |
| **Largest Module** | 2,725 LOC | <800 LOC | Phase 4 |
| **Cyclomatic Complexity** | >100 | <10 | Phase 4 |
| **Code Duplication** | ~15% | <5% | Phase 0 |
| **Type Coverage** | ~80% | 100% | Phase 0 |
| **Test Coverage** | ~60% | 80%+ | Phase 6 |
| **Unit Test %** | ~20% | 60%+ | Phase 6 |

### Performance Metrics

| Metric | Current | Target | Phase |
|--------|---------|--------|-------|
| **Dual Transcription** | Sequential | 2x faster | Phase 9 |
| **File I/O** | Baseline | 20% faster | Phase 9 |
| **Memory Usage** | Baseline | <500MB | Phase 9 |
| **Test Suite** | ~2min | <30s | Phase 6 |

### Developer Experience Metrics

| Metric | Current | Target | Phase |
|--------|---------|--------|-------|
| **Onboarding Time** | ~2 weeks | ~3 days | Phase 4 |
| **Feature Add Time** | ~2 days | ~4 hours | Phase 4 |
| **Bug Fix Time** | ~4 hours | ~30 min | Phase 4 |
| **Code Review Time** | ~1 hour | ~15 min | Phase 4 |

---

## Post-Refactoring Maintenance

### 1. Code Quality Gates
- Enforce function size limits (<100 LOC)
- Enforce cyclomatic complexity (<10)
- Require 80%+ test coverage for new code
- Pre-commit hooks for formatting/linting

### 2. Architecture Decision Records
- Document major architectural decisions
- Maintain ADR log in docs/adr/

### 3. Continuous Improvement
- Monthly code review sessions
- Quarterly refactoring sprints
- Performance monitoring and optimization
- Regular dependency updates

### 4. Documentation Maintenance
- Keep docs in sync with code
- Regular documentation reviews
- User feedback integration
- Video tutorial updates

---

## Appendix A: File Size Targets

| File | Current | Target | Reduction |
|------|---------|--------|-----------|
| orchestrate.py | 2,725 | 400 | 85% |
| deepcast.py | 1,369 | 400 | 71% |
| notion.py | 1,575 | 300 | 81% |
| transcribe.py | 938 | 600 | 36% |
| export.py | 900 | 600 | 33% |
| fetch.py | 732 | 500 | 32% |
| plugins.py | 564 | 400 | 29% |
| yaml_config.py | 423 | 200 | 53% |

**Total LOC Reduction:** ~6,000 LOC removed via better organization (40% reduction)

---

## Appendix B: New Modules to Create

### Domain Layer (7 new files)
- domain/models/episode.py
- domain/models/transcript.py
- domain/models/analysis.py
- domain/models/pipeline.py
- domain/models/notion_page.py
- domain/enums.py
- domain/constants.py

### State Layer (3 new files)
- state/run_state.py
- state/artifact_detector.py
- state/state_store.py

### Service Layer (6 new files)
- services/pipeline_service.py
- services/step_executor.py
- services/command_builder.py
- services/workflow_presets.py
- services/deepcast_chunker.py
- services/notion_builder.py

### UI Layer (5 new files)
- ui/episode_selector.py
- ui/transcript_selector.py
- ui/confirmation.py
- ui/table_builder.py
- ui/formatters.py

### Config Layer (5 new files)
- config/manager.py
- config/loader.py
- config/validator.py
- config/podcast_mappings.py
- config/migrations.py

### Adapter Layer (3 new files)
- adapters/subprocess_executor.py
- adapters/file_manager.py
- adapters/progress_tracker.py

### Utils Layer (4 new files)
- utils/fidelity.py
- utils/validation.py
- utils/file_utils.py
- utils/command_utils.py

**Total New Files:** ~33 modules (improving organization)

---

## Appendix C: Testing Plan

### Unit Test Coverage Targets

| Module | Current | Target | New Tests |
|--------|---------|--------|-----------|
| domain/ models | 100% | 100% | 15 |
| state/ management | 0% | 95% | 20 |
| services/ layer | 0% | 90% | 30 |
| ui/ components | 0% | 85% | 15 |
| config/ manager | 60% | 90% | 10 |
| utils/ | 0% | 90% | 10 |

**Total New Unit Tests:** ~100

### Integration Test Coverage

| Area | Current | Target | New Tests |
|------|---------|--------|-----------|
| Full pipeline | 5 | 10 | 5 |
| CLI commands | 10 | 20 | 10 |
| Plugin system | 3 | 10 | 7 |
| Configuration | 5 | 10 | 5 |

**Total New Integration Tests:** ~27

---

## Conclusion

This comprehensive refactoring plan will transform the podx codebase from a functional but monolithic system into a well-architected, maintainable, and extensible platform. The phased approach ensures minimal disruption while systematically addressing technical debt.

**Key Outcomes:**
- 85% reduction in largest function size
- 80%+ test coverage
- Clean separation of concerns
- Enhanced developer experience
- Improved performance
- Better extensibility

**Timeline:** 9-11 weeks (aggressive) to 4-6 months (sustainable pace)

**Recommendation:** Execute Phases 0-2 immediately (foundational improvements), then assess velocity and resource availability for remaining phases. Each phase delivers incremental value and can be deployed independently.
