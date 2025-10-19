# Podx CLI Inconsistencies - Fix Plan

**Version:** 2.0
**Date:** 2025-10-19
**Status:** Ready for Implementation

---

## Overview

This document provides a step-by-step implementation plan to fix CLI inconsistencies identified in `CLI_INCONSISTENCIES.md`. The plan is organized into 3 phases with clear priorities and effort estimates.

**Quick Stats:**
- **Critical Fixes:** 5 issues (4-6 hours)
- **Documentation:** 3 tasks (2-3 hours)
- **Future Improvements:** 4 tasks (8-12 hours)
- **Total Estimated Effort:** 14-21 hours

---

## Phase 1: Critical Fixes (v2.0)

**Priority:** HIGH | **Effort:** 4-6 hours | **Breaking:** YES

These changes standardize the CLI interface for consistency and predictability.

### Fix 1.1: Add `-i` and `-o` Short Forms to `podx-preprocess`

**File:** `podx/preprocess.py`

**Current Code (lines 51-52):**
```python
@click.option("--input", type=click.Path(exists=True), help="...")
@click.option("--output", type=click.Path(), help="...")
```

**Fixed Code:**
```python
@click.option("--input", "-i", type=click.Path(exists=True), help="...")
@click.option("--output", "-o", type=click.Path(), help="...")
```

**Testing:**
```bash
# Test backward compatibility
podx-preprocess --input transcript.json --output processed.json

# Test new short forms
podx-preprocess -i transcript.json -o processed.json

# Test piping
cat transcript.json | podx-preprocess -o processed.json

# Run unit tests
pytest tests/unit/test_preprocess.py -v
```

**Files to Update:**
- `podx/preprocess.py:51-52`
- `docs/PLUGINS.md` (if examples exist)

---

### Fix 1.2: Standardize `podx-agreement` Inputs

**File:** `podx/agreement.py`

**Current Code (lines 19-25):**
```python
@click.option("--a", type=click.Path(exists=True), required=True, help="First deepcast JSON")
@click.option("--b", type=click.Path(exists=True), required=True, help="Second deepcast JSON")
```

**Strategy:** Add `--input/-i` for structured input, keep `--a/--b` as legacy shortcuts

**Fixed Code:**
```python
@click.option("--input", "-i", "input_file", type=click.Path(exists=True),
              help="JSON file with keys: 'a' (first analysis) and 'b' (second analysis)")
@click.option("--a", type=click.Path(exists=True),
              help="First deepcast JSON (shortcut for --input)")
@click.option("--b", type=click.Path(exists=True),
              help="Second deepcast JSON (shortcut for --input)")
@click.option("--interactive", is_flag=True, help="...")
def main(input_file, a, b, interactive, ...):
    """Compare two deepcast analyses."""

    # Priority: input_file > (a and b) > interactive selection
    if input_file:
        with open(input_file) as f:
            inputs = json.load(f)
        a = inputs.get("a")
        b = inputs.get("b")
    elif not (a and b) and not interactive:
        raise click.UsageError("Provide --input, or both --a and --b, or use --interactive")

    # ... rest of implementation
```

**Testing:**
```bash
# Test new structured input
echo '{"a": "deepcast1.json", "b": "deepcast2.json"}' > inputs.json
podx-agreement -i inputs.json

# Test legacy shortcuts (still work)
podx-agreement --a deepcast1.json --b deepcast2.json

# Test piping
echo '{"a": "deep1.json", "b": "deep2.json"}' | podx-agreement -i -

# Run unit tests
pytest tests/unit/test_agreement.py -v
```

**Files to Update:**
- `podx/agreement.py:19-30`
- `podx/agreement.py:main()` function logic

---

### Fix 1.3: Standardize `podx-consensus` Inputs

**File:** `podx/consensus.py`

**Current Code (lines 27-35):**
```python
@click.option("--precision", type=click.Path(exists=True), help="Precision deepcast JSON")
@click.option("--recall", type=click.Path(exists=True), help="Recall deepcast JSON")
@click.option("--agreement", type=click.Path(exists=True), help="Optional agreement JSON")
@click.option("--input", "-i", "input_file", type=click.Path(exists=True),
              help="JSON with keys: precision, recall, agreement")
```

**Issue:** Already has `--input/-i` but also has long-form named options without short forms

**Strategy:** Add short forms `-p` and `-r` for consistency

