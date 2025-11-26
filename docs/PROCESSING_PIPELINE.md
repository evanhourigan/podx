# PodX Processing Pipeline & State Graph

**Last Updated:** 2025-10-21
**Status:** Active Knowledge Base
**Version:** 2.0.0

## Overview

This document tracks PodX's simplified transcript processing pipeline, state transitions, and the planned PodGraph metadata system.

**Major Change in v2.0:** Alignment is no longer a user-visible state. It happens internally as part of diarization, simplifying the pipeline and removing user confusion about processing order.

---

## Current Processing State Graph (v2.0)

```
Base Transcript (fresh ASR output)
    ├──> Diarized (speaker labels + word-level alignment)
    │      └──> Preprocessed (text cleanup) [TERMINAL]
    │
    └──> Preprocessed (single-speaker: merged/normalized/LLM-cleaned) [TERMINAL]
```

### Valid Transitions

| From State | To State | Valid? | Notes |
|------------|----------|--------|-------|
| Base | Diarized | ✅ Yes | Runs alignment internally, then adds speaker labels |
| Base | Preprocessed | ✅ Yes | For single-speaker content; skips diarization |
| Diarized | Preprocessed | ✅ Yes | Final text cleanup before deepcast analysis |
| Preprocessed | Diarized | ❌ No | Text no longer matches audio word-for-word |

---

## Processing Steps Detailed

### 1. Base Transcript (`transcript-{model}.json`)

**Source:** `podx transcribe`
**Input:** Audio file (WAV16)
**Output:** JSON with segments containing start/end/text

**What it does:**
- Runs ASR (faster-whisper, OpenAI, or HuggingFace)
- Produces segments with approximate timestamps
- Segment-level granularity (not word-level)

**File naming:** `transcript-large-v3.json`

**Contains:**
```json
{
  "audio_path": "/path/to/audio.wav",
  "language": "en",
  "asr_model": "large-v3",
  "asr_provider": "local",
  "segments": [
    {"start": 0.0, "end": 5.2, "text": "Welcome to the show."}
  ]
}
```

---

### 2. Diarized Transcript (`transcript-diarized-{model}.json`)

**Source:** `podx diarize`
**Input:** Base transcript + audio file
**Output:** JSON with speaker labels and word-level timestamps

**What it does:**
- Runs WhisperX alignment internally (word-level timestamps)
- Runs WhisperX diarization pipeline (speaker detection)
- Assigns speaker labels to words/segments
- **Note:** Alignment happens automatically as part of diarization - users don't need to run alignment separately

**File naming:** `transcript-diarized-large-v3.json`

**Contains:**
```json
{
  "audio_path": "/path/to/audio.wav",
  "language": "en",
  "asr_model": "large-v3",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Welcome to the show.",
      "speaker": "SPEAKER_00",
      "words": [
        {"word": "Welcome", "start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"}
      ]
    }
  ]
}
```

---

### 3. Preprocessed Transcript (`transcript-preprocessed-{model}.json`)

**Source:** `podx preprocess`
**Input:** Any transcript (base or diarized)
**Output:** JSON with cleaned/merged segments

**What it does (all optional via flags):**

#### A. Merge Segments (`--merge`)
Combines adjacent short segments if:
- Gap between them < 1.0s (configurable via `--max-gap`)
- Combined text length < 800 chars (configurable via `--max-len`)

Example:
```json
// Before
[
  {"start": 0.0, "end": 2.5, "text": "Welcome to the show."},
  {"start": 2.8, "end": 5.0, "text": "Today we're talking about AI."}
]

// After (gap = 0.3s < 1.0s)
[
  {"start": 0.0, "end": 5.0, "text": "Welcome to the show. Today we're talking about AI."}
]
```

#### B. Normalize Text (`--normalize`)
- Collapses whitespace: `"word  word"` → `"word word"`
- Fixes punctuation spacing: `"word.Another"` → `"word. Another"`

#### C. Semantic Restore (`--restore`)
LLM-based cleanup (GPT-4 in batches):
- Fixes grammar and punctuation
- Preserves every idea/clause (even incomplete ones)
- Does NOT remove filler words
- Keeps semantic meaning intact

