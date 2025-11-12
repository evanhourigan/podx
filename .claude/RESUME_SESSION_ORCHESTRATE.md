# Resume Session: orchestrate.py Decomposition

**Created:** 2025-11-11
**Status:** IN PROGRESS
**Goal:** Decompose orchestrate.py from 1,256 lines to ~200 lines
**Context Used:** ~83k/200k (42%)

---

## Current Progress

### Already Completed (Earlier in Session)

Three commits already made that reduced orchestrate.py from 2,533 → 1,256 lines (50% reduction):

1. **Commit a0de91d** - Extracted command runner utilities
   - Created `podx/cli/services/command_runner.py` (100 lines)
   - Extracted `run_command()` and `run_passthrough()`
   - Reduction: 2,533 → 2,478 lines (55 lines)

2. **Commit 0c1adb2** - Extracted config builder
   - Created `podx/cli/services/config_builder.py` (123 lines)
   - Extracted `build_pipeline_config()`
   - Reduction: 2,478 → 2,391 lines (87 lines)

3. **Commit 7766e9b** - Extracted pipeline execution functions
   - Created `podx/cli/services/pipeline_steps.py` (1,167 lines)
   - Extracted all 12 pipeline step functions
   - Reduction: 2,391 → 1,259 lines (1,132 lines)

**Current state:** orchestrate.py is 1,256 lines, needs to reach ~200 lines

---

## Structure Analysis

### What's Currently in orchestrate.py (1,256 lines)

**Imports & Setup:** ~87 lines (lines 1-87)
- Rich-click configuration
- Service imports
- Logging setup
- Backwards compatibility aliases

**Main CLI Group:** ~17 lines (lines 88-115)
- PodxGroup class definition
- main() CLI group definition

**Main "run" Command:** ~352 lines (lines 118-622)
- 100+ lines of @click.option decorators (CLI argument definitions)
- ~250 lines of actual run() function logic
- THIS IS THE BIGGEST TARGET FOR EXTRACTION