**Fixed Code:**
```python
@click.option("--precision", "-p", type=click.Path(exists=True),
              help="Precision deepcast JSON (from dual mode)")
@click.option("--recall", "-r", type=click.Path(exists=True),
              help="Recall deepcast JSON (from dual mode)")
@click.option("--agreement", "-a", type=click.Path(exists=True),
              help="Optional agreement JSON to inform confidence scores")
@click.option("--input", "-i", "input_file", type=click.Path(exists=True),
              help="JSON with keys: 'precision', 'recall', 'agreement' (optional)")
```

**Testing:**
```bash
# Test new short forms
podx-consensus -p precision.json -r recall.json -a agreement.json

# Test structured input
echo '{"precision": "p.json", "recall": "r.json"}' | podx-consensus -i -

# Test legacy (long forms still work)
podx-consensus --precision p.json --recall r.json

# Run unit tests
pytest tests/unit/test_consensus.py -v
```

**Files to Update:**
- `podx/consensus.py:27-35`

---

### Fix 1.4: Remove JSON Output in Interactive Mode

**Files:** `podx/export.py`, `podx/deepcast.py`

**Issue:** Some commands print JSON to stdout in interactive mode, creating confusing mixed output

**Principle:** Interactive mode should ONLY show rich user-friendly output, NO JSON to stdout

#### 1.4a: Fix `podx-export` Interactive Mode

**File:** `podx/export.py:220-350`

**Current Pattern:**
```python
if interactive:
    # ... interactive selection ...
    # ... file operations ...
    print(json.dumps(result))  # ❌ REMOVE THIS
```

**Fixed Pattern:**
```python
if interactive:
    # ... interactive selection ...
    # ... file operations ...

    # Rich user output only
    console.print(f"\n[green]✓[/green] Export complete!")
    console.print(f"Markdown: {exported_md}")
    if exported_pdf:
        console.print(f"PDF: {exported_pdf}")

    # NO JSON to stdout in interactive mode
else:
    # Non-interactive: JSON to stdout for piping
    result = {
        "exported_md": str(exported_md),
        "exported_pdf": str(exported_pdf) if exported_pdf else None
    }
    print(json.dumps(result, indent=2))
```

**Search Pattern:** Look for `print(json.dumps` within `if interactive:` blocks

#### 1.4b: Fix `podx-deepcast` Interactive Mode

**File:** `podx/deepcast.py:180-280`

**Same pattern as above**

**Testing:**
```bash
# Interactive mode should NOT print JSON
podx-export --interactive
# Expected: Rich table, confirmation messages only
# Not expected: JSON output

# Non-interactive should print JSON
podx-export -i deepcast.json
# Expected: JSON to stdout

# Test with output redirection
podx-export --interactive > /tmp/test.txt
# /tmp/test.txt should be empty or contain only human-readable output

# Run manual integration tests
pytest tests/integration/test_interactive_modes.py -v
```

**Files to Update:**
- `podx/export.py:220-350`
- `podx/deepcast.py:180-280`
- Any other commands with `print(json.dumps)` in interactive blocks

---

### Fix 1.5: Add `--output/-o` to `podx-notion`

**File:** `podx/notion.py`

**Current Code:**
```python
# No --output option exists
# Only prints to stdout: {"ok": true, "page_id": "..."}
```

**Fixed Code:**
```python
@click.option("--output", "-o", type=click.Path(),
              help="Save summary JSON (page_id, url, properties) to file")
# ... in main():
def main(..., output, ...):
    # ... existing logic ...

    result = {
        "ok": True,
        "page_id": page_id,
        "url": page_url,
        "properties": properties_set,
        "blocks_written": block_count
    }

    # Save to file if requested
    if output:
        Path(output).write_text(json.dumps(result, indent=2))

    # Always print to stdout (unless interactive)
    if not interactive:
        print(json.dumps(result, indent=2))
    else:
        console.print(f"[green]✓[/green] Page created: {page_url}")
```

**Testing:**
```bash
# Test with output file
podx-notion -i deepcast.json --db MY_DB_ID -o notion-result.json
cat notion-result.json  # Should contain page_id, url, etc.

# Test without output (still prints to stdout)
podx-notion -i deepcast.json --db MY_DB_ID

# Test interactive mode (no stdout JSON)
podx-notion --interactive

# Run unit tests
pytest tests/unit/test_notion.py -v
```

