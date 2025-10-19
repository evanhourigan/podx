# Orchestration Refactoring Plan

**Status:** Phase 1 Complete - Services Exist, Integration Pending
**Start Date:** 2025-10-18
**Updated:** 2025-10-18
**Target:** Reduce orchestrate.py from 2,354 lines to ~400 lines

---

## Current State

**orchestrate.py Analysis:**
- **Total Lines:** 2,354 (unchanged - services not yet integrated)
- **run() function:** Lines 456-1219 (~764 lines)
- **Parameters:** 38 function parameters
- **Command Executions:** 13+ `_run()` calls
- **Mixed Concerns:** CLI + UI + business logic + state + command building

**Services Status:**
- ✅ **CommandBuilder** exists and ready (podx/services/command_builder.py)
- ✅ **StepExecutor** exists and ready (podx/services/step_executor.py)
- ✅ **PipelineService** exists and ready (podx/services/pipeline_service.py)
- ❌ **Integration:** Services NOT yet used by orchestrate.py
- 🔄 **Next Step:** Wire services into run() function

**Key Patterns Identified:**
1. Commands built as lists: `["podx-transcode", "--to", fmt, "--outdir", str(wd)]`
2. Execution via `_run()` helper (lines 73-121)
3. JSON stdin/stdout communication
4. Resume detection via artifact scanning
5. Interactive UI flows interspersed with logic

---

## Extraction Strategy

### Phase 1: Extract CommandBuilder ✅
**Goal:** Create fluent interface for building CLI commands
**Effort:** ~2 days
**Risk:** Low (no behavioral changes)

**Target Structure:**
```
podx/
├── services/
│   ├── __init__.py
│   └── command_builder.py
```

**Example Usage:**
```python
# Before
cmd = ["podx-transcode", "--to", fmt, "--outdir", str(wd)]
audio = _run(cmd, stdin_payload=meta)

# After
cmd = (CommandBuilder("podx-transcode")
    .add_option("--to", fmt)
    .add_option("--outdir", str(wd))
    .build())
audio = _run(cmd, stdin_payload=meta)
```

**Benefits:**
- Type-safe command building
- Easier to test command construction
- Clearer intent in code
- Foundation for StepExecutor

---

### Phase 2: Extract SubprocessExecutor
**Goal:** Move _run() logic into adapter with abstract interface
**Effort:** ~2 days
**Risk:** Low (encapsulation only)

**Target Structure:**
```
podx/
├── adapters/
│   ├── __init__.py
│   ├── command_executor.py      # Abstract interface
│   └── subprocess_executor.py   # Production implementation
```

**Example Usage:**
```python
# Before
audio = _run(cmd, stdin_payload=meta, verbose=verbose, save_to=file)

# After
executor = SubprocessExecutor()
audio = executor.execute(
    cmd,
    stdin_payload=meta,
    verbose=verbose,
    save_to=file
)
```

**Benefits:**
- Testable with MockExecutor
- Clear interface contract
- Separates execution from building

---

### Phase 3: Extract StepExecutor
**Goal:** Create service methods for each pipeline step
**Effort:** ~3 days
**Risk:** Medium (more complex extraction)

**Target Structure:**
```
podx/
├── services/
│   ├── step_executor.py         # Pipeline step execution
```

**Example Usage:**
```python
# Before
audio = _run(
    ["podx-transcode", "--to", fmt, "--outdir", str(wd)],
    stdin_payload=meta,
    verbose=verbose,
    save_to=audio_meta_file
)

# After
executor = StepExecutor(command_executor, verbose=verbose)
audio = executor.transcode(
    meta=meta,
    format=fmt,
    output_dir=wd,
    save_to=audio_meta_file
)
```

**Benefits:**
- Encapsulates step logic
- Type-safe parameters
- Easier unit testing
- Single responsibility

---

### Phase 4: Extract PipelineService
**Goal:** Extract business logic from run() into service
**Effort:** ~4 days
**Risk:** High (largest refactoring)

**Target Structure:**
```
podx/
├── services/
│   ├── pipeline_service.py      # Core orchestration logic
```

**Example Usage:**
```python
# orchestrate.py::run() becomes thin wrapper
def run(...):  # All CLI args preserved
    # 1. Build config from CLI args
    config = _build_pipeline_config(align, diarize, deepcast, ...)

    # 2. Handle interactive selection
    working_dir, resume_state = _handle_interactive_mode(
        interactive_select, scan_dir, show, workdir
    )

    # 3. Execute pipeline
    service = PipelineService(
        executor=SubprocessExecutor(),
        state_manager=StateManager(working_dir)
    )
    result = service.execute(config, working_dir, resume=resume_state)

    # 4. Display results
    _display_results(result)
```

