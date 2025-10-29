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

### Progress Callbacks

Progress callbacks allow UI integration without coupling core logic to UI frameworks:

```python
from typing import Callable, Optional

def my_callback(message: str):
    """Progress callback receives status messages."""
    print(f"Status: {message}")

engine = SomeEngine(progress_callback=my_callback)
result = engine.process(input_data)
```

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

## Additional Resources

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