Example:
```
Before: "um so like the the main thing is uh we need to focus on quality"
After:  "So, the main thing is we need to focus on quality."
```

**⚠️ CRITICAL: Preprocessing is a TERMINAL operation**
- Text no longer matches audio word-for-word
- Cannot align or diarize after preprocessing
- Should be the last text operation before analysis

**File naming:** `transcript-preprocessed-large-v3.json`

---

## Recommended Processing Flow (v2.0 Defaults)

```
1. Transcribe (Base)
   transcript-large-v3.json
     ↓
2. Diarize (includes alignment internally) [DEFAULT - disable with --no-diarize]
   transcript-diarized-large-v3.json
     ↓
3. Preprocess (merge/normalize/restore) [DEFAULT - TERMINAL STATE]
   transcript-preprocessed-large-v3.json
     ↓
4. Deepcast Analysis [DEFAULT]
   deepcast-large-v3-gpt4-interview.json
     ↓
5. Export Markdown [DEFAULT]
   deepcast-large-v3-gpt4-interview.md
```

**Note:** In v2.0, steps 2-5 are enabled by default. Use `--no-diarize` for single-speaker content.

---

## v2.0 Resolved Issues

### ✅ **Removed Confusing Alignment Step**
- **v1.0 Problem:** Users had to understand when to align vs. diarize
- **v2.0 Solution:** Alignment happens automatically as part of diarization
- **Result:** Simpler mental model, one less command to learn

### ✅ **Clear Default Pipeline**
- **v1.0 Problem:** No clear "best practice" path, users unsure what flags to use
- **v2.0 Solution:** Sensible defaults (diarize + preprocess + deepcast + markdown)
- **Result:** Just run `podx run` and get useful output

### ✅ **Removed Dual-Track Complexity**
- **v1.0 Problem:** Precision/recall dual-track with unmeasured quality benefit
- **v2.0 Solution:** Removed dual-track, presets, fidelity levels entirely
- **Result:** 5× faster processing, simpler file organization

## Remaining Issues (Future PodGraph Work)

### 1. **Metadata Duplication**
- Episode info (show, title, date) duplicated in every JSON file
- Easy to get out of sync
- No single source of truth

### 2. **File Lineage Not Explicit**
- `transcript-preprocessed-large-v3.json` doesn't explicitly indicate source (base vs. diarized)
- PodGraph manifest will track processing history

---

## The PodGraph Project

**Goal:** Build a robust metadata and file organization system to solve the issues above.

### Vision

**Option 3: Hybrid Approach** (Recommended)

1. Keep individual artifact files as they are
2. Add `episode-manifest.json` as an index/cache
3. Add lineage metadata to each artifact file
4. Make manifest regeneratable from scanning files

### Example Manifest Structure

```json
{
  "episode": {
    "show": "Lenny's Podcast",
    "title": "Building Better Products",
    "published": "2024-12-15",
    "feed_url": "https://...",
    "fetched_at": "2025-01-21T10:30:00Z"
  },
  "artifacts": {
    "audio": {
      "original": {
        "id": "audio-original",
        "path": "episode.mp3",
        "format": "mp3",
        "checksum": "sha256:abc123..."
      },
      "transcoded": {
        "id": "audio-wav16",
        "path": "episode.wav",
        "format": "wav16",
        "derived_from": "audio-original",
        "created_at": "2025-01-21T10:35:00Z"
      }
    },
    "transcripts": [
      {
        "id": "transcript-large-v3-v1",
        "model": "large-v3",
        "type": "base",
        "path": "transcript-large-v3.json",
        "derived_from": "audio-wav16",
        "created_at": "2025-01-21T10:40:00Z"
      },
      {
        "id": "transcript-aligned-large-v3-v1",
        "model": "large-v3",
        "type": "aligned",
        "path": "transcript-aligned-large-v3.json",
        "derived_from": "transcript-large-v3-v1",
        "created_at": "2025-01-21T10:45:00Z"
      }
    ]
  },
  "processing_graph": {
    "nodes": ["audio-original", "audio-wav16", "transcript-large-v3-v1", "transcript-aligned-large-v3-v1"],
    "edges": [
      {"from": "audio-original", "to": "audio-wav16", "operation": "transcode"},
      {"from": "audio-wav16", "to": "transcript-large-v3-v1", "operation": "transcribe"},
      {"from": "transcript-large-v3-v1", "to": "transcript-aligned-large-v3-v1", "operation": "align"}
    ]
  }
}
```