**Benefits:**
- Business logic fully testable
- Clear separation of concerns
- Enables API/library usage
- Dramatically improves maintainability

---

### Phase 5: Refactor orchestrate.py
**Goal:** Make run() a thin CLI wrapper
**Effort:** ~2 days
**Risk:** Low (mechanical refactoring)

**Target:** orchestrate.py < 400 lines

**Structure:**
- CLI decorator + argument parsing (~100 LOC)
- Config building helper (~50 LOC)
- Interactive mode handler (~100 LOC)
- Service invocation (~50 LOC)
- Results display (~50 LOC)

---

### Phase 6: Add Comprehensive Tests
**Goal:** 80%+ test coverage for new modules
**Effort:** ~3 days
**Risk:** Low

**Test Coverage Targets:**
- CommandBuilder: 100%
- SubprocessExecutor: 90%
- StepExecutor: 90%
- PipelineService: 85%

**Test Structure:**
```
tests/
├── unit/
│   ├── services/
│   │   ├── test_command_builder.py
│   │   ├── test_step_executor.py
│   │   └── test_pipeline_service.py
│   └── adapters/
│       └── test_subprocess_executor.py
├── integration/
│   └── test_orchestrate_integration.py
```

---

## Success Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| orchestrate.py LOC | 2,354 | <400 | 🔄 |
| Largest function | 1,159 | <100 | 🔄 |
| Unit test coverage | ~20% | 80%+ | 🔄 |
| Testable business logic | 0% | 100% | 🔄 |

---

## Risk Mitigation

1. **Preserve Backward Compatibility**
   - All CLI arguments unchanged
   - JSON schemas unchanged
   - State file format unchanged

2. **Testing Strategy**
   - Run full test suite after each phase
   - Add integration tests before extraction
   - Compare outputs before/after

3. **Incremental Deployment**
   - Each phase is independently deployable
   - Can rollback at phase boundaries
   - Feature flags for new code paths

---

## Timeline

- **Phase 1:** 2 days (CommandBuilder)
- **Phase 2:** 2 days (SubprocessExecutor)
- **Phase 3:** 3 days (StepExecutor)
- **Phase 4:** 4 days (PipelineService)
- **Phase 5:** 2 days (Refactor orchestrate.py)
- **Phase 6:** 3 days (Tests)

**Total:** 16 days (aggressive) to 30 days (sustainable)

---

## Phase 1 Details: CommandBuilder

**Files to Create:**
- `podx/services/__init__.py`
- `podx/services/command_builder.py`

**Implementation:**
```python
class CommandBuilder:
    """Fluent interface for building CLI commands."""

    def __init__(self, command: str):
        self.parts: List[str] = [command]

    def add_option(self, flag: str, value: Optional[str] = None) -> "CommandBuilder":
        """Add --flag value to command."""
        self.parts.append(flag)
        if value is not None:
            self.parts.append(str(value))
        return self

    def add_flag(self, flag: str) -> "CommandBuilder":
        """Add boolean flag to command."""
        self.parts.append(flag)
        return self

    def build(self) -> List[str]:
        """Return final command list."""
        return self.parts
```

**Usage Locations to Update:**
- Line 708: fetch command
- Line 812: transcode command
- Line 881: transcribe command
- Lines 909, 922: dual transcribe commands
- Line 952, 958, 970: preprocess commands
- Line 1020: align command
- Line 1073: diarize command
- Line 1091: export command
- Line 1402: deepcast command

**Testing:**
```python
def test_command_builder_basic():
    cmd = CommandBuilder("podx-transcode")
    .add_option("--to", "wav16")
    .add_option("--outdir", "/tmp/test")
    .build()

    assert cmd == ["podx-transcode", "--to", "wav16", "--outdir", "/tmp/test"]
```

---

## Completed Work

### ✅ Phase 1-4: Services Extracted (Previously Completed)

**What Exists:**
1. **podx/services/command_builder.py** (75 lines)
   - `CommandBuilder` class with fluent interface
   - Methods: `add_option()`, `add_flag()`, `add_options()`, `build()`
   - Example: `CommandBuilder("podx-fetch").add_option("--show", "Podcast").build()`