**Files to Update:**
- `podx/notion.py:40-50` (add option)
- `podx/notion.py:main()` function (add output logic)

---

## Phase 2: Documentation Improvements (v2.0)

**Priority:** MEDIUM | **Effort:** 2-3 hours | **Breaking:** NO

These changes improve usability without breaking existing functionality.

### Doc 2.1: Clarify `--model` Flag in Help Text

**Issue:** `--model` means different things in different commands (ASR model vs LLM model)

**Files to Update:**
- `podx/transcribe.py`
- `podx/deepcast.py`
- `podx/agreement.py`
- `podx/preprocess.py`

**Pattern:**

```python
# Before:
@click.option("--model", default="large-v3-turbo", help="Model to use")

# After:
@click.option("--model", default="large-v3-turbo",
              help="ASR model: tiny, small, medium, large, large-v2, large-v3, large-v3-turbo, "
                   "or provider-prefixed (openai:whisper-1, hf:distil-large-v3)")
```

**For LLM commands:**
```python
@click.option("--model", default="gpt-4.1",
              help="LLM model for analysis: gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini, "
                   "claude-4.5-sonnet, etc. See 'podx-models' for full list.")
```

**Testing:** Manual review of `--help` output

```bash
podx-transcribe --help  # Should clearly say "ASR model"
podx-deepcast --help    # Should clearly say "LLM model"
podx-agreement --help   # Should clearly say "LLM model for comparison"
```

---

### Doc 2.2: Add Return Schema Documentation

**Pattern to apply to all command `main()` functions:**

```python
def main(input, output, model, ...) -> dict:
    """
    Run transcription on audio file.

    Args:
        input: Path to AudioMeta JSON file (or stdin if not specified)
        output: Path to save Transcript JSON (or stdout if not specified)
        model: ASR model name (e.g., large-v3-turbo, small.en)
        asr_provider: ASR provider (auto, local, openai, hf)
        preset: High-level decoding preset (balanced, precision, recall)
        compute: Compute type (int8, float16, float32)
        interactive: Enable interactive episode browser
        scan_dir: Directory to scan for episodes (default: current directory)

    Returns:
        Transcript JSON with schema:
        {
            "audio_path": str,              # Absolute path to audio file
            "language": str,                # Detected language (ISO 639-1)
            "asr_model": str,               # Model used (e.g., large-v3-turbo)
            "asr_provider": str,            # Provider (local, openai, hf)
            "preset": str | None,           # Preset used (if any)
            "decoder_options": dict,        # Decoder configuration
            "segments": [                   # Transcript segments
                {
                    "start": float,         # Start time (seconds)
                    "end": float,           # End time (seconds)
                    "text": str             # Segment text
                }
            ],
            "text": str                     # Full transcript text
        }

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If audio file format unsupported
        RuntimeError: If transcription fails

    Examples:
        # Non-interactive with file I/O
        $ podx-transcribe -i audio-meta.json -o transcript.json --model large-v3-turbo

        # Piping from previous command
        $ podx-transcode -i episode-meta.json | podx-transcribe --model small

        # Interactive browser
        $ podx-transcribe --interactive --scan-dir ~/podcasts

        # OpenAI Whisper API
        $ podx-transcribe -i audio.json --asr-provider openai --model whisper-1

    See Also:
        - podx-align: Add word-level timestamps to transcript
        - podx-diarize: Add speaker labels
        - podx-preprocess: Clean and merge segments
    """
    # ... implementation
```

**Apply to:**
- All 17 command entry points
- Focus on complex return schemas (deepcast, consensus, agreement)

**Validation:**
```bash
# Check that docstrings render correctly
python -c "import podx.transcribe; help(podx.transcribe.main)"
```

---

### Doc 2.3: Update README.md with Command Reference

**File:** `README.md`

**Add new section:**

