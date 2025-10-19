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

### 🔄 Phase 5: Integration (IN PROGRESS)

**Goal:** Wire existing services into orchestrate.py::run()

**Approach:**
1. ✅ Document existing services (this file)
2. ✅ Commit current state (safe checkpoint)
3. 🔄 Create `_build_pipeline_config()` helper
4. 🔄 Create `_handle_interactive_mode()` helper
5. 🔄 Replace run() body with service calls
6. 🔄 Test thoroughly
7. 🔄 Commit integrated version

**Target run() Structure (~200 lines):**
```python
def run(...):  # All 38 CLI parameters preserved
    # 1. Build config from args (~50 lines)
    config = _build_pipeline_config(...)

    # 2. Handle interactive mode (~50 lines)
    if interactive_select:
        meta, workdir = _handle_interactive_mode(config, ...)
        config.workdir = workdir

    # 3. Execute via service (~30 lines)
    print_podx_header()
    service = PipelineService(config)

    with PodxProgress() as progress:
        result = service.execute(
            skip_completed=True,
            progress_callback=lambda step, status: progress.update(step, status)
        )

    # 4. Display results (~30 lines)
    print_podx_success(f"Completed in {result.duration}s")
    print(json.dumps(result.to_dict(), indent=2))
```

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