2. **podx/services/step_executor.py** (430+ lines)
   - `StepExecutor` class for running individual pipeline steps
   - Methods: `fetch()`, `transcode()`, `transcribe()`, `align()`, `diarize()`, `preprocess()`, `deepcast()`, `export()`, `notion()`
   - Encapsulates `_run()` logic with proper error handling

3. **podx/services/pipeline_service.py** (680+ lines)
   - `PipelineConfig` dataclass (all configuration in one place)
   - `PipelineResult` dataclass (execution results)
   - `PipelineService` class with `execute()` method
   - State management with `ArtifactDetector`
   - Resume support built-in

**How Services Work:**
```python
# Configuration from CLI args
config = PipelineConfig(
    show="My Podcast",
    align=True,
    deepcast=True,
    model="large-v3",
    # ... all other settings
)

# Execute pipeline
service = PipelineService(config)
result = service.execute(
    skip_completed=True,
    progress_callback=my_callback
)

# Result contains all artifacts
print(result.workdir)
print(result.artifacts)
print(result.duration)
```

---

## Next Steps

### 🔄 Phase 5: Integration Analysis (IN PROGRESS)

**Goal:** Determine how to integrate services into orchestrate.py::run()

**Progress:**
1. ✅ Document existing services (this file)
2. ✅ Commit current state (safe checkpoint)
3. ✅ Analyze PipelineService compatibility with run()
4. 🔄 Document compatibility issues found
5. 🔄 Decide integration strategy
6. 🔄 Implement chosen strategy

---

## Compatibility Analysis

### 🔍 PipelineService vs run() Function Comparison

**Current run() Function Structure (orchestrate.py:456-1219, ~764 lines):**

```python
def run(...):  # 38 CLI parameters
    # 1. Variable initialization (lines 456-461)
    selected = None
    chosen_type = None
    preview = ""
    yaml_analysis_type = None

    # 2. Preset handling (lines 463-497)
    if full: align=True, deepcast=True, extract_markdown=True, notion=True
    if workflow: apply_workflow_preset(workflow)
    if fidelity: apply_fidelity_preset(fidelity, preset)

    # 3. Start execution (lines 498-509)
    print_podx_header()
    start_time = time.time()
    results = {}
    with PodxProgress() as progress:
        wd = None  # Determined after fetch

        # 4. INTERACTIVE MODE (lines 511-597) ⚠️ NOT IN PipelineService
        if interactive_select:
            # 4a. Episode selection with rich table UI
            selected, meta = select_episode_interactive(scan_dir, show, console)

            # 4b. Fidelity choice (1-5) with detailed panel
            console.print(Panel(help_text, title="Choose Fidelity (1-5)"))
            fchoice = input("Choose preset [1-5]: ")
            fid_flags = apply_fidelity_preset(fidelity, preset, interactive=True)
            align, diarize, preprocess, restore, deepcast, dual = ...

            # 4c. Model selection prompts
            prompt_asr = input(f"ASR model (Enter to keep '{model}'): ")
            prompt_ai = input(f"AI model (Enter to keep '{deepcast_model}'): ")

            # 4d. Toggle options panel
            align = Confirmation.yes_no("Align (WhisperX)", align)
            diarize = Confirmation.yes_no("Diarize (speaker labels)", diarize)
            preprocess = Confirmation.yes_no("Preprocess (merge/normalize)", preprocess)
            restore = Confirmation.yes_no("Semantic restore (LLM)", restore)
            deepcast = Confirmation.yes_no("Deepcast (AI analysis)", deepcast)
            dual = Confirmation.yes_no("Dual mode (precision+recall)", dual)
            extract_markdown = Confirmation.yes_no("Save Markdown file", extract_markdown)
            deepcast_pdf = Confirmation.yes_no("Also render PDF (pandoc)", deepcast_pdf)

            # 4e. Deepcast type selection
            chosen_type = select_deepcast_type(console, default_type=yaml_analysis_type)

            # 4f. Pipeline preview with cost estimate
            stages = ["fetch", "transcode", "transcribe", ...]
            if align: stages.append("align")
            # ... build preview, show cost estimate

            # 4g. Final confirmation
            proceed = input("Proceed? [y/N]: ")

        # 5. Execution (lines 652+)
        # ... actual pipeline steps
```

**PipelineService.execute() Structure (pipeline_service.py:126-205, ~80 lines):**