```markdown
## Command Reference

### Command Chaining

Podx commands are designed to be composed via JSON I/O:

\`\`\`bash
# Full pipeline using pipes
podx-fetch --show "Lex Fridman" --date 2024-03-15 \\
  | podx-transcode --to wav16 \\
  | podx-transcribe --model large-v3-turbo --preset precision \\
  | podx-align \\
  | podx-diarize \\
  | podx-deepcast --model gpt-4.1 --type interview_guest_focused \\
  | podx-notion --db MY_DATABASE_ID
\`\`\`

### Standard Options

All commands that process files support:
- `--input, -i PATH`: Read input JSON from file instead of stdin
- `--output, -o PATH`: Save output JSON to file (also prints to stdout)
- `--interactive`: Interactive mode with rich UI (disables JSON output to stdout)
- `--scan-dir PATH`: Directory to scan for episodes (default: current directory)

### Interactive vs Non-Interactive

**Non-interactive** (for scripting and piping):
\`\`\`bash
# Prints JSON to stdout
podx-transcribe -i audio-meta.json --model large-v3-turbo > transcript.json
\`\`\`

**Interactive** (for manual workflows):
\`\`\`bash
# Rich UI with tables and progress bars, saves to file
podx-transcribe --interactive --scan-dir ~/podcasts
\`\`\`

### Command Quick Reference

| Command | Purpose | Input | Output |
|---------|---------|-------|--------|
| `podx-fetch` | Download episode | API/RSS | EpisodeMeta |
| `podx-transcode` | Convert audio | EpisodeMeta | AudioMeta |
| `podx-transcribe` | ASR transcription | AudioMeta | Transcript |
| `podx-align` | Word timestamps | Transcript | AlignedTranscript |
| `podx-diarize` | Speaker labels | AlignedTranscript | DiarizedTranscript |
| `podx-preprocess` | Clean segments | Transcript | Transcript |
| `podx-deepcast` | LLM analysis | Transcript | DeepcastBrief |
| `podx-consensus` | Merge dual mode | 2× Deepcast | Consensus |
| `podx-export` | Export formats | Deepcast/Transcript | MD/PDF/TXT/SRT |
| `podx-notion` | Notion upload | Deepcast | Page info |
| `podx-agreement` | Compare analyses | 2× Deepcast | Agreement |
| `podx-models` | List AI models | — | Model list |
| `podx-list` | Browse episodes | — | Episode table |

For detailed usage of each command, run: `podx-{command} --help`
\`\`\`

**Files to Update:**
- `README.md` (add Command Reference section)
- Consider adding `docs/COMMAND_REFERENCE.md` for full details

---

## Phase 3: Future Improvements (v2.1+)

**Priority:** LOW | **Effort:** 8-12 hours | **Breaking:** NO

These changes improve maintainability and developer experience long-term.

### Improvement 3.1: Add Deprecation Warnings for Legacy Filenames

**Pattern:**
```python
# In file detection logic (e.g., podx/orchestrate.py, podx/export.py)
if transcript_path.name == "transcript.json":
    logger.warning(
        "Legacy filename 'transcript.json' detected. "
        "Please rename to 'transcript-{model}.json' format. "
        "Support for legacy filenames will be removed in v3.0."
    )
```

**Legacy patterns to warn on:**
- `transcript.json` → `transcript-{model}.json`
- `aligned-transcript-*.json` → `transcript-aligned-{model}.json`
- `deepcast-brief-{ai}.json` → `deepcast-{asr}-{ai}-{type}-{timestamp}.json`

**Files to Update:**
- `podx/orchestrate.py` (file detection logic)
- `podx/export.py` (scan for deepcasts)
- `podx/state/artifact_detector.py` (ARTIFACT_PATTERNS)

---

### Improvement 3.2: Enforce Pydantic Schema Validation

**Current State:** Schemas exist in `podx/schemas.py` but aren't enforced

**Goal:** All commands validate input/output using Pydantic models

**Pattern:**
```python
from podx.schemas import Transcript, AudioMeta

def main(input, output, ...):
    # Load and validate input
    with open(input) as f:
        data = json.load(f)

    audio = AudioMeta(**data)  # ✓ Validates schema, raises if invalid

    # ... processing ...

    # Validate output before writing
    result = Transcript(
        audio_path=audio.audio_path,
        language=detected_lang,
        segments=segments,
        ...
    )

    # Output validated data
    print(result.model_dump_json(indent=2))
```

**Benefits:**
- Catches schema errors early
- Self-documenting code
- Better IDE support

**Files to Update:**
- All command `main()` functions
- Add validation to input loading
- Add validation to output generation

**Effort:** ~1 hour per command × 14 commands = 14 hours

---

### Improvement 3.3: Create Unified Progress Library

**Current State:** Each command implements its own progress tracking

**Goal:** Shared progress library for consistency

**New Module:** `podx/ui/progress.py`

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

class PodxProgress:
    """Unified progress reporting for all podx commands."""

    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        )

    def start_step(self, name: str, total: int = 100) -> int:
        """Start a new pipeline step."""
        return self.progress.add_task(name, total=total)

    def update_step(self, task_id: int, advance: int = 1, **kwargs):
        """Update step progress."""
        self.progress.update(task_id, advance=advance, **kwargs)

    def complete_step(self, task_id: int, message: str = None):
        """Mark step as complete."""
        self.progress.update(task_id, completed=100)
        if message:
            self.progress.console.print(f"[green]✓[/green] {message}")
```

