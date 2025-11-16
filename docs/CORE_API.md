# PodX Core API Reference

This document describes the core business logic modules in PodX v2.0. These modules provide pure business logic separated from CLI concerns, enabling easier testing, reuse, and integration.

## Overview

PodX v2.0 introduces a clean **core/CLI separation** architecture where:

- **Core modules** (`podx.core.*`) contain pure business logic with no Click dependencies
- **CLI wrappers** (`podx.cli.*`) handle user interaction, progress display, and terminal I/O
- **Engines** are initialized with options and optional progress callbacks for UI integration

This architecture enables:
- ✅ Pure unit testing without UI mocking
- ✅ Programmatic API usage without CLI overhead
- ✅ Easy integration into other Python applications
- ✅ Better code organization and maintainability

---

## Module Index

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| **[transcode](#transcode-module)** | Audio format conversion | `TranscodeEngine` |
| **[fetch](#fetch-module)** | Episode discovery and download | `FetchEngine` |
| **[preprocess](#preprocess-module)** | Transcript normalization | `PreprocessEngine` |
| **[transcribe](#transcribe-module)** | Speech-to-text | `TranscribeEngine` |
| **[diarize](#diarize-module)** | Speaker identification | `DiarizeEngine` |
| **[deepcast](#deepcast-module)** | AI-powered analysis | `DeepcastEngine` |
| **[notion](#notion-module)** | Notion API integration | `NotionEngine` |
| **[export](#export-module)** | Format conversion | `ExportEngine` |
| **[youtube](#youtube-module)** | YouTube download | `YouTubeEngine` |
| **[audio_quality](#audio-quality-module)** | Audio quality analysis | `AudioQualityAnalyzer` |
| **[batch](#batch-processing-module)** | Batch processing | `BatchProcessor`, `EpisodeDiscovery`, `BatchStatus` |

---

## Common Patterns

### Engine Initialization

All core engines follow a consistent initialization pattern:

```python
from podx.core.module_name import ModuleEngine

# Basic initialization
engine = ModuleEngine()

# With progress callback for UI integration
def progress_callback(message: str):
    print(f"[PROGRESS] {message}")

engine = ModuleEngine(progress_callback=progress_callback)

# With specific options
engine = ModuleEngine(
    option1=value1,
    option2=value2,
    progress_callback=progress_callback
)
```

### Progress Reporting

PodX provides unified progress reporting via the `ProgressReporter` abstraction. All engines accept either a `ProgressReporter` instance or a legacy callback function.

#### Using ProgressReporter (Recommended)

```python
from podx.progress import ConsoleProgressReporter

# Create a progress reporter
progress = ConsoleProgressReporter(verbose=True)

# Use with any engine
engine = SomeEngine(progress=progress)
result = engine.process(input_data)
```

**Available Reporters:**
- `ConsoleProgressReporter` - Rich-based CLI output with spinners and colors
- `APIProgressReporter` - Event queue for web API integration (SSE/WebSocket)
- `SilentProgressReporter` - No-op for testing (optional call tracking)
- Custom reporters - Implement `ProgressReporter` interface

#### Legacy Progress Callbacks (Backward Compatible)

For backward compatibility, engines still support simple callback functions:

```python
from typing import Callable, Optional

def my_callback(message: str):
    """Progress callback receives status messages."""
    print(f"Status: {message}")

# Works with legacy callback
engine = SomeEngine(progress_callback=my_callback)

# Or via 'progress' parameter (auto-detected)
engine = SomeEngine(progress=my_callback)
```

**For comprehensive progress reporting documentation, see [Progress Reporting API](./PROGRESS_REPORTING.md).**

### Error Handling

Each module defines custom exceptions for specific error cases:

```python
from podx.core.module_name import ModuleError

try:
    result = engine.process(input_data)
except ModuleError as e:
    print(f"Processing failed: {e}")
    # Handle error appropriately
```

---

## Transcode Module

**Purpose:** Audio format conversion and normalization for optimal transcription quality.

### TranscodeEngine

```python
from podx.core.transcode import TranscodeEngine, TranscodeError

# Initialize
engine = TranscodeEngine(progress_callback=callback)

# Transcode audio
result = engine.transcode(
    input_file="/path/to/audio.mp3",
    output_format="wav16",  # wav16, wav, mp3, etc.
    output_file="/path/to/output.wav"  # Optional
)

# Returns: Dict with output_file path and format info
```

**Key Methods:**
- `transcode(input_file, output_format, output_file=None)` - Convert audio format

**Output Formats:**
- `wav16` - 16kHz WAV (optimal for Whisper)
- `wav` - Standard WAV
- `mp3` - MP3 compression
- `aac` - AAC compression

---

## Fetch Module

**Purpose:** Discover and download podcast episodes from various sources (iTunes, RSS, YouTube).

### FetchEngine

```python
from podx.core.fetch import FetchEngine, FetchError

# Initialize
engine = FetchEngine(progress_callback=callback)

# Fetch episode by show name and date
result = engine.fetch(
    show="Lex Fridman Podcast",
    date="2024-10-15",
    interactive=False
)

# Returns: Dict with episode metadata and audio file path
# {
#   "title": "...",
#   "audio_file": "/path/to/audio.mp3",
#   "date": "2024-10-15",
#   "duration": 7234.5,
#   "show": "..."
# }
```

**Key Methods:**
- `fetch(show, date, interactive=False)` - Download episode by show and date
- `search_episodes(show, limit=10)` - Search for episodes

---

## Preprocess Module

**Purpose:** Normalize and optionally restore transcript text using LLM-powered correction.

### PreprocessEngine

```python
from podx.core.preprocess import PreprocessEngine, PreprocessError

# Initialize
engine = PreprocessEngine(
    merge_threshold=0.5,  # Merge segments < 0.5s apart
    restore=True,         # Enable LLM restoration
    restore_model="gpt-4o-mini",
    progress_callback=callback
)

# Preprocess transcript
result = engine.preprocess(transcript_data)

# Returns: Enhanced transcript with normalized text
```

**Key Methods:**
- `preprocess(transcript)` - Normalize and optionally restore transcript

**Options:**
- `merge_threshold` - Seconds between segments to merge (default: 0.5)
- `restore` - Enable LLM-powered text restoration (default: False)
- `restore_model` - LLM model for restoration (default: "gpt-4o-mini")

---

## Transcribe Module

**Purpose:** Speech-to-text transcription using Whisper models.

### TranscribeEngine

```python
from podx.core.transcribe import TranscribeEngine, TranscribeError

# Initialize
engine = TranscribeEngine(
    model="large-v3-turbo",  # Whisper model
    device="auto",           # cuda, cpu, or auto
    compute_type="float16",
    progress_callback=callback
)

# Transcribe audio
result = engine.transcribe(
    audio_file="/path/to/audio.wav",
    language="en"  # Optional language hint
)

# Returns: Dict with segments and full text
# {
#   "text": "Full transcript...",
#   "segments": [
#     {"start": 0.0, "end": 2.5, "text": "Hello world"},
#     ...
#   ]
# }
```

**Key Methods:**
- `transcribe(audio_file, language=None)` - Transcribe audio to text

**Supported Models:**
- `tiny`, `small`, `medium`, `large-v2`, `large-v3`, `large-v3-turbo`

---

## Diarize Module

**Purpose:** Add speaker identification and word-level timestamps using WhisperX.

### DiarizeEngine

```python
from podx.core.diarize import DiarizeEngine, DiarizeError

# Initialize
engine = DiarizeEngine(
    device="auto",
    hf_token=None,  # HuggingFace token for speaker models
    progress_callback=callback
)

# Diarize transcript
result = engine.diarize(
    audio_file="/path/to/audio.wav",
    transcript_segments=[...]  # Segments from transcribe
)

# Returns: Enhanced segments with speakers and word timestamps
# [
#   {
#     "start": 0.0,
#     "end": 2.5,
#     "text": "Hello world",
#     "speaker": "SPEAKER_01",
#     "words": [
#       {"word": "Hello", "start": 0.0, "end": 0.5},
#       {"word": "world", "start": 0.6, "end": 1.1}
#     ]
#   },
#   ...
# ]
```

**Key Methods:**
- `diarize(audio_file, transcript_segments)` - Add speakers and word timestamps

**Requirements:**
- WhisperX library
- HuggingFace token for speaker models (optional)

---

## Deepcast Module

**Purpose:** AI-powered podcast analysis using LLMs (GPT-4, Claude).

### DeepcastEngine

```python
from podx.core.deepcast import DeepcastEngine, DeepcastError

# Initialize
engine = DeepcastEngine(
    model="gpt-4o",
    analysis_type="interview_guest_focused",
    custom_prompts="Focus on technical insights...",
    api_key=None,  # Uses OPENAI_API_KEY env var if not provided
    progress_callback=callback
)

# Analyze transcript
markdown, json_data = engine.deepcast(
    transcript=transcript_data,
    episode_metadata={"title": "...", "date": "..."}
)

# Returns:
# - markdown: Formatted analysis with sections
# - json_data: Structured insights (title, key_points, quotes, etc.)
```

**Key Methods:**
- `deepcast(transcript, episode_metadata)` - Generate AI analysis

**Analysis Types:**
- `interview_guest_focused` - Focus on guest insights
- `solo_commentary` - Single speaker analysis
- `panel_discussion` - Multi-speaker discussion
- `narrative` - Storytelling podcasts

**Output Structure:**
```python
{
    "title": "Episode title",
    "summary": "One-line summary",
    "key_points": ["Point 1", "Point 2", ...],
    "insights": ["Insight 1", ...],
    "quotes": [
        {"speaker": "...", "quote": "...", "context": "..."},
        ...
    ],
    "topics": ["Topic 1", "Topic 2", ...],
    "actionable_takeaways": ["Takeaway 1", ...]
}
```

---

## Notion Module

**Purpose:** Create and publish content to Notion pages.

### NotionEngine

```python
from podx.core.notion import NotionEngine, NotionError

# Initialize
engine = NotionEngine(
    token=None,  # Uses NOTION_TOKEN env var if not provided
    progress_callback=callback
)

# Create page
page_id = engine.create_page(
    database_id="your-database-id",
    title="Episode Title",
    markdown_content="# Content...",
    properties={
        "Date": "2024-10-15",
        "Show": "Podcast Name"
    }
)

# Set page cover image
engine.set_page_cover(page_id, "https://example.com/cover.jpg")
```

**Key Methods:**
- `create_page(database_id, title, markdown_content, properties)` - Create page
- `set_page_cover(page_id, cover_url)` - Set cover image
- `md_to_blocks(markdown)` - Convert markdown to Notion blocks (utility)

**Supported Markdown:**
- Headings (`#`, `##`, `###`)
- Bold (`**text**`)
- Italic (`*text*`)
- Code (`` `text` ``)
- Lists (`-`, `1.`)
- Quotes (`>`)
- Code blocks (` ``` `)
- Dividers (`---`)

---

## Export Module

**Purpose:** Convert transcripts to various output formats.

### ExportEngine

```python
from podx.core.export import ExportEngine, ExportError

# Initialize
engine = ExportEngine(progress_callback=callback)

# Export transcript
result = engine.export(
    transcript=transcript_data,
    formats=["txt", "srt", "vtt", "md"],
    output_dir="/path/to/output",
    base_filename="episode"
)

# Returns: Dict with written files
# {
#   "files_written": 4,
#   "output_dir": "/path/to/output",
#   "formats": {
#     "txt": "/path/to/output/episode.txt",
#     "srt": "/path/to/output/episode.srt",
#     "vtt": "/path/to/output/episode.vtt",
#     "md": "/path/to/output/episode.md"
#   }
# }
```

**Key Methods:**
- `export(transcript, formats, output_dir, base_filename)` - Export to formats

**Supported Formats:**
- `txt` - Plain text transcript
- `srt` - SubRip subtitles with timestamps
- `vtt` - WebVTT subtitles
- `md` - Markdown with timestamps
- `json` - Raw JSON transcript

**Format Options:**
- All formats preserve speaker attribution (if available)
- Timestamps use format: `HH:MM:SS,mmm` (SRT) or `HH:MM:SS.mmm` (VTT)
- Markdown includes both timestamp and text formatting

---

## YouTube Module

**Purpose:** Download audio from YouTube videos.

### YouTubeEngine

```python
from podx.core.youtube import YouTubeEngine, YouTubeError

# Initialize
engine = YouTubeEngine(
    output_dir="/path/to/downloads",
    progress_callback=callback
)

# Download video audio
result = engine.download(url="https://youtube.com/watch?v=VIDEO_ID")

# Returns: Dict with audio file and metadata
# {
#   "audio_file": "/path/to/downloads/video.mp3",
#   "title": "Video Title",
#   "duration": 1234.5,
#   "channel": "Channel Name",
#   "upload_date": "2024-10-15"
# }

# Parse YouTube URL
video_id = engine.parse_url("https://youtube.com/watch?v=VIDEO_ID")
# Returns: "VIDEO_ID"
```

**Key Methods:**
- `download(url)` - Download audio from YouTube
- `parse_url(url)` - Extract video ID from URL
- `get_metadata(url)` - Get video metadata without downloading

**Requirements:**
- yt-dlp library
- ffmpeg (for audio extraction)

---

## Integration Examples

### Complete Processing Pipeline

```python
from podx.core.fetch import FetchEngine
from podx.core.transcode import TranscodeEngine
from podx.core.transcribe import TranscribeEngine
from podx.core.diarize import DiarizeEngine
from podx.core.deepcast import DeepcastEngine
from podx.core.export import ExportEngine
from podx.core.notion import NotionEngine

def progress(msg):
    print(f"[{datetime.now()}] {msg}")

# 1. Fetch episode
fetch = FetchEngine(progress_callback=progress)
episode = fetch.fetch("Lex Fridman", "2024-10-15")

# 2. Transcode to WAV
transcode = TranscodeEngine(progress_callback=progress)
audio = transcode.transcode(episode["audio_file"], "wav16")

# 3. Transcribe
transcribe = TranscribeEngine(
    model="large-v3-turbo",
    progress_callback=progress
)
transcript = transcribe.transcribe(audio["output_file"])

# 4. Diarize
diarize = DiarizeEngine(progress_callback=progress)
diarized = diarize.diarize(audio["output_file"], transcript["segments"])

# 5. Analyze
deepcast = DeepcastEngine(
    model="gpt-4o",
    analysis_type="interview_guest_focused",
    progress_callback=progress
)
markdown, insights = deepcast.deepcast(
    {"segments": diarized},
    episode
)

# 6. Export
export = ExportEngine(progress_callback=progress)
export.export(
    {"segments": diarized},
    ["txt", "srt", "md"],
    "/output",
    "episode"
)

# 7. Publish to Notion
notion = NotionEngine(progress_callback=progress)
page_id = notion.create_page(
    database_id="your-db-id",
    title=episode["title"],
    markdown_content=markdown,
    properties={"Date": episode["date"]}
)
```

### YouTube to Transcript

```python
from podx.core.youtube import YouTubeEngine
from podx.core.transcribe import TranscribeEngine
from podx.core.export import ExportEngine

# Download YouTube audio
youtube = YouTubeEngine()
video = youtube.download("https://youtube.com/watch?v=VIDEO_ID")

# Transcribe
transcribe = TranscribeEngine(model="large-v3-turbo")
transcript = transcribe.transcribe(video["audio_file"])

# Export
export = ExportEngine()
export.export(transcript, ["txt", "srt"], "/output", "video")
```

### Batch Processing with Custom Progress

```python
from podx.core.transcribe import TranscribeEngine
from rich.progress import Progress

episodes = ["ep1.wav", "ep2.wav", "ep3.wav"]

with Progress() as progress:
    task = progress.add_task("Processing", total=len(episodes))

    def callback(msg):
        progress.console.log(msg)

    engine = TranscribeEngine(progress_callback=callback)

    for episode in episodes:
        transcript = engine.transcribe(episode)
        # Process transcript...
        progress.advance(task)
```

---

## Testing

All core modules have comprehensive unit tests with 97-100% coverage:

```bash
# Run all core tests
pytest tests/unit/test_core_*.py -v

# Run specific module tests
pytest tests/unit/test_core_export.py -v

# With coverage report
pytest tests/unit/test_core_*.py --cov=podx.core --cov-report=html
```

See [TESTING.md](./TESTING.md) for testing guidelines and patterns.

---

## Error Handling Reference

Each module defines custom exceptions:

| Module | Exception Class | Common Causes |
|--------|----------------|---------------|
| transcode | `TranscodeError` | Invalid format, ffmpeg not found |
| fetch | `FetchError` | Episode not found, network error |
| preprocess | `PreprocessError` | Invalid transcript, LLM API error |
| transcribe | `TranscribeError` | Model not found, audio file invalid |
| diarize | `DiarizeError` | WhisperX not installed, no audio |
| deepcast | `DeepcastError` | LLM API error, invalid prompt |
| notion | `NotionError` | Auth failure, invalid database ID |
| export | `ExportError` | Invalid format, write permission |
| youtube | `YouTubeError` | Invalid URL, download failure |

---

## Best Practices

### 1. Always Use Progress Callbacks

```python
# Good: Provides feedback to users
def progress(msg):
    logger.info(msg)

engine = Engine(progress_callback=progress)

# Bad: Silent processing
engine = Engine()  # No feedback
```

### 2. Handle Exceptions Appropriately

```python
# Good: Specific error handling
from podx.core.transcribe import TranscribeEngine, TranscribeError

try:
    result = engine.transcribe(audio_file)
except TranscribeError as e:
    logger.error(f"Transcription failed: {e}")
    # Fallback or retry logic
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### 3. Validate Inputs

```python
# Good: Validate before processing
from pathlib import Path

audio_file = Path("audio.wav")
if not audio_file.exists():
    raise FileNotFoundError(f"Audio file not found: {audio_file}")

result = engine.transcribe(str(audio_file))
```

### 4. Use Type Hints

```python
# Good: Type-safe API usage
from typing import Dict, List, Optional

def process_episode(
    show: str,
    date: str,
    formats: List[str],
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    # Implementation
    pass
```

---

## Migration from v1.x

If you're migrating from PodX v1.x CLI-only architecture:

**Old (v1.x):**
```python
# Everything coupled to Click
@click.command()
def transcribe(audio_file, model):
    # CLI logic mixed with business logic
    click.echo("Transcribing...")
    result = whisper_model.transcribe(audio_file)
    click.echo("Done!")
```

**New (v2.0):**
```python
# Core: Pure business logic
class TranscribeEngine:
    def transcribe(self, audio_file):
        if self.progress_callback:
            self.progress_callback("Transcribing...")
        return result

# CLI: UI layer
@click.command()
def transcribe(audio_file, model):
    engine = TranscribeEngine(model, progress_callback=click.echo)
    result = engine.transcribe(audio_file)
```

**Benefits:**
- ✅ Core logic is testable without Click
- ✅ Reusable in other contexts (API, GUI, etc.)
- ✅ Clear separation of concerns
- ✅ Progress callbacks work with any UI framework

---

## Batch Processing Module

### Overview

The Batch Processing module (`podx.batch`) provides tools for processing multiple podcast episodes in parallel with automatic discovery, filtering, error handling, and status tracking.

**Key Features:**
- Automatic episode discovery from directory structure
- Flexible filtering (show name, date range, duration, status)
- Parallel processing with configurable workers
- Retry logic with exponential backoff
- Continue-on-error support
- Persistent status tracking
- Rich progress display

### EpisodeDiscovery

Discovers and filters episodes for batch processing.

#### Basic Usage

```python
from pathlib import Path
from podx.batch import EpisodeDiscovery, EpisodeFilter

# Create discovery engine
discovery = EpisodeDiscovery(base_path=Path("episodes"))

# Auto-discover all episodes
episodes = discovery.discover_episodes(auto_detect=True)
print(f"Found {len(episodes)} episodes")

# Discover with filters
filters = EpisodeFilter(
    show="My Podcast",
    since="2024-01-01",
    min_duration=300,  # 5 minutes
    max_duration=7200,  # 2 hours
    status="new"  # Only unprocessed episodes
)
filtered = discovery.discover_episodes(auto_detect=True, filters=filters)
```

#### Episode Filter Options

```python
from podx.batch import EpisodeFilter

filter_options = EpisodeFilter(
    show="Podcast Name",           # Filter by show name
    since="2024-01-01",             # Episodes since date
    date_range=("2024-01-01", "2024-12-31"),  # Date range tuple
    min_duration=300,               # Minimum duration in seconds
    max_duration=7200,              # Maximum duration in seconds
    status="new"                    # "new", "partial", or "complete"
)
```

### BatchProcessor

Processes multiple episodes in parallel with error handling and progress tracking.

#### Basic Usage

```python
from pathlib import Path
from podx.batch import BatchProcessor, EpisodeDiscovery

# Discover episodes
discovery = EpisodeDiscovery(base_path=Path("episodes"))
episodes = discovery.discover_episodes(auto_detect=True)

# Create processor
processor = BatchProcessor(
    parallel_workers=4,
    continue_on_error=True,
    max_retries=2,
    retry_delay=5
)

# Define processing function
def transcribe_episode(episode):
    from podx.core.transcribe import TranscribeEngine

    audio_path = Path(episode["directory"]) / "episode-audio.wav"
    transcriber = TranscribeEngine(model="large-v3")
    return transcriber.transcribe(audio_path)

# Process batch
results = processor.process_batch(
    episodes=episodes,
    process_fn=transcribe_episode,
    operation_name="Transcribing"
)

# Check results
successful = sum(1 for r in results if r.success)
failed = sum(1 for r in results if not r.success)
print(f"✓ {successful} succeeded, ✗ {failed} failed")
```

#### Configuration Options

```python
from podx.batch import BatchProcessor

processor = BatchProcessor(
    parallel_workers=4,        # Number of parallel threads (default: 1)
    continue_on_error=True,    # Continue if episodes fail (default: True)
    max_retries=2,             # Retry failed episodes (default: 0)
    retry_delay=5              # Seconds between retries (default: 5)
)
```

#### Batch Result

Each batch operation returns a list of `BatchResult` objects:

```python
from podx.batch import BatchResult

result = BatchResult(
    episode=dict,     # Episode metadata
    success=bool,     # Whether processing succeeded
    result=Any,       # Processing result (if successful)
    error=str,        # Error message (if failed)
    retries=int       # Number of retries attempted
)
```

### BatchStatus

Tracks processing status for pipeline operations with persistence.

#### Basic Usage

```python
from pathlib import Path
from podx.batch import BatchStatus, ProcessingState

# Create status tracker
status = BatchStatus(status_file=Path.home() / ".podx" / "batch-status.json")

# Update episode status
status.update_episode_status(
    title="Episode 1",
    step="transcribe",
    state=ProcessingState.IN_PROGRESS
)

# Mark step complete
status.update_episode_status(
    title="Episode 1",
    step="transcribe",
    state=ProcessingState.COMPLETED
)

# Display status table
status.display_status_table()

# Save to disk
status.save()
```

#### Processing States

```python
from podx.batch import ProcessingState

ProcessingState.NOT_STARTED   # Step not started
ProcessingState.IN_PROGRESS   # Currently processing
ProcessingState.COMPLETED     # Successfully completed
ProcessingState.FAILED        # Failed with error
```

#### Status Display

The status tracker provides a rich table view:

```
Batch Processing Status
┏━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ Episode         ┃ Fetch ┃ Transcribe  ┃ Diarize ┃ Export  ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ Episode 1       │   ✓   │      ⏳     │    ○    │    ○    │
│ Episode 2       │   ✓   │      ✓      │    ✓    │    ○    │
│ Episode 3       │   ✗   │      ○      │    ○    │    ○    │
└─────────────────┴───────┴─────────────┴─────────┴─────────┘

Legend: ○ Not Started  ⏳ In Progress  ✓ Completed  ✗ Failed
```

### CLI Commands

The batch module provides three CLI commands:

#### podx-batch-transcribe

Batch transcribe multiple episodes:

```bash
# Auto-detect and transcribe all episodes
podx-batch-transcribe --auto-detect

# Filter by show and date
podx-batch-transcribe --auto-detect --show "My Podcast" --since 2024-01-01

# Use pattern matching
podx-batch-transcribe --pattern "*/episode-audio.wav"

# Configure processing
podx-batch-transcribe \
  --auto-detect \
  --model large-v3 \
  --parallel 4 \
  --max-retries 2 \
  --continue-on-error
```

**Options:**
- `--auto-detect` - Auto-discover episodes
- `--pattern GLOB` - Glob pattern for audio files
- `--show NAME` - Filter by show name
- `--since DATE` - Process episodes since date
- `--date-range START:END` - Date range filter
- `--min-duration SECS` - Minimum duration filter
- `--max-duration SECS` - Maximum duration filter
- `--model NAME` - ASR model (default: large-v3)
- `--parallel N` - Parallel workers (default: 1)
- `--max-retries N` - Retry attempts (default: 0)
- `--retry-delay SECS` - Retry delay (default: 5)
- `--continue-on-error` - Continue on failures (default: true)

#### podx-batch-pipeline

Run full pipeline on multiple episodes:

```bash
# Run all steps
podx-batch-pipeline --auto-detect

# Select specific steps
podx-batch-pipeline \
  --auto-detect \
  --steps transcribe,diarize,export

# Configure export formats
podx-batch-pipeline \
  --auto-detect \
  --export-formats txt,srt,md

# Parallel processing
podx-batch-pipeline --auto-detect --parallel 4
```

**Options:**
- All options from `podx-batch-transcribe`
- `--steps STEPS` - Comma-separated steps (default: all)
  - Available: `transcribe`, `diarize`, `preprocess`, `deepcast`, `export`
- `--export-formats FORMATS` - Export formats (default: txt,srt,md)

#### podx-batch-status

View and manage batch processing status:

```bash
# Display status table
podx-batch-status

# Export to JSON
podx-batch-status --export status.json

# Clear completed episodes
podx-batch-status --clear-completed
```

### Practical Examples

**Batch transcribe with quality check:**

```python
from pathlib import Path
from podx.batch import BatchProcessor, EpisodeDiscovery
from podx.core.audio_quality import AudioQualityAnalyzer
from podx.core.transcribe import TranscribeEngine

# Discover episodes
discovery = EpisodeDiscovery(base_path=Path("episodes"))
episodes = discovery.discover_episodes(auto_detect=True)

# Process with quality-based settings
analyzer = AudioQualityAnalyzer()

def smart_transcribe(episode):
    audio_path = Path(episode["directory"]) / "episode-audio.wav"

    # Analyze audio quality
    analysis = analyzer.analyze(audio_path)
    recommendations = analysis["recommendations"]

    # Use recommended settings
    transcriber = TranscribeEngine(
        model=recommendations["model"],
        vad_filter=recommendations["vad_filter"]
    )
    return transcriber.transcribe(audio_path)

# Process batch
processor = BatchProcessor(parallel_workers=2)
results = processor.process_batch(episodes, smart_transcribe, "Transcribing")
```

**Filter and process recent episodes:**

```python
from datetime import datetime, timedelta
from pathlib import Path
from podx.batch import EpisodeDiscovery, EpisodeFilter, BatchProcessor

# Find episodes from last 7 days
since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

discovery = EpisodeDiscovery(base_path=Path("episodes"))
filters = EpisodeFilter(since=since_date, status="new")
episodes = discovery.discover_episodes(auto_detect=True, filters=filters)

print(f"Found {len(episodes)} new episodes from last 7 days")

# Process them
def process_episode(episode):
    # Your processing logic here
    pass

processor = BatchProcessor(parallel_workers=4, continue_on_error=True)
results = processor.process_batch(episodes, process_episode)
```

**Track pipeline progress:**

```python
from pathlib import Path
from podx.batch import BatchStatus, ProcessingState

# Load status
status = BatchStatus()

# Process episodes with status tracking
for episode in episodes:
    try:
        # Transcribe
        status.update_episode_status(
            episode["title"],
            "transcribe",
            ProcessingState.IN_PROGRESS
        )
        transcribe_result = transcribe(episode)
        status.update_episode_status(
            episode["title"],
            "transcribe",
            ProcessingState.COMPLETED
        )

        # Diarize
        status.update_episode_status(
            episode["title"],
            "diarize",
            ProcessingState.IN_PROGRESS
        )
        diarize_result = diarize(episode)
        status.update_episode_status(
            episode["title"],
            "diarize",
            ProcessingState.COMPLETED
        )

    except Exception as e:
        status.update_episode_status(
            episode["title"],
            current_step,
            ProcessingState.FAILED
        )

    # Save after each episode
    status.save()

# Display final status
status.display_status_table()
```

---

## Audio Quality Module

### Overview

The Audio Quality module (`podx.core.audio_quality`) provides intelligent audio analysis to detect quality issues and recommend optimal transcription settings.

**Key Features:**
- Signal-to-noise ratio (SNR) calculation
- Dynamic range analysis
- Clipping detection
- Silence ratio estimation
- Speech content estimation
- Automatic model recommendations
- Processing suggestions (VAD, noise reduction, etc.)

### AudioQualityAnalyzer

Analyzes audio files and provides comprehensive quality metrics plus recommendations for optimal transcription.

#### Basic Usage

```python
from pathlib import Path
from podx.core.audio_quality import AudioQualityAnalyzer

# Create analyzer
analyzer = AudioQualityAnalyzer()

# Analyze audio file
audio_path = Path("episode-audio.wav")
analysis = analyzer.analyze(audio_path)

# Access quality metrics
quality = analysis["quality"]
print(f"SNR: {quality['snr_db']} dB")
print(f"Dynamic Range: {quality['dynamic_range_db']} dB")
print(f"Clipping: {quality['clipping_ratio']*100:.2f}%")
print(f"Silence: {quality['silence_ratio']*100:.1f}%")
print(f"Speech Content: {quality['speech_ratio']*100:.1f}%")

# Get recommendations
recommendations = analysis["recommendations"]
print(f"Recommended Model: {recommendations['model']}")
print(f"Use VAD Filter: {recommendations['vad_filter']}")

# Review suggestions
for suggestion in recommendations["suggestions"]:
    print(f"[{suggestion['type']}] {suggestion['message']}")
    print(f"  → {suggestion['recommendation']}")
```

#### Analysis Output

The `analyze()` method returns a dictionary with the following structure:

```python
{
    "audio_path": str,              # Path to analyzed file
    "duration_seconds": float,      # Audio duration
    "sample_rate": int,             # Sample rate in Hz
    "quality": {
        "snr_db": float,            # Signal-to-noise ratio (higher is better)
        "dynamic_range_db": float,  # Dynamic range (peak vs RMS)
        "clipping_ratio": float,    # Ratio of clipped samples (0.0-1.0)
        "silence_ratio": float,     # Ratio of silent frames (0.0-1.0)
        "speech_ratio": float,      # Estimated speech content (0.0-1.0)
    },
    "recommendations": {
        "model": str,               # Recommended ASR model
        "vad_filter": bool,         # Whether to use VAD filter
        "suggestions": [            # List of quality suggestions
            {
                "type": str,        # "success", "info", "warning", "error"
                "message": str,     # User-friendly message
                "recommendation": str  # Actionable recommendation
            }
        ]
    }
}
```

#### Quality Metrics

**Signal-to-Noise Ratio (SNR)**
- Measures signal quality vs background noise
- Uses high-pass filtering to isolate noise floor
- `> 30 dB`: Excellent quality
- `20-30 dB`: Good quality
- `10-20 dB`: Fair quality
- `< 10 dB`: Poor quality (recommend large model)

**Dynamic Range**
- Measures variation between loud and quiet parts
- Calculated as peak amplitude vs RMS
- `> 20 dB`: Good dynamic range
- `10-20 dB`: Fair dynamic range
- `< 10 dB`: Low dynamic range (compressed audio)

**Clipping Ratio**
- Detects distortion from samples near maximum amplitude
- `< 0.1%`: Minimal clipping (acceptable)
- `0.1-1%`: Moderate clipping (may affect quality)
- `> 1%`: High clipping (recommend re-recording)

**Silence Ratio**
- Percentage of audio that is silent
- `< 15%`: Low silence (VAD not needed)
- `15-50%`: Moderate silence (VAD recommended)
- `> 50%`: High silence (VAD highly recommended)

**Speech Ratio**
- Estimates speech vs music/noise content
- Uses spectral features (centroid, zero-crossing rate)
- `> 70%`: High speech content
- `30-70%`: Moderate speech content
- `< 30%`: Low speech content (may not be speech audio)

#### Model Recommendations

The analyzer automatically recommends the optimal ASR model based on audio quality:

```python
# Excellent quality (SNR > 30 dB, minimal clipping)
# → "small" (fast, accurate enough)

# Good quality (SNR > 20 dB)
# → "medium" (balanced accuracy/speed)

# Moderate quality (SNR > 15 dB)
# → "large-v3" (better accuracy for challenging audio)

# Poor quality (SNR < 15 dB)
# → "large-v3" (most robust model)
```

#### Practical Examples

**Check audio quality before transcription:**

```python
from pathlib import Path
from podx.core.audio_quality import AudioQualityAnalyzer
from podx.core.transcribe import TranscribeEngine

# Analyze audio
analyzer = AudioQualityAnalyzer()
analysis = analyzer.analyze(Path("podcast.wav"))

# Use recommended settings
recommendations = analysis["recommendations"]
model = recommendations["model"]
vad_filter = recommendations["vad_filter"]

# Transcribe with optimal settings
transcriber = TranscribeEngine(
    model=model,
    vad_filter=vad_filter
)
result = transcriber.transcribe(Path("podcast.wav"))
```

**Batch quality analysis:**

```python
from pathlib import Path
from podx.core.audio_quality import AudioQualityAnalyzer

analyzer = AudioQualityAnalyzer()
audio_files = Path("episodes").glob("*.wav")

for audio_file in audio_files:
    analysis = analyzer.analyze(audio_file)
    quality = analysis["quality"]

    # Flag low-quality files
    if quality["snr_db"] < 15:
        print(f"⚠️  Low quality: {audio_file.name}")
        print(f"   SNR: {quality['snr_db']:.1f} dB")

    # Flag excessive clipping
    if quality["clipping_ratio"] > 0.01:
        print(f"⚠️  Clipping detected: {audio_file.name}")
        print(f"   {quality['clipping_ratio']*100:.2f}% clipped")
```

**Export analysis results:**

```python
import json
from pathlib import Path
from podx.core.audio_quality import AudioQualityAnalyzer

analyzer = AudioQualityAnalyzer()
analysis = analyzer.analyze(Path("episode.wav"))

# Export to JSON
with open("quality-analysis.json", "w") as f:
    json.dump(analysis, f, indent=2)
```

#### CLI Command

The audio quality analyzer is also available as a CLI command:

```bash
# Analyze audio file
podx-analyze-audio episode.wav

# Output as JSON
podx-analyze-audio episode.wav --json

# Export to file
podx-analyze-audio episode.wav --export analysis.json
```

**Output example:**

```
Audio Quality Analysis
============================================================

File: episode.wav
Duration: 45m 32s
Sample Rate: 16000 Hz

Quality Metrics:
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Metric                 ┃ Value     ┃ Rating    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Signal-to-Noise Ratio  │ 25.3 dB   │ Good      │
│ Dynamic Range          │ 18.5 dB   │ Fair      │
│ Clipping               │ 0.02%     │ Minimal   │
│ Silence                │ 12.4%     │ Low       │
│ Speech Content         │ 78.3%     │ High      │
└────────────────────────┴───────────┴───────────┘

Recommendations:
  Model: medium
  VAD Filter: Not needed

Suggestions:
  ✓ Good audio quality
    → medium model recommended for optimal accuracy/speed balance

Suggested Command:
┌────────────────────────────────────────────────────────┐
│ podx-transcribe episode.wav --model medium             │
└────────────────────────────────────────────────────────┘
```

#### Dependencies

The audio quality analyzer requires the optional `audio-analysis` dependency group:

```bash
pip install 'podx[audio-analysis]'
```

This installs:
- `librosa` - Audio analysis library
- `scipy` - Signal processing (included with librosa)

---

## Search Module (NEW in v2.1.0)

**Location:** `podx/search/`

The search module provides powerful transcript search and analysis capabilities, including full-text search, semantic search, quote extraction, and topic clustering.

### Components

1. **TranscriptDatabase** - SQLite FTS5 full-text search
2. **SemanticSearch** - Embedding-based semantic search
3. **QuoteExtractor** - Quote extraction and highlight detection

### Full-Text Search

**Module:** `podx.search.database`

The `TranscriptDatabase` class provides fast keyword search using SQLite FTS5 with BM25 ranking.

#### Key Features

- **FTS5 full-text search** with BM25 ranking
- **Episode indexing** with metadata (title, show, date, duration)
- **Speaker filtering** for targeted search
- **Episode management** (list, delete, get info)
- **Database statistics** (episode count, segment count)

#### Basic Usage

```python
from pathlib import Path
from podx.domain.models.transcript import Transcript
from podx.search import TranscriptDatabase

# Initialize database (defaults to ~/.podx/transcripts.db)
db = TranscriptDatabase()

# Load and index a transcript
transcript = Transcript.from_file(Path("transcript.json"))
metadata = {
    "title": "AI Safety Discussion",
    "show_name": "Lex Fridman Podcast",
    "date": "2024-11-15",
    "duration": 3612.5
}
db.index_transcript("ep001", transcript, metadata)

# Search transcripts
results = db.search("artificial intelligence", limit=10)
for result in results:
    print(f"{result['show_name']} - {result['title']}")
    print(f"  {result['speaker']} @ {result['timestamp']:.1f}s")
    print(f"  {result['text'][:100]}...")
    print()

# Filter by speaker
alice_results = db.search("quantum computing", speaker_filter="Alice")

# List all indexed episodes
episodes = db.list_episodes(limit=20)
for ep in episodes:
    print(f"{ep['episode_id']}: {ep['title']} ({ep['date']})")

# Get database stats
stats = db.get_stats()
print(f"Indexed: {stats['episodes']} episodes, {stats['segments']} segments")
```

### Semantic Search

**Module:** `podx.search.semantic`

The `SemanticSearch` class provides meaning-based search using sentence transformers and FAISS.

#### Key Features

- **Semantic similarity search** with sentence embeddings
- **FAISS vector index** for fast similarity search
- **Topic clustering** with K-means
- **Similar segment discovery**
- **Multiple embedding models** supported

#### Dependencies

Semantic search requires optional dependencies:

```bash
pip install podx[search]
# Or manually:
pip install sentence-transformers~=2.2.0 faiss-cpu>=1.8.0 scikit-learn~=1.3.0
```

#### Basic Usage

```python
from pathlib import Path
from podx.domain.models.transcript import Transcript
from podx.search import SemanticSearch

# Initialize (defaults to ~/.podx/semantic_index/)
semantic = SemanticSearch(model_name="all-MiniLM-L6-v2")

# Index a transcript
transcript = Transcript.from_file(Path("transcript.json"))
metadata = {"title": "AI Safety", "show_name": "Lex Fridman"}
semantic.index_transcript("ep001", transcript, metadata)

# Semantic search (find by meaning, not just keywords)
results = semantic.search("dangers of artificial intelligence", k=5)
for result in results:
    print(f"Similarity: {result['similarity']:.2%}")
    print(f"{result['speaker']} @ {result['timestamp']:.1f}s")
    print(f"{result['text']}")
    print()

# Find similar segments
similar = semantic.find_similar_segments("ep001", timestamp=120.0, k=5)

# Cluster topics
topics = semantic.cluster_topics(n_clusters=10)
for topic in topics:
    rep = topic['representative']
    print(f"Topic {topic['cluster_id'] + 1} ({topic['size']} segments):")
    print(f"  {rep['text'][:100]}...")
```

### Quote Extraction

**Module:** `podx.search.quotes`

The `QuoteExtractor` class identifies and extracts notable quotes using heuristics and quality scoring.

#### Key Features

- **Quality scoring** (0-1 scale) based on quotable patterns
- **Quote extraction** with configurable filters
- **Highlight detection** (temporal clustering of quotes)
- **Speaker grouping** for per-speaker quotes
- **Customizable** word count and quality thresholds

#### Basic Usage

```python
from pathlib import Path
from podx.domain.models.transcript import Transcript
from podx.search import QuoteExtractor

# Initialize extractor
extractor = QuoteExtractor(
    min_words=10,      # Minimum quote length
    max_words=100,     # Maximum quote length
    min_score=0.3      # Minimum quality score
)

# Load transcript
transcript = Transcript.from_file(Path("transcript.json"))

# Extract top quotes
quotes = extractor.extract_quotes(transcript, max_quotes=20)
for quote in quotes:
    score_pct = quote["score"] * 100
    print(f"[{score_pct:.0f}%] {quote['speaker']}:")
    print(f'  "{quote["text"]}"')
    print()

# Extract quotes by speaker
by_speaker = extractor.extract_by_speaker(transcript, top_n=5)
for speaker, speaker_quotes in by_speaker.items():
    print(f"\n{speaker}:")
    for quote in speaker_quotes:
        print(f'  "{quote["text"][:80]}..."')

# Find highlight moments (clusters of good quotes)
highlights = extractor.find_highlights(transcript, duration_threshold=30.0)
for i, highlight in enumerate(highlights, 1):
    start_min = int(highlight["start"] // 60)
    end_min = int(highlight["end"] // 60)
    print(f"\nHighlight {i}: {start_min}:{start_min%60:02d} - {end_min}:{end_min%60:02d}")
    print(f"  {highlight['quote_count']} quotes, avg score: {highlight['avg_score']:.0%}")
    for quote in highlight["quotes"][:3]:
        print(f'  • {quote["text"][:60]}...')
```

#### Quote Scoring Heuristics

The quote scoring algorithm considers:

- **Quotable patterns** (+boost): "I think", "The key is", "The truth is", "Remember"
- **Exclude patterns** (-penalty): Filler words ("um", "uh", "like"), questions
- **Complete sentences** (+boost): Ends with period
- **Data/numbers** (+boost): Contains specific numbers
- **Uncommon words** (+boost): Long words (8+ characters)
- **Length optimization** (+/-): Prefers 15-60 words

### CLI Commands

The search module is also available via CLI commands:

#### podx-search

```bash
# Index a transcript
podx-search index transcript.json --episode-id ep001 --title "AI Safety"

# Keyword search
podx-search query "artificial intelligence" --limit 10

# Semantic search
podx-search query "dangers of AI" --semantic --limit 5

# List indexed episodes
podx-search list --show "Lex Fridman"

# Show statistics
podx-search stats
```

#### podx-analyze

```bash
# Extract quotes
podx-analyze quotes transcript.json --max-quotes 20

# Group quotes by speaker
podx-analyze quotes transcript.json --by-speaker

# Find highlights
podx-analyze highlights transcript.json --duration 30

# Cluster topics (requires semantic search)
podx-analyze topics ep001 --clusters 10

# Speaker statistics
podx-analyze speakers transcript.json
```

### Performance Considerations

#### Database Size

- SQLite FTS5 index size: ~2-3x the size of original transcript JSON
- FAISS semantic index: ~1.5KB per segment (384-dim embeddings)
- Recommended: Store indices on SSD for best performance

#### Search Performance

- **FTS5 keyword search**: <10ms for typical queries (100K segments)
- **Semantic search**: ~50-100ms for k=10 (after initial embedding load)
- **Topic clustering**: 1-5 seconds for 1000 segments (K-means)

#### Optimization Tips

1. **Batch indexing**: Index multiple transcripts in one session to amortize model loading
2. **Custom embeddings**: Use smaller models (e.g., "all-MiniLM-L6-v2") for faster embedding
3. **Filter early**: Use episode/speaker filters to reduce search space
4. **Cache results**: Semantic search results can be cached for repeated queries

### Dependencies

**Core (included):**
- `sqlite3` - Full-text search (Python standard library)

**Optional (for semantic search):**
- `sentence-transformers~=2.2.0` - Embedding models
- `faiss-cpu>=1.8.0` - Vector similarity search
- `scikit-learn~=1.3.0` - Clustering algorithms
- `numpy` - Array operations

---

## Additional Resources

- **[Progress Reporting API](./PROGRESS_REPORTING.md)** - **NEW:** Unified progress reporting for CLI, web API, and testing
- **[Architecture Guide](./ARCHITECTURE_V2.md)** - Deep dive into v2.0 architecture
- **[Testing Guide](./TESTING.md)** - Testing patterns and best practices
- **[Configuration Guide](./CONFIGURATION.md)** - YAML configuration
- **[Plugin System](./PLUGINS.md)** - Creating custom plugins

---

## Support

For questions and issues:
- 📖 Read the documentation
- 🐛 Report bugs on GitHub Issues
- 💬 Ask questions in GitHub Discussions