```python
def execute(self, skip_completed=True, progress_callback=None) -> PipelineResult:
    start_time = time.time()
    result = PipelineResult(workdir=Path("."))

    try:
        # 1. Fetch episode metadata (ALWAYS CALLS FETCH)
        meta = self._execute_fetch(result, progress_callback)

        # 2. Determine working directory (NEW GENERATION ONLY)
        workdir = self._determine_workdir(meta)
        result.workdir = workdir
        workdir.mkdir(parents=True, exist_ok=True)

        # 3. Save metadata
        (workdir / "episode-meta.json").write_text(json.dumps(meta, indent=2))

        # 4. Initialize state management
        detector = ArtifactDetector(workdir)
        artifacts = detector.detect_all()

        # 5. Execute pipeline steps
        self._execute_transcode(workdir, meta, artifacts, result, progress_callback)
        latest = self._execute_transcribe(workdir, artifacts, result, skip_completed, progress_callback)
        latest = self._execute_preprocess(workdir, latest, artifacts, result, skip_completed, progress_callback)
        latest = self._execute_align(workdir, latest, artifacts, result, skip_completed, progress_callback)
        latest = self._execute_diarize(workdir, latest, artifacts, result, skip_completed, progress_callback)

        # 6. Export, deepcast, notion
        self._execute_export(workdir, latest, result, progress_callback)
        if self.config.deepcast or self.config.dual:
            self._execute_deepcast(workdir, latest, result, progress_callback)  # ⚠️ SIMPLIFIED
        if self.config.notion and not self.config.dual:
            self._execute_notion(workdir, result, progress_callback)

        # 7. Cleanup
        if self.config.clean:
            self._execute_cleanup(workdir, result, progress_callback)

        result.duration = time.time() - start_time

    except Exception as e:
        result.errors.append(str(e))
        raise

    return result
```

---

### ⚠️ Critical Compatibility Issues

| Issue | Current run() | PipelineService | Impact |
|-------|---------------|-----------------|--------|
| **Interactive Mode** | Lines 511-597 (~87 lines) | ❌ Not supported | BLOCKER |
| **Metadata Source** | Can use existing episode-meta.json | ✅ Always calls fetch | Major |
| **Workdir Handling** | From selected episode OR generated | Only generated from meta | Major |
| **Dual Mode** | Full support with dual transcription | ⚠️ Simplified (line 566 comment) | Major |
| **Consensus** | Generates consensus/agreement artifacts | ❌ No support | Major |
| **Analysis Type** | Interactive selection via select_deepcast_type() | config.analysis_type exists but unused | Medium |
| **Cost Preview** | Shows estimated cost before execution | ❌ No preview | Medium |
| **Final Confirmation** | "Proceed? [y/N]" prompt | ❌ No confirmation | Medium |

**Detailed Issues:**

**1. Interactive Mode (BLOCKER)**
- Current run() has extensive interactive UI (87 lines):
  - Episode selection from scanned directories
  - Paginated table with rich formatting
  - Fidelity choice (1-5) with detailed help
  - Model selection prompts
  - Boolean option toggles
  - Deepcast type selection
  - Pipeline preview with stages
  - Cost estimation
  - Final confirmation prompt
- PipelineService has NONE of this - it's designed for programmatic use

**2. Metadata Source Mismatch**
- Interactive mode loads metadata from selected episode's `episode-meta.json`
- PipelineService._execute_fetch() ALWAYS calls executor.fetch() for new episodes
- No way to pass pre-loaded metadata to PipelineService.execute()

**3. Workdir Handling**
- Interactive mode: workdir = selected["directory"] (existing episode folder)
- PipelineService._determine_workdir(): generates new workdir from show name + date
- Cannot process existing episodes via PipelineService

**4. Dual Mode Incomplete**
- Current run() supports full dual mode:
  - Transcribe with both precision and recall presets
  - Preprocess both transcripts
  - Generate deepcasts for both
  - Create agreement/consensus artifacts
  - Special handling throughout pipeline
- PipelineService._execute_deepcast() has comment "Simplified version - full implementation would handle dual mode"
- PipelineService._execute_transcribe() doesn't handle dual transcription

**5. Missing Consensus Support**
- Dual mode generates agreement-*.json and consensus-*.json artifacts
- PipelineService has no code for consensus workflow
- ArtifactDetector detects these files but PipelineService doesn't create them

---

### 🔀 Integration Strategy Options

**Option 1: Extend PipelineService (HIGH EFFORT)**
- Add interactive mode support to PipelineService
- Add metadata injection (skip fetch)
- Add existing workdir support
- Complete dual mode implementation
- Add consensus support
- **Pros:** Full service-based architecture
- **Cons:** ~2-3 weeks work, high risk, mixes UI concerns into service