**Usage in commands:**
```python
with PodxProgress() as progress:
    task = progress.start_step("Transcribing audio")
    # ... work ...
    progress.complete_step(task, "Transcription complete (1:23:45)")
```

**Files to Create:**
- `podx/ui/progress.py`

**Files to Update:**
- All commands that show progress
- Replace custom progress code with `PodxProgress`

---

### Improvement 3.4: Add Integration Tests for Command Chaining

**Goal:** Validate that commands work together via pipes

**New File:** `tests/integration/test_command_chaining.py`

```python
import subprocess
import json
from pathlib import Path

def test_full_pipeline_chain():
    """Test: fetch → transcode → transcribe → align"""

    # Step 1: Fetch
    result = subprocess.run(
        ["podx-fetch", "--show", "Lex Fridman", "--date", "2024-03-15"],
        capture_output=True,
        text=True
    )
    episode = json.loads(result.stdout)
    assert "audio_path" in episode

    # Step 2: Transcode (using pipe)
    result = subprocess.run(
        ["podx-transcode", "--to", "wav16"],
        input=result.stdout,
        capture_output=True,
        text=True
    )
    audio = json.loads(result.stdout)
    assert audio["format"] == "wav16"

    # Step 3: Transcribe
    result = subprocess.run(
        ["podx-transcribe", "--model", "tiny"],
        input=result.stdout,
        capture_output=True,
        text=True
    )
    transcript = json.loads(result.stdout)
    assert "segments" in transcript

    # Step 4: Align
    result = subprocess.run(
        ["podx-align"],
        input=result.stdout,
        capture_output=True,
        text=True
    )
    aligned = json.loads(result.stdout)
    assert "words" in aligned["segments"][0]
```

**Files to Create:**
- `tests/integration/test_command_chaining.py`
- `tests/integration/test_file_io_consistency.py`

**Testing:**
```bash
pytest tests/integration/ -v --durations=10
```

---

## Implementation Checklist

### Phase 1: Critical Fixes (Required for v2.0)

- [ ] **1.1** Add `-i` and `-o` to `podx-preprocess`
  - [ ] Update code
  - [ ] Test backward compatibility
  - [ ] Update docs (if needed)

- [ ] **1.2** Standardize `podx-agreement` inputs
  - [ ] Add `--input/-i` option
  - [ ] Keep `--a/--b` as legacy
  - [ ] Update function logic
  - [ ] Test all input modes

- [ ] **1.3** Standardize `podx-consensus` inputs
  - [ ] Add `-p`, `-r`, `-a` short forms
  - [ ] Test all input modes

- [ ] **1.4** Remove JSON in interactive mode
  - [ ] Fix `podx-export`
  - [ ] Fix `podx-deepcast`
  - [ ] Test interactive mode output
  - [ ] Test non-interactive mode

- [ ] **1.5** Add `--output/-o` to `podx-notion`
  - [ ] Add option
  - [ ] Implement file save logic
  - [ ] Test output file

- [ ] **Phase 1 Validation**
  - [ ] Run full test suite: `pytest tests/ -v`
  - [ ] Manual test each modified command
  - [ ] Update CHANGELOG.md

### Phase 2: Documentation (Required for v2.0)

- [ ] **2.1** Clarify `--model` help text
  - [ ] `podx-transcribe`
  - [ ] `podx-deepcast`
  - [ ] `podx-agreement`
  - [ ] `podx-preprocess`

- [ ] **2.2** Add return schema docs
  - [ ] All 17 command docstrings
  - [ ] Focus on complex schemas

- [ ] **2.3** Update README.md
  - [ ] Add Command Reference section
  - [ ] Add chaining examples
  - [ ] Add interactive vs non-interactive guide

### Phase 3: Future Improvements (v2.1+)

- [ ] **3.1** Add deprecation warnings
  - [ ] Legacy filename detection
  - [ ] Warning messages