### Implementation Phases

#### Phase 1: Add episode-manifest.json generation
- Create manifest after each processing step
- Make it regeneratable via `podx info --rebuild-manifest`
- Track artifact IDs and lineage

#### Phase 2: Add lineage tracking to artifact files
- Update all commands to add `_metadata` section
- Track `derived_from` chains
- Include processing parameters

#### Phase 3: Use manifest for better UIs
- Show processing history in browsers
- Visualize artifact dependencies
- Warn about stale artifacts
- Validate processing order

#### Phase 4 (optional): Reorganize file structure
- Migrate existing episodes
- Update all scanners
- Consider grouping by stage or model

---

## File Naming Conventions (v2.0)

| Type | Pattern | Example |
|------|---------|---------|
| Episode metadata | `episode-meta.json` | `episode-meta.json` |
| Original audio | `{title}.{ext}` | `episode.mp3` |
| Transcoded audio | `audio-meta.json` + `{title}.wav` | `episode.wav` |
| Base transcript | `transcript-{model}.json` | `transcript-large-v3.json` |
| Diarized transcript | `transcript-diarized-{model}.json` | `transcript-diarized-large-v3.json` |
| Preprocessed transcript | `transcript-preprocessed-{model}.json` | `transcript-preprocessed-large-v3.json` |
| Deepcast JSON | `deepcast-{asr}-{ai}-{type}.json` | `deepcast-large-v3-gpt4-interview.json` |
| Deepcast Markdown | `deepcast-{asr}-{ai}-{type}.md` | `deepcast-large-v3-gpt4-interview.md` |

**Note:** Aligned transcripts (`transcript-aligned-*.json`) no longer exist in v2.0. Alignment happens internally during diarization.

---

## v2.0 Design Decisions

1. **✅ Preprocessing is encouraged (default)**
   - Merging improves readability for LLM analysis
   - Semantic restore is opt-in (`--restore` flag) due to cost/hallucination risk
   - Default: merge + normalize only

2. **✅ No combined state files**
   - Clean separation: base → diarized → preprocessed
   - No `transcript-aligned-preprocessed-*.json` complexity

3. **✅ Re-processing overwrites**
   - Running same step twice overwrites the file
   - PodGraph manifest will track history in future

4. **✅ Diarization always includes alignment**
   - Alignment is not optional - always runs before diarization
   - Users don't need to understand the distinction

---

## Related Files (v2.0)

- **Scanners:**
  - `podx/ui/diarize_browser.py::scan_diarizable_transcripts()` (base transcripts only)
  - `podx/ui/preprocess_browser.py::scan_preprocessable_transcripts()` (most-processed per model)
  - `podx/ui/transcribe_browser.py::scan_transcribable_episodes()`
  - `podx/ui/transcode_browser.py::scan_transcodable_episodes()`

- **Processing Commands:**
  - `podx/transcribe.py`
  - `podx/diarize.py` (includes internal alignment)
  - `podx/preprocess.py`

- **UI:**
  - `podx/ui/two_phase_browser.py::TwoPhaseTranscriptBrowser` (episode → transcript selection)
  - `podx/ui/episode_browser_tui.py::SimpleProcessingBrowser` (for transcode/transcribe)

---

## Version History

| Date | Change | Notes |
|------|--------|-------|
| 2025-01-21 | Initial document | Captured current understanding of pipeline |
| 2025-10-21 | v2.0 major update | Removed alignment as user-visible state, removed dual-track/presets/workflows, new defaults |