**Option 2: Hybrid Approach (RECOMMENDED)**
- Keep orchestrate.py for CLI/UI/interactive concerns
- Use PipelineService ONLY for programmatic/API usage
- Extract helper functions in orchestrate.py:
  - `_build_pipeline_config()` - convert CLI args to config
  - `_handle_interactive_mode()` - all interactive UI logic
  - `_execute_pipeline()` - direct subprocess execution (existing flow)
- **Pros:** Clean separation, low risk, incremental improvement
- **Cons:** orchestrate.py still ~1500 lines (down from 2354)

**Option 3: Create CLIPipelineService (MEDIUM EFFORT)**
- New service that wraps PipelineService
- Adds CLI-specific features:
  - Interactive mode support
  - Pre-loaded metadata handling
  - Existing workdir support
  - Full dual mode
  - Consensus support
- orchestrate.py becomes thin wrapper around CLIPipelineService
- **Pros:** Testable business logic, cleaner than Option 1
- **Cons:** ~1-2 weeks work, two service layers

---

### ✅ Recommended Strategy: Option 2 (Hybrid Approach)

**Rationale:**
1. **PipelineService is well-designed for programmatic use** - Don't pollute it with CLI/UI concerns
2. **Interactive mode is inherently CLI-specific** - Belongs in orchestrate.py, not in service layer
3. **Dual mode is complex** - Current implementation works, don't rush to extract it
4. **Clean separation of concerns:**
   - `PipelineService` → Programmatic/API usage (future Python library)
   - `orchestrate.py` → CLI/UI/interactive features
5. **Low risk, incremental improvement** - Can extract more to services later

**Implementation Plan:**

Extract 2 helper functions from run(), keeping pipeline execution in place:

1. **`_build_pipeline_config()`** - Convert CLI args to config dict (~80 lines)
2. **`_handle_interactive_mode()`** - All interactive UI logic (~120 lines)

Keep existing pipeline execution code (dual mode, consensus, etc.) in run() for now.

**Benefits:**
- ✅ Reduces orchestrate.py from 2,354 → ~1,200 lines (49% reduction)
- ✅ Extracts 2 testable helper functions (~200 lines)
- ✅ Clean separation: config building + interactive mode extracted
- ✅ Zero risk - keeps working dual mode implementation
- ✅ PipelineService remains clean for future API/library use
- ✅ Can incrementally extract more later (dual mode, consensus, etc.)

**Metrics After Hybrid Approach:**

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| orchestrate.py LOC | 2,354 | ~1,200 | -49% |
| Largest function | 764 | ~550 | -28% |
| Testable helpers | 0 | 2 | +100% |
| Service layer | Unused | Ready for API | ✅ |

**Next Steps if Approved:**
1. Extract `_build_pipeline_config()` helper
2. Extract `_handle_interactive_mode()` helper
3. Refactor run() to use helpers
4. Test thoroughly
5. Commit hybrid approach
6. (Future) Incrementally extract dual mode to service layer

---

### ⏳ Phase 6: Testing

**Goal:** 80%+ test coverage for services

**Tests Needed:**
- `tests/unit/services/test_command_builder.py`
- `tests/unit/services/test_step_executor.py`
- `tests/unit/services/test_pipeline_service.py`
- `tests/integration/test_orchestrate_integration.py`

---

## Current Status Summary

| Component | Status | Location | Lines | Notes |
|-----------|--------|----------|-------|-------|
| CommandBuilder | ✅ Complete | services/command_builder.py | 75 | Ready to use |
| StepExecutor | ✅ Complete | services/step_executor.py | 430 | Ready to use |
| PipelineService | ✅ Complete | services/pipeline_service.py | 680 | Ready to use |
| orchestrate.py | 🔄 Pending | orchestrate.py | 2,354 | Needs integration |
| Unit Tests | ❌ Missing | tests/unit/services/ | 0 | Phase 6 |
| Integration Tests | ❌ Missing | tests/integration/ | 0 | Phase 6 |

---

## Risk Assessment

**Low Risk (Safe to proceed):**
- Services are well-designed and isolated
- All CLI arguments remain unchanged
- JSON schemas remain unchanged
- Existing tests can validate behavior

**Medium Risk (Requires care):**
- Interactive mode integration (complex UI flows)
- Resume logic (state management)
- Error handling edge cases
- Progress callback wiring

**Mitigation:**
- Test each helper function independently
- Compare outputs before/after integration
- Keep old run() in git history for reference
- Deploy to staging first