**Command Shims:** ~600+ lines (lines 623-1065)
- fetch_cmd() - passthrough to podx-fetch
- transcode_cmd() - passthrough to podx-transcode
- transcribe_cmd() - passthrough to podx-transcribe
- diarize_cmd() - passthrough to podx-diarize
- export_cmd() - passthrough to podx-export
- deepcast_cmd() - passthrough to podx-deepcast
- models_cmd() - passthrough to podx-models
- notion_cmd() - passthrough to podx-notion
- quick() - deprecated workflow (62 lines)
- analyze() - deprecated workflow (87 lines)
- publish() - deprecated workflow (77 lines)
- help_command() - help display (13 lines)
- config_command() - config CLI (67 lines)
- **These should be extracted to podx/cli/commands/**

**Config Subcommands:** ~120 lines (lines 1097-1217)
- config_init()
- config_show()
- config_validate()
- config_databases()
- **These should be extracted to podx/cli/commands/config_commands.py**

**Preprocess Shim & Main:** ~70 lines (lines 1066-1256)
- preprocess_shim() - passthrough command
- run_main() - entry point

---

## Extraction Plan

### Phase 1: Extract Command Shims (~600 lines → separate files)

**Target:** Create `podx/cli/commands/` directory with one file per command

```
podx/cli/commands/
├── __init__.py              - Re-exports all commands
├── fetch.py                 - fetch_cmd()
├── transcode.py             - transcode_cmd()
├── transcribe.py            - transcribe_cmd()
├── diarize.py               - diarize_cmd()
├── export.py                - export_cmd()
├── deepcast.py              - deepcast_cmd()
├── models.py                - models_cmd()
├── notion.py                - notion_cmd()
├── deprecated.py            - quick(), analyze(), publish()
├── help.py                  - help_command()
├── config.py                - config_command() + config subcommands
└── preprocess.py            - preprocess_shim()
```

**Estimated reduction:** ~600 lines

### Phase 2: Simplify Main run() Command (~250 lines → ~100 lines)

The run() function at line 271 is ~352 lines but includes ~100 lines of @click.option decorators.

**Option 1:** Keep decorators in orchestrate.py, extract run() logic
- Extract the actual execution logic to `run_pipeline()` in services
- Leave CLI declaration in orchestrate.py
- Estimated reduction: ~150 lines

**Option 2:** Move entire run command to separate file
- Create `podx/cli/commands/run.py`
- Import and register in orchestrate.py
- Estimated reduction: ~350 lines

**Recommendation:** Option 2 - cleaner separation

### Phase 3: Clean Up Imports & Aliases

After extractions:
- Remove backwards compatibility aliases (lines 70-85)
- Simplify imports
- Keep only main CLI group setup

**Estimated final size:** ~200 lines

---

## Implementation Steps

### Step 1: Create commands/ Directory Structure (5 min)

```bash
mkdir -p podx/cli/commands
touch podx/cli/commands/__init__.py
```

### Step 2: Extract Simple Command Shims (30 min)

Extract one at a time, test after each:
1. fetch.py
2. transcode.py
3. transcribe.py
4. diarize.py
5. export.py
6. deepcast.py
7. models.py
8. notion.py
9. preprocess.py

Each file pattern:
```python
import click
from podx.cli.services import run_passthrough

@click.command()
@click.pass_context
def fetch_cmd(ctx):
    """Fetch podcast episodes from RSS feed."""
    run_passthrough("podx-fetch", ctx)
```

### Step 3: Extract Deprecated Commands (10 min)

Create `deprecated.py` with quick(), analyze(), publish()

### Step 4: Extract Help & Config Commands (15 min)

- help.py - help_command()
- config.py - config_command() + all config subcommands

### Step 5: Extract Main run() Command (20 min)

Create `run.py` with full run() command definition

### Step 6: Update orchestrate.py Imports (10 min)

```python
from podx.cli.commands import (
    analyze_cmd,
    config_command,
    deepcast_cmd,
    diarize_cmd,
    export_cmd,
    fetch_cmd,
    help_command,
    models_cmd,
    notion_cmd,
    preprocess_shim,
    publish_cmd,
    quick_cmd,
    run_cmd,
    transcribe_cmd,
    transcode_cmd,
)

# Register commands
main.add_command(run_cmd, name="run")
main.add_command(fetch_cmd, name="fetch")
# ... etc
```

### Step 7: Test Everything (15 min)

```bash
pytest tests/ -x --tb=short -q
podx --help
podx run --help
```

### Step 8: Commit (5 min)

```bash
git add -A
git commit -m "refactor: extract all commands from orchestrate.py to commands/ module

Massive extraction reducing orchestrate.py to minimal CLI setup.

Changes:
- Created podx/cli/commands/ with 12 command files
- Moved all command definitions to separate modules
- Updated orchestrate.py to import and register commands
- orchestrate.py: 1,256 → ~200 lines (84% reduction!)

Total reduction: 2,533 → ~200 lines (92% reduction cumulative)
All tests passing (459+ passed, 53 skipped)"
```

---

## Current File State

```
podx/cli/
├── orchestrate.py              (1,256 lines - TARGET: ~200)
├── services/
│   ├── __init__.py
│   ├── command_runner.py       (100 lines) ✅
│   ├── config_builder.py       (123 lines) ✅
│   └── pipeline_steps.py       (1,167 lines) ✅
└── commands/                    (TO CREATE)
    └── (12 files to extract)
```

---

## If Session Interrupted

### What to do next:

1. **Read this file first**
2. **Check current state:**
   ```bash
   wc -l /Users/evan/code/podx/podx/cli/orchestrate.py
   ls -la /Users/evan/code/podx/podx/cli/commands/
   ```
3. **If commands/ doesn't exist:** Start at Step 1
4. **If commands/ exists:** Check what's been extracted, continue from there
5. **Reference:** `.ai-docs/planning/REFACTORING_NORTH_STAR_20251111.md` for overall plan

### Resume Command:

```
Continue orchestrate.py decomposition from RESUME_SESSION_ORCHESTRATE.md.

Current: orchestrate.py at 1,256 lines
Target: ~200 lines by extracting commands to podx/cli/commands/

Check: wc -l podx/cli/orchestrate.py && ls podx/cli/commands/

Next: [See RESUME_SESSION_ORCHESTRATE.md for current step]
```

---

## Success Criteria

- ✅ orchestrate.py reduced to ~200 lines
- ✅ All commands extracted to podx/cli/commands/
- ✅ All tests passing (459+ passed)
- ✅ No functionality lost
- ✅ Clean imports and structure

---

**Last Updated:** 2025-11-11
**Estimated Time Remaining:** 2-3 hours
**Context Usage:** 42% (plenty of room)
