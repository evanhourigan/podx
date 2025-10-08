# Interactive Features in podx

This document summarizes all the interactive modes implemented across the podx CLI tools.

## Overview

Six podx commands now support `--interactive` mode, providing a visual browser interface for selecting and processing podcast episodes:

1. **podx-fetch** - Browse and download episodes from RSS feeds
2. **podx-transcode** - Browse and transcode downloaded episodes
3. **podx-transcribe** - Browse and transcribe transcoded episodes
4. **podx-align** - Browse and align transcripts with WhisperX
5. **podx-diarize** - Browse and add speaker labels to aligned transcripts
6. **podx-notion** - Browse and upload deepcast analyses to Notion

## Common Features

All interactive modes share these features:
- ✨ **Rich UI** - Colorful tables with emoji and styled text
- 📄 **Pagination** - Navigate through large episode lists
- 🔍 **Smart Scanning** - Automatically finds relevant files
- ✅ **Status Indicators** - Shows what's already been processed
- 🛡️ **Confirmation Prompts** - Prevents accidental overwrites
- 🚪 **Clean Exit** - Press 'Q' to quit anytime

## Command Details

### 1. podx-fetch --interactive

**Purpose:** Browse RSS feed episodes and download audio

**Usage:**
```bash
podx-fetch --show "My Podcast" --interactive
# or
podx-fetch --rss-url "https://feeds.example.com/podcast.xml" --interactive
```

**Features:**
- Paginated table of episodes from RSS feed
- Shows: # | Published Date | Title
- 8 episodes per page by default
- Downloads selected episode audio
- Generates episode-meta.json

**Navigation:**
- `1-N`: Select episode number
- `N`: Next page
- `P`: Previous page
- `Q`: Quit

---

### 2. podx-transcode --interactive

**Purpose:** Browse downloaded episodes and transcode audio

**Usage:**
```bash
podx-transcode --interactive --scan-dir ./episodes
```

**Features:**
- Scans for episodes with episode-meta.json
- Shows: # | Status | Show | Date | Title
- Status shows transcode format (e.g., "✓ wav" if audio-meta.json exists)
- Confirmation prompt for re-transcoding
- 10 episodes per page
- Outputs audio-meta.json + transcoded audio file

**Display Columns:**
- **Status**: Shows transcode format with checkmark if completed
- **Show**: Truncated to 18 chars
- **Date**: YYYY-MM-DD format
- **Title**: Truncated to 45 chars

---

### 3. podx-transcribe --interactive

**Purpose:** Browse transcoded episodes and generate transcripts

**Usage:**
```bash
podx-transcribe --interactive --scan-dir ./episodes
```

**Features:**
- Scans for episodes with audio-meta.json
- Shows: # | Status | Show | Date | Title
- Status shows ASR models used (e.g., "✓ large-v3, base")
- ASR model selection for each transcription
- Confirmation prompt for re-transcribing with same model
- 10 episodes per page
- Outputs transcript-{model}.json

**ASR Model Selection:**
- `1`: tiny
- `2`: base
- `3`: small
- `4`: medium
- `5`: large-v3 (default)

**Display Columns:**
- **Status**: Shows completed ASR models with checkmarks
- **Show**: Truncated to 18 chars
- **Date**: YYYY-MM-DD format
- **Title**: Truncated to 45 chars

---

### 4. podx-align --interactive

**Purpose:** Browse transcripts and align them with WhisperX

**Usage:**
```bash
podx-align --interactive --scan-dir ./episodes
```

**Features:**
- Scans for transcript-{model}.json files
- Shows: # | Status | Show | Date | Title
- Status shows ASR model with checkmark if aligned
- Confirmation prompt for re-aligning
- 10 episodes per page
- Outputs aligned-transcript-{model}.json

**Requirements:**
- WhisperX installed
- Python 3.12 or earlier (whisperx limitation)

**Display Columns:**
- **Status**: "✓ {model}" if aligned, "○ {model}" if not
- **Show**: Truncated to 18 chars
- **Date**: YYYY-MM-DD format
- **Title**: Truncated to 45 chars

**Header:** 🎙️ Episodes Available for Transcription Alignment (Page X/Y)

---

### 5. podx-diarize --interactive

**Purpose:** Browse aligned transcripts and add speaker labels

**Usage:**
```bash
podx-diarize --interactive --scan-dir ./episodes
```

**Features:**
- Scans for aligned-transcript-{model}.json files
- Shows: # | Status | Show | Date | Title
- Status shows ASR model with checkmark if diarized
- Confirmation prompt for re-diarizing
- 10 episodes per page
- Outputs diarized-transcript-{model}.json

