# PodX Processing Pipeline & State Graph

**Last Updated:** 2025-01-21
**Status:** Active Knowledge Base

## Overview

This document tracks the current understanding of PodX's transcript processing pipeline, state transitions, and the planned PodGraph metadata system.

---

## Current Processing State Graph

```
Base Transcript (fresh ASR output)
    ├──> Aligned (WhisperX word-level alignment)
    │      └──> Diarized (speaker labels)
    │             └──> Preprocessed (text cleanup) [TERMINAL]
    │
    └──> Preprocessed (merged/normalized/LLM-cleaned) [TERMINAL - BREAKS ALIGNMENT]
```

### Valid Transitions

| From State | To State | Valid? | Notes |
|------------|----------|--------|-------|
| Base | Aligned | ✅ Yes | Adds word-level timestamps via WhisperX |
| Base | Preprocessed | ⚠️ Yes but... | Text cleanup works, but can't align/diarize after |
| Aligned | Diarized | ✅ Yes | Adds speaker labels to aligned words |
| Aligned | Preprocessed | ⚠️ Yes but... | Terminal state - no more audio ops possible |
| Diarized | Preprocessed | ✅ Yes | Final text cleanup before analysis |
| Preprocessed | Aligned | ❌ No | Scanner skips preprocessed files |
| Preprocessed | Diarized | ❌ No | Text no longer matches audio |
| Diarized | Aligned | ❌ No | Scanner skips diarized files; order wrong anyway |

---

## Processing Steps Detailed

### 1. Base Transcript (`transcript-{model}.json`)

**Source:** `podx-transcribe`
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

### 2. Aligned Transcript (`transcript-aligned-{model}.json`)

**Source:** `podx-align`
**Input:** Base transcript + audio file
**Output:** JSON with word-level timestamps

**What it does:**
- Uses WhisperX to align words to precise timestamps
- Improves timestamp accuracy significantly
- Required for high-quality diarization

**File naming:** `transcript-aligned-large-v3.json`

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
      "words": [
        {"word": "Welcome", "start": 0.0, "end": 0.5},
        {"word": "to", "start": 0.6, "end": 0.7},
        {"word": "the", "start": 0.75, "end": 0.9},
        {"word": "show", "start": 1.0, "end": 1.4}
      ]
    }
  ]
}
```

---

### 3. Diarized Transcript (`transcript-diarized-{model}.json`)

**Source:** `podx-diarize`
**Input:** Aligned transcript + audio file
**Output:** JSON with speaker labels

**What it does:**
- Uses WhisperX diarization pipeline
- Assigns speaker labels to words/segments
- Requires aligned transcript for best results

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

### 4. Preprocessed Transcript (`transcript-preprocessed-{model}.json`)

**Source:** `podx-preprocess`
**Input:** Any transcript (base, aligned, or diarized)
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

## Recommended Processing Flow

```
1. Transcribe (Base)
   transcript-large-v3.json
     ↓
2. Align [OPTIONAL but recommended]
   transcript-aligned-large-v3.json
     ↓
3. Diarize [OPTIONAL]
   transcript-diarized-large-v3.json
     ↓
4. Preprocess [OPTIONAL cleanup - TERMINAL STATE]
   transcript-preprocessed-large-v3.json
     ↓
5. Deepcast Analysis
   deepcast-large-v3-gpt4-interview.json
```

---

## Current Issues & Confusion

### 1. **Preprocessing Can Happen Too Early**
- If you preprocess a base transcript, you can't align it later
- No validation prevents this invalid flow

### 2. **File Naming Doesn't Show Lineage**
- `transcript-preprocessed-large-v3.json` doesn't indicate if it came from:
  - Base → Preprocessed
  - Aligned → Preprocessed
  - Diarized → Preprocessed
- All three have different quality/capabilities

### 3. **No Clear "Best Practice" Path**
- Should preprocessing happen at all?
- When is merging beneficial vs. harmful?
- When to use semantic restore?

### 4. **Scanner Logic is Fragile**
- Each command has its own scanner that skips certain file patterns
- Easy to miss edge cases
- Hard to maintain consistency

### 5. **Metadata Duplication**
- Episode info (show, title, date) duplicated in every JSON file
- Easy to get out of sync
- No single source of truth

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

## File Naming Conventions (Current)

| Type | Pattern | Example |
|------|---------|---------|
| Episode metadata | `episode-meta.json` | `episode-meta.json` |
| Original audio | `{title}.{ext}` | `episode.mp3` |
| Transcoded audio | `audio-meta.json` + `{title}.wav` | `episode.wav` |
| Base transcript | `transcript-{model}.json` | `transcript-large-v3.json` |
| Aligned transcript | `transcript-aligned-{model}.json` | `transcript-aligned-large-v3.json` |
| Diarized transcript | `transcript-diarized-{model}.json` | `transcript-diarized-large-v3.json` |
| Preprocessed transcript | `transcript-preprocessed-{model}.json` | `transcript-preprocessed-large-v3.json` |
| Deepcast analysis | `deepcast-{asr}-{ai}-{type}[-{track}].json` | `deepcast-large-v3-gpt4-interview-precision.json` |

---

## Questions & Open Issues

1. **Should preprocessing be encouraged or discouraged?**
   - Merging can improve readability
   - But semantic restore might hallucinate
   - When is it worth the tradeoff?

2. **What about combined states?**
   - Should we support `transcript-aligned-preprocessed-{model}.json`?
   - Or is that too complex?

3. **How to handle re-processing?**
   - If you align twice, which file wins?
   - Version numbers in filenames?
   - Keep history in manifest?

4. **Should diarization require alignment?**
   - Technically it works better with aligned
   - But could work on base transcripts
   - Should we enforce the requirement?

---

## Related Files

- **Scanners:**
  - `podx/ui/align_browser.py::scan_alignable_transcripts()`
  - `podx/ui/diarize_browser.py::scan_diarizable_transcripts()`
  - `podx/ui/transcribe_browser.py::scan_transcribable_episodes()`
  - `podx/ui/transcode_browser.py::scan_transcodable_episodes()`

- **Processing Commands:**
  - `podx/transcribe.py`
  - `podx/align.py`
  - `podx/diarize.py`
  - `podx/preprocess.py`

- **UI:**
  - `podx/ui/episode_browser_tui.py::ModelLevelProcessingBrowser` (for align/diarize)
  - `podx/ui/episode_browser_tui.py::SimpleProcessingBrowser` (for transcode/transcribe)

---

## Version History

| Date | Change | Notes |
|------|--------|-------|
| 2025-01-21 | Initial document | Captured current understanding of pipeline |