- [ ] **3.2** Pydantic schema validation
  - [ ] Validate inputs
  - [ ] Validate outputs
  - [ ] All 14 commands

- [ ] **3.3** Unified progress library
  - [ ] Create `PodxProgress` class
  - [ ] Refactor all commands

- [ ] **3.4** Integration tests
  - [ ] Command chaining tests
  - [ ] File I/O consistency tests

---

## Testing Strategy

### Automated Testing
```bash
# Run all unit tests
pytest tests/unit/ -v

# Run integration tests (Phase 3)
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=podx --cov-report=html
```

### Manual Testing Script
```bash
#!/bin/bash
# test_cli_consistency.sh

echo "Testing podx-preprocess..."
podx-preprocess -i tests/fixtures/transcript.json -o /tmp/out.json
echo "✓ Short forms work"

echo "Testing podx-agreement..."
echo '{"a": "tests/fixtures/deep1.json", "b": "tests/fixtures/deep2.json"}' | podx-agreement -i -
echo "✓ Structured input works"

echo "Testing podx-consensus..."
podx-consensus -p tests/fixtures/precision.json -r tests/fixtures/recall.json
echo "✓ Short forms work"

echo "Testing interactive mode (no JSON to stdout)..."
podx-export --interactive > /tmp/export-output.txt 2>&1
if grep -q '{' /tmp/export-output.txt; then
    echo "❌ FAIL: JSON found in interactive output"
else
    echo "✓ No JSON in interactive mode"
fi

echo "Testing podx-notion output..."
podx-notion -i tests/fixtures/deepcast.json --db TEST_DB -o /tmp/notion.json
test -f /tmp/notion.json && echo "✓ Output file created"

echo "All tests passed!"
```

---

## Migration Guide for Users

### Before v2.0 → After v2.0

#### Breaking Changes

1. **Interactive mode no longer prints JSON to stdout**
   ```bash
   # v1.x: Printed both rich output AND JSON (confusing)
   podx-export --interactive > output.json  # Got mixed output

   # v2.0: Rich output only, saves to file automatically
   podx-export --interactive  # Clean rich output, saves to file

   # Use non-interactive for JSON piping:
   podx-export -i deepcast.json > output.json
   ```

2. **`podx-preprocess` now requires standard flags**
   ```bash
   # Still works (with deprecation warning):
   podx-preprocess --input file.json --output out.json

   # Recommended:
   podx-preprocess -i file.json -o out.json
   ```

3. **`podx-agreement` supports structured input**
   ```bash
   # Both work:
   podx-agreement --a file1.json --b file2.json  # Legacy
   podx-agreement -i inputs.json  # New structured format
   ```

#### Upgrade Steps

1. Update podx: `pip install --upgrade podx`
2. Test scripts that use `--interactive` (remove stdout redirection)
3. Update any scripts using `podx-preprocess` to use `-i`/`-o`
4. Review any custom pipelines for compatibility

---

## Success Criteria

### Phase 1 Complete When:
- [ ] All commands follow `-i`/`-o` pattern
- [ ] Interactive mode never prints JSON to stdout
- [ ] All unit tests pass
- [ ] Manual testing confirms no regressions

### Phase 2 Complete When:
- [ ] All commands have comprehensive docstrings
- [ ] README has full command reference
- [ ] `--help` output is clear and consistent

### Phase 3 Complete When:
- [ ] Pydantic validation on all I/O
- [ ] Unified progress library in use
- [ ] Integration tests cover all command chains
- [ ] Deprecation warnings in place

---

## Timeline Estimate

| Phase | Tasks | Effort | Duration |
|-------|-------|--------|----------|
| Phase 1 | 5 fixes | 4-6 hours | 1-2 days |
| Phase 2 | 3 docs | 2-3 hours | 1 day |
| Phase 3 | 4 improvements | 8-12 hours | 2-3 days |
| **Total** | **12 tasks** | **14-21 hours** | **4-6 days** |

*Assuming part-time work (3-4 hours/day)*

---

## Questions or Issues?

If you encounter any issues during implementation:
1. Check the detailed analysis in `docs/CLI_INCONSISTENCIES.md`
2. Review existing test patterns in `tests/unit/`
3. Consult the plugin documentation in `docs/PLUGINS.md`

**Next Steps:** Start with Phase 1, Fix 1.1 (podx-preprocess) - it's the easiest and sets the pattern for the others.
