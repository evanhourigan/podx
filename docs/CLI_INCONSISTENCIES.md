# Podx CLI Inconsistencies Analysis

**Generated:** 2025-10-19
**Purpose:** Comprehensive audit of all podx CLI commands to identify and fix inconsistencies

---

## Executive Summary

The podx codebase implements **17 console entry points** with a composable architecture where commands chain together via JSON I/O. After comprehensive analysis, we've identified **3 critical inconsistencies**, **5 minor issues**, but also **strong consistency** in many areas (scan-dir pattern, environment variables, interactive mode support).

### Critical Issues Found
1. ❌ **Input flag naming:** `podx-preprocess` uses `--input` without `-i` short form (all others use `-i`)
2. ❌ **Mixed input patterns:** `podx-agreement` uses `--a/--b`, `podx-consensus` uses `--precision/--recall/--input`
3. ❌ **Interactive output behavior:** Inconsistent JSON output in interactive mode across commands

### Strengths
✅ Excellent `--scan-dir` consistency across all scanning commands
✅ Strong environment variable pattern
✅ Interactive mode widely supported (14/17 commands)
✅ Smart file discovery and resumption logic

---

## Table of Contents
- [Complete Command Inventory](#complete-command-inventory)
- [Detailed Inconsistencies](#detailed-inconsistencies)
- [Recommended Fixes](#recommended-fixes)
- [Fix Plan](#fix-plan)

---

## Complete Command Inventory

### Entry Points (from pyproject.toml)

| Command | Entry Point | Purpose | Interactive | Input | Output |
|---------|-------------|---------|-------------|-------|--------|
| `podx` | `podx.orchestrate:main` | Main orchestrator with subcommands | ✓ (run) | Various | Various |
| `podx-fetch` | `podx.fetch:main` | Episode metadata fetcher | ✓ | API/RSS | `-o` JSON |
| `podx-transcode` | `podx.transcode:main` | Audio transcoder | ✓ | `-i` | `-o` JSON |
| `podx-transcribe` | `podx.transcribe:main` | ASR transcription | ✓ | `-i` | `-o` JSON |
| `podx-align` | `podx.align:main` | Word-level alignment | ✓ | `-i` | `-o` JSON |
| `podx-diarize` | `podx.diarize:main` | Speaker diarization | ✓ | `-i` | `-o` JSON |
| `podx-export` | `podx.export:main` | Export to formats | ✓ | `-i` | `-o` JSON |
| `podx-deepcast` | `podx.deepcast:main` | LLM analysis | ✓ | `-i` | `-o` JSON |
| `podx-notion` | `podx.notion:main` | Notion integration | ✓ | `-i` | stdout JSON |
| `podx-preprocess` | `podx.preprocess:main` | Transcript preprocessing | ✓ | `--input` ⚠️ | `--output` ⚠️ |
| `podx-agreement` | `podx.agreement:main` | Compare analyses | ✓ | `--a/--b` ⚠️ | stdout JSON |
| `podx-consensus` | `podx.consensus:main` | Merge precision/recall | ✓ | `--precision/--recall/-i` ⚠️ | `-o` JSON |
| `podx-models` | `podx.models:main` | List AI models & pricing | TTY | — | JSON/Table |
| `podx-list` | `podx.list:main` | Browse episodes | ✓ | — | Table only |

**Legend:**
- ✓ = Feature present and consistent
- ⚠️ = Inconsistency identified
- — = Not applicable

---

## Detailed Inconsistencies

### 1. Input/Output Flag Inconsistencies

#### Pattern Standard (Expected)
Most commands follow this pattern:
```bash
--input, -i PATH     # Read input JSON from file instead of stdin
--output, -o PATH    # Save output JSON to file (also prints to stdout)
```

#### Violations

**podx-preprocess** (❌ CRITICAL)
```python
# Current (inconsistent):
--input PATH         # Missing -i short form
--output PATH        # Missing -o short form

# Expected:
--input, -i PATH
--output, -o PATH
```

**podx-agreement** (❌ CRITICAL)
```python
# Current (inconsistent):
--a PATH             # First deepcast JSON
--b PATH             # Second deepcast JSON

# Expected (two options):
# Option A: Structured input
--input, -i PATH     # JSON: {"a": "path1", "b": "path2"}

# Option B: Named inputs (keep but add consistency)
--first, -a PATH
--second, -b PATH
```

**podx-consensus** (❌ CRITICAL)
```python
# Current (inconsistent):
--precision PATH     # Precision deepcast JSON
--recall PATH        # Recall deepcast JSON
--input, -i PATH     # Alternative: read both from structured JSON

# Expected (two options):
# Option A: Keep named but add short forms
--precision, -p PATH
--recall, -r PATH

# Option B: Structured input only
--input, -i PATH     # JSON: {"precision": "path1", "recall": "path2", "agreement": "path3"}
```

**podx-notion** (⚠️ MINOR)
```python
# Current:
--input, -i PATH     # ✓ Has input
# No --output flag    # Returns page_id to stdout

# Recommendation:
--output, -o PATH    # Optional: save summary JSON
```

**Files:**
- `/Users/evan/code/podx/podx/preprocess.py:51-52`
- `/Users/evan/code/podx/podx/agreement.py:19-20`
- `/Users/evan/code/podx/podx/consensus.py:27-29`

---

### 2. Interactive Mode Output Behavior

#### Current Inconsistencies

| Command | Interactive Stdout | File Save | User Messages |
|---------|-------------------|-----------|---------------|
| `podx-fetch` | ❌ None | ✓ `episode-meta.json` | ✓ Rich output |
| `podx-transcode` | ❌ None | ✓ `audio-meta.json` | ✓ Rich output |
| `podx-transcribe` | ❌ None | ✓ `transcript-*.json` | ✓ Rich output |
| `podx-align` | ❌ None | ✓ `transcript-aligned-*.json` | ✓ Rich output |
| `podx-diarize` | ❌ None | ✓ `transcript-diarized-*.json` | ✓ Rich output |
| `podx-export` | ⚠️ Sometimes | ✓ `exported-*.md` | ✓ Rich output |
| `podx-deepcast` | ⚠️ Sometimes | ✓ `deepcast-*.json` | ✓ Rich output |
| `podx-notion` | ✓ Success msg | ❌ None (optional) | ✓ Rich output |
| `podx-preprocess` | ❌ None | ✓ `transcript-preprocessed-*.json` | ✓ Rich output |

**Recommendation:** Standardize on **NO JSON to stdout in interactive mode**
- Interactive mode: Rich user-friendly output + file save
- Non-interactive mode: JSON to stdout + optional file save with `-o`

**Files:**
- `/Users/evan/code/podx/podx/export.py:220-350` (interactive mode)
- `/Users/evan/code/podx/podx/deepcast.py:180-280` (interactive mode)

---

### 3. Model Flag Ambiguity

#### Current Usage

| Command | Flag | Meaning |
|---------|------|---------|
| `podx-transcribe` | `--model` | ASR model (whisper variants) |
| `podx-deepcast` | `--model` | LLM model (gpt-4.1, etc.) |
| `podx-agreement` | `--model` | LLM model for comparison |
| `podx-preprocess` | `--restore-model` | LLM model for restoration |
| `podx run` | `--model` | ASR model |
| `podx run` | `--deepcast-model` | LLM model |

**Confusion:** `--model` means different things in different commands

**Options:**
1. **Keep current pattern** but improve help text clarity
2. **Rename to be explicit:**
   - `--asr-model` for transcription commands
   - `--llm-model` for analysis commands

**Recommendation:** Keep current pattern (less breaking change), but add help text like:
```python
# podx-transcribe
--model TEXT  # ASR model: tiny, small, medium, large, large-v3-turbo, etc.

# podx-deepcast
--model TEXT  # LLM model: gpt-4.1, gpt-4.1-mini, gpt-4o, etc.
```

---

### 4. Filename Convention Variations

#### Current Patterns

**Consistent Pattern** (✓ GOOD):
```
episode-meta.json              # Fetch output
audio-meta.json                # Transcode output
transcript-{model}.json        # Transcribe output
transcript-aligned-{model}.json    # Align output (NEW)
transcript-diarized-{model}.json   # Diarize output (NEW)
transcript-preprocessed-{asr}.json # Preprocess output
```

**Complex Patterns** (⚠️ VARIES):
```
deepcast-{asr}-{ai}-{type}-{timestamp}.json    # Deepcast output
consensus-{asr}-{ai}.json                      # Consensus output
agreement-*.json                               # Agreement output (less specific)
exported-{track}-{timestamp}.md                # Export markdown
```

**Legacy Support** (still detected):
```
transcript.json                    # Old single transcript
aligned-transcript-*.json          # Old align format
deepcast-brief-{ai}.json          # Old deepcast format
```

**Issues:**
- Agreement has no specific naming pattern
- Consensus doesn't include timestamp (but deepcast does)
- Export uses "track" but could be more descriptive

**Recommendation:**
1. Keep current patterns for stability
2. Document canonical format in code comments
3. Phase out legacy format support in v2.0

---

### 5. Return Schema Documentation

#### Current State

Most commands return JSON but schemas are not explicitly documented in:
- Docstrings
- Type hints
- Validation decorators

**Example from `podx-deepcast`:**
```python
def main(inp, output, model, temperature, ...):
    """Run deepcast analysis on a transcript."""
    # Returns complex nested JSON but schema not documented in function
```

**Recommendation:**
1. Add Pydantic models for all return types (already exists in `podx/schemas.py`, but not enforced)
2. Use type hints: `def main(...) -> DeepcastBrief:`
3. Add docstring section documenting return schema

---

### 6. Scan Directory Consistency

#### Assessment: ✅ EXCELLENT

All scanning commands use consistent pattern:
```python
--scan-dir PATH    # Directory to scan for episodes (default: .)
```

**Commands using this:**
- transcode, transcribe, align, diarize, export, deepcast, preprocess, agreement, consensus, list, notion

**Type:** Always `Path`
**Default:** Always `.` (current directory)

**No changes needed** - this is a model of consistency!

---

### 7. Environment Variable Usage

#### Assessment: ✅ GOOD

**Required Variables:**
```bash
OPENAI_API_KEY         # deepcast, agreement, preprocess --restore
NOTION_TOKEN           # notion
HUGGINGFACE_TOKEN      # diarize
```

**Optional Defaults:**
```bash
OPENAI_BASE_URL        # deepcast (custom endpoint)
OPENAI_MODEL           # deepcast --model default
OPENAI_TEMPERATURE     # deepcast --temperature default
NOTION_DB_ID           # notion --db default
NOTION_PODCAST_PROP    # notion --podcast-prop default
NOTION_DATE_PROP       # notion --date-prop default
NOTION_EPISODE_PROP    # notion --episode-prop default
PODX_CHROME_BIN        # export PDF (chrome path)
```

**Recommendation:** No changes needed - well-documented and consistent

---

## Recommended Fixes

### High Priority (Breaking Changes)

#### 1. Standardize Input/Output Flags

**File:** `podx/preprocess.py`
```python
# Before:
@click.option("--input", type=click.Path(exists=True), help="...")
@click.option("--output", type=click.Path(), help="...")

# After:
@click.option("--input", "-i", type=click.Path(exists=True), help="...")
@click.option("--output", "-o", type=click.Path(), help="...")
```

**File:** `podx/agreement.py`
```python
# Option A: Structured input (RECOMMENDED)
@click.option("--input", "-i", type=click.Path(exists=True),
              help="JSON with keys: 'a' (first analysis) and 'b' (second analysis)")
# Keep --a and --b as shortcuts that build the structure

# Option B: Add short forms only
@click.option("--first", "-a", "a", type=click.Path(exists=True), help="...")
@click.option("--second", "-b", "b", type=click.Path(exists=True), help="...")
```

**File:** `podx/consensus.py`
```python
# Option A: Keep named but standardize
@click.option("--precision", "-p", type=click.Path(exists=True), help="...")
@click.option("--recall", "-r", type=click.Path(exists=True), help="...")

# Option B: Structured input only (RECOMMENDED)
@click.option("--input", "-i", type=click.Path(exists=True),
              help="JSON with keys: 'precision', 'recall', 'agreement' (optional)")
# Keep individual flags as shortcuts
```

#### 2. Standardize Interactive Mode Output

**Principle:** In interactive mode, NO JSON to stdout, only rich user messages

**Files to update:**
- `podx/export.py:220-350` - Remove JSON output in interactive mode
- `podx/deepcast.py:180-280` - Remove JSON output in interactive mode

**Pattern:**
```python
if interactive:
    # Rich output: tables, progress bars, success messages
    console.print("[green]✓[/green] Analysis complete!")
    console.print(f"Saved to: {output_path}")
    # NO: print(json.dumps(result))
else:
    # JSON to stdout for piping
    print(json.dumps(result, indent=2))
```

#### 3. Add Output Flag to Notion

**File:** `podx/notion.py`
```python
@click.option("--output", "-o", type=click.Path(),
              help="Save summary JSON (page_id, url, properties) to file")

# Implementation:
if output:
    output_path = Path(output)
    output_path.write_text(json.dumps(result, indent=2))
```

---

### Medium Priority (Documentation)

#### 4. Clarify Model Flag in Help Text

**Files:** `podx/transcribe.py`, `podx/deepcast.py`, `podx/agreement.py`

```python
# podx-transcribe
@click.option("--model", default="large-v3-turbo",
              help="ASR model: tiny, small, medium, large, large-v2, large-v3, large-v3-turbo, "
                   "or provider-prefixed (openai:whisper-1, hf:distil-large-v3)")

# podx-deepcast
@click.option("--model", default="gpt-4.1",
              help="LLM model for analysis: gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini, "
                   "claude-4.5-sonnet, etc.")

# podx-agreement
@click.option("--model", default="gpt-4.1",
              help="LLM model for comparison: gpt-4.1, gpt-4.1-mini, gpt-4o, etc.")
```

#### 5. Document Return Schemas

**Pattern to add to all command `main()` functions:**

```python
def main(...) -> dict:
    """
    Run transcription on audio file.

    Args:
        model: ASR model name
        input: Input AudioMeta JSON file (or stdin)
        output: Output Transcript JSON file (or stdout)
        ...

    Returns:
        Transcript JSON with schema:
        {
            "audio_path": str,
            "language": str,
            "asr_model": str,
            "asr_provider": "local" | "openai" | "hf",
            "segments": [
                {"start": float, "end": float, "text": str}
            ],
            "text": str
        }

    Examples:
        $ cat audio-meta.json | podx-transcribe --model large-v3-turbo
        $ podx-transcribe -i audio-meta.json -o transcript.json --model small
    """
```

---

### Low Priority (Future Improvements)

#### 6. Deprecate Legacy Filename Formats

Add warnings when detecting old formats:
```python
if path.name == "transcript.json":
    logger.warning(
        "Legacy filename 'transcript.json' detected. "
        "Please use 'transcript-{model}.json' format."
    )
```

#### 7. Add Schema Validation

Use Pydantic models throughout:
```python
from podx.schemas import Transcript, AudioMeta, EpisodeMeta

def main(...) -> Transcript:
    # ...
    result = Transcript(**data)  # Validates schema
    return result.model_dump()
```

#### 8. Unified Progress Reporting

Create shared progress library:
```python
# podx/ui/progress.py
class PodxProgress:
    """Unified progress reporting for all commands."""

    def start_step(self, name: str):
        """Start a new pipeline step."""

    def complete_step(self, message: str, duration: float):
        """Mark step as complete."""
```

---

## Fix Plan

### Phase 1: Critical Fixes (Breaking Changes - v2.0)

**Estimated Effort:** 4-6 hours

1. **Add `-i` and `-o` short forms to `podx-preprocess`**
   - File: `podx/preprocess.py:51-52`
   - Change: Add `, "-i"` and `, "-o"` to decorators
   - Test: `pytest tests/unit/test_preprocess.py`

2. **Standardize `podx-agreement` inputs**
   - File: `podx/agreement.py:19-25`
   - Change: Add `--input/-i` option, keep `--a/--b` as legacy aliases
   - Test: `pytest tests/unit/test_agreement.py`
   - Document migration in CHANGELOG

3. **Standardize `podx-consensus` inputs**
   - File: `podx/consensus.py:27-35`
   - Change: Add short forms `-p` and `-r`, or unify under `--input/-i`
   - Test: `pytest tests/unit/test_consensus.py`

4. **Remove JSON output in interactive mode**
   - Files: `podx/export.py:220-350`, `podx/deepcast.py:180-280`
   - Change: Wrap `print(json.dumps(...))` in `if not interactive`
   - Test: Manual testing in interactive mode

5. **Add `--output/-o` to `podx-notion`**
   - File: `podx/notion.py:40-50`
   - Change: Add option and save summary JSON
   - Test: `pytest tests/unit/test_notion.py`

**Validation:**
```bash
# Run full test suite
pytest tests/ -v

# Test each modified command manually
podx-preprocess -i transcript.json -o processed.json
podx-agreement --input inputs.json  # where inputs = {"a": "...", "b": "..."}
podx-consensus -p precision.json -r recall.json
podx-export --interactive  # Should NOT print JSON to stdout
podx-notion -i deepcast.json -o notion-result.json
```

---

### Phase 2: Documentation (Non-Breaking)

**Estimated Effort:** 2-3 hours

1. **Clarify `--model` flag help text**
   - Files: `podx/transcribe.py`, `podx/deepcast.py`, `podx/agreement.py`
   - Add specific examples in help text

2. **Add return schema docstrings**
   - Files: All command `main()` functions
   - Add comprehensive docstring with Args, Returns, Examples

3. **Update README.md**
   - Document all commands and their I/O patterns
   - Add "Command Chaining" examples

---

### Phase 3: Future Improvements (v2.1+)

**Estimated Effort:** 8-12 hours

1. **Add deprecation warnings for legacy filenames**
   - Warn on: `transcript.json`, `aligned-transcript-*.json`, `deepcast-brief-*.json`

2. **Enforce Pydantic schema validation**
   - All commands use models from `podx/schemas.py`
   - Add validation to inputs and outputs

3. **Create unified progress library**
   - Extract common progress patterns
   - Use in all commands

4. **Add integration tests**
   - Test command chaining: `podx-fetch | podx-transcode | podx-transcribe`
   - Validate JSON I/O contracts

---

## Migration Guide for Users

### v2.0 Breaking Changes

#### 1. `podx-preprocess` now requires `-i` / `-o` for consistency
```bash
# Before (still works with deprecation warning):
podx-preprocess --input transcript.json --output processed.json

# After (recommended):
podx-preprocess -i transcript.json -o processed.json
```

#### 2. `podx-agreement` now supports structured input
```bash
# Before:
podx-agreement --a deepcast1.json --b deepcast2.json

# After (both work, new way recommended):
echo '{"a": "deepcast1.json", "b": "deepcast2.json"}' | podx-agreement -i -
podx-agreement --a deepcast1.json --b deepcast2.json  # Legacy still works
```

#### 3. Interactive mode no longer prints JSON to stdout
```bash
# Before: Interactive mode printed JSON + rich output (confusing)
podx-export --interactive  # Printed both table and JSON

# After: Interactive mode only shows rich output
podx-export --interactive  # Only shows rich table, saves to file

# Use non-interactive mode for JSON output:
podx-export -i deepcast.json  # Prints JSON to stdout
```

---

## Conclusion

The podx CLI is **generally well-designed** with strong consistency in most areas. The main issues are:
1. Three commands with non-standard input flags (easily fixable)
2. Inconsistent interactive mode output behavior (design decision needed)

The recommended fixes are **low-risk** and can be implemented incrementally. Priority should be:
1. **Phase 1** for consistency and usability
2. **Phase 2** for better developer experience
3. **Phase 3** for long-term maintainability

**Total estimated effort:** 14-21 hours across all phases.