**Requirements:**
- WhisperX installed
- HuggingFace token (HUGGINGFACE_TOKEN env var)
- Python 3.12 or earlier (whisperx limitation)

**Display Columns:**
- **Status**: "✓ {model}" if diarized, "○ {model}" if not
- **Show**: Truncated to 18 chars
- **Date**: YYYY-MM-DD format
- **Title**: Truncated to 45 chars

**Header:** 🎙️ Episodes Available for Transcription Diarization (Page X/Y)

---

### 6. podx-notion --interactive

**Purpose:** Browse deepcast analyses and upload to Notion

**Usage:**
```bash
podx-notion --db-id <notion-database-id> --interactive
```

**Features:**
- Three-step selection flow:
  1. **Show Selection** - Choose podcast show
  2. **Date Selection** - Choose episode date
  3. **Model Selection** - Choose deepcast model
- Only shows shows/dates with existing deepcast files
- Preview before uploading
- Dry-run option
- Rich colored UI matching other commands

**Flow:**
1. Lists all shows with deepcasts
2. After show selection, lists dates for that show
3. After date selection, lists available deepcast models
4. Confirms and uploads to Notion

**Filter Commands:**
- Type `/filter <text>` at show or date selection to filter list
- Clear filter with `/filter` (no argument)

---

## Implementation Details

### Dependencies

All interactive modes require:
- `rich` library for terminal UI
- `click` for CLI argument parsing

ASR-related commands additionally require:
- `faster-whisper` for transcription
- `whisperx` for alignment and diarization (Python < 3.13)
- `dateutil` for date parsing

### File Scanning

Interactive modes use smart scanning:
- **podx-transcode**: Looks for `episode-meta.json`
- **podx-transcribe**: Looks for `audio-meta.json`
- **podx-align**: Looks for `transcript-{model}.json`
- **podx-diarize**: Looks for `aligned-transcript-{model}.json`
- **podx-notion**: Looks for `deepcast-{model}.md` files

### Status Tracking

Each command tracks completion status:
- ✓ (checkmark) = already processed
- ○ (circle) = not yet processed
- Multiple models shown comma-separated when applicable

### Confirmation Prompts

When selecting already-processed items:
- "Re-transcode anyway? (yes/no):"
- "Re-transcribe with model 'large-v3' anyway? (yes/no):"
- "Re-align anyway? (yes/no):"
- "Re-diarize anyway? (yes/no):"

Type `yes` or `y` to proceed, anything else cancels.

### Output Files

All commands save to episode directory structure:
```
episodes/{show}/{YYYY-MM-DD}/
  ├── episode-meta.json          # from podx-fetch
  ├── audio-meta.json            # from podx-transcode
  ├── {show}.wav                 # from podx-transcode
  ├── transcript-{model}.json    # from podx-transcribe
  ├── aligned-transcript-{model}.json    # from podx-align
  ├── diarized-transcript-{model}.json   # from podx-diarize
  └── deepcast-{model}.md        # from podx-deepcast
```

## UI Consistency

All commands follow the same visual style:
- **Title**: Emoji + descriptive text with page numbers
- **Table Headers**: Bold magenta
- **Column Colors**:
  - `#` (Index): Cyan
  - Status: Yellow/Green
  - Show: Green
  - Date: Blue
  - Title: White
- **Navigation Panel**: Blue border
- **Options**: Color-coded (Cyan for numbers, Yellow for N/P, Red for Q)

## Git Commits

Key commits implementing these features:
```
621dfec - fix: match formatting of podx-align/diarize interactive to podx-transcribe
e2dd39e - docs: document interactive modes for podx-align and podx-diarize
3e49f04 - feat: add interactive mode to podx-align and podx-diarize
7e8ec30 - fix: clean exit when cancelling interactive transcribe mode
99bc4c5 - feat: add interactive transcribe mode with ASR model-specific filenames
4265f1a - feat: implement interactive version of podx-transcode
a0a1ba1 - feat: create interactive version of podx-fetch
6c782c8 - podx-notion --interactive: clear screen and richer colors
5da7236 - podx-notion --interactive: Rich table UI and /filter
fe050ed - podx-notion: add --interactive MVP
```

## Benefits

1. **Visual Selection** - No need to remember file paths or episode names
2. **Status Awareness** - See what's completed at a glance
3. **Prevent Duplicates** - Confirmation prompts for re-processing
4. **Consistent UX** - Same interaction patterns across all commands
5. **Efficient Workflow** - Process multiple episodes quickly
6. **Beginner Friendly** - No complex CLI arguments needed

## Future Enhancements

Potential improvements:
- Batch processing (select multiple episodes)
- Filter/search within interactive browser
- Sort by different columns
- Export selection to script/config
- Resume interrupted processes
- Progress bars for long-running operations

