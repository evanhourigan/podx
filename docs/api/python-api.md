# PodX Python API

The PodX Python API provides a clean, type-safe interface for podcast processing operations. It's designed for developers building web applications, automation tools, or custom workflows.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [API Clients](#api-clients)
4. [Methods Reference](#methods-reference)
5. [Response Models](#response-models)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Advanced: Multi-Provider LLM Support](#advanced-multi-provider-llm-support)
9. [Advanced: Progress Reporting](#advanced-progress-reporting-with-progressreporter)

## Installation

```bash
pip install podx
```

Or for development:

```bash
git clone https://github.com/evanhourigan/podx.git
cd podx
pip install -e .
```

## Quick Start

### Synchronous API

For simple scripts and batch processing:

```python
from podx.api.client import PodxClient

# Create client
client = PodxClient()

# Transcribe audio
result = client.transcribe(
    audio_url="podcast.mp3",
    asr_model="base",
    out_dir="./output"
)

if result.success:
    print(f"Transcript saved to: {result.transcript_path}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Segments: {result.segments_count}")
else:
    print(f"Error: {result.error}")
```

### Asynchronous API

For web applications and real-time progress:

```python
import asyncio
from podx.api.client import AsyncPodxClient

async def main():
    client = AsyncPodxClient()

    # Progress callback
    async def on_progress(update: dict):
        print(f"[{update.get('percent', 0)}%] {update.get('message')}")

    # Transcribe with progress
    result = await client.transcribe(
        audio_path="podcast.mp3",
        model="base",
        progress_callback=on_progress
    )

    print(f"Done: {result.transcript_path}")

asyncio.run(main())
```

## API Clients

### PodxClient

Synchronous client for straightforward operations.

```python
from podx.api.client import PodxClient, ClientConfig

# Create with custom config
client = PodxClient(
    config=ClientConfig(
        default_model="base",           # Default ASR model
        default_llm_model="gpt-4o",     # Default LLM model
        output_dir=Path("./episodes"),  # Default output directory
        cache_enabled=True,             # Enable result caching
        validate_inputs=True,           # Validate before processing
        verbose=False,                  # Enable verbose logging
    )
)
```

**Use when:**
- Building simple scripts or CLI tools
- Processing files in sequence
- You don't need real-time progress updates

### AsyncPodxClient

Asynchronous client with progress callback support.

```python
from podx.api.client import AsyncPodxClient, ClientConfig

# Create async client
client = AsyncPodxClient(
    config=ClientConfig(default_model="base")
)
```

**Use when:**
- Building web applications (FastAPI, Flask, etc.)
- You need real-time progress updates
- Processing multiple files in parallel
- Streaming progress to WebSocket clients

## Methods Reference

### PodxClient Methods

#### `fetch_episode()`

Fetch a podcast episode by show name or RSS URL.

```python
result = client.fetch_episode(
    show_name: Optional[str] = None,           # Show name to search
    rss_url: Optional[str] = None,             # Or direct RSS URL
    date: Optional[str] = None,                # Episode date (YYYY-MM-DD)
    title_contains: Optional[str] = None,      # Filter by title
    output_dir: Optional[Path] = None,         # Output directory
) -> FetchResponse
```

**Returns:** `FetchResponse` with episode metadata and audio file path.

**Example:**

```python
result = client.fetch_episode(
    show_name="Lex Fridman Podcast",
    date="2024-01-20",
    output_dir=Path("./episodes")
)

if result.success:
    print(f"Title: {result.episode_meta['title']}")
    print(f"Audio: {result.audio_path}")
```

#### `transcribe()`

Transcribe audio to text using ASR (Automatic Speech Recognition).

```python
result = client.transcribe(
    audio_url: str,                           # Path or URL to audio
    asr_model: Optional[str] = None,          # ASR model (tiny, base, small, medium, large)
    out_dir: Optional[str] = None,            # Output directory
    provider_keys: Optional[Dict] = None,     # API keys for providers
) -> TranscribeResponse
```

**Returns:** `TranscribeResponse` with transcript path and metadata.

**Example:**

```python
result = client.transcribe(
    audio_url="episode.mp3",
    asr_model="base",  # Options: tiny, base, small, medium, large, large-v2, large-v3
    out_dir="./output"
)

if result.success:
    print(f"Model: {result.model_used}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Segments: {result.segments_count}")
    print(f"Transcript: {result.transcript_path}")
```

#### `diarize()`

Add speaker identification to a transcript.

```python
result = client.diarize(
    transcript_path: str | Path,              # Path to transcript JSON
    audio_path: Optional[str | Path] = None,  # Audio path (auto-detected if None)
    num_speakers: Optional[int] = None,       # Exact number of speakers (if known)
    min_speakers: Optional[int] = None,       # Minimum speakers
    max_speakers: Optional[int] = None,       # Maximum speakers
    output_dir: Optional[Path] = None,        # Output directory
) -> DiarizeResponse
```

**Returns:** `DiarizeResponse` with diarized transcript path and speaker count.

**Example:**

```python
# If you know exact number of speakers
result = client.diarize(
    transcript_path="transcript-base.json",
    num_speakers=2
)

# Or specify range
result = client.diarize(
    transcript_path="transcript-base.json",
    min_speakers=2,
    max_speakers=4
)

if result.success:
    print(f"Speakers found: {result.speakers_found}")
    print(f"Output: {result.transcript_path}")
```

#### `deepcast()`

Analyze transcript with AI to generate insights, summaries, and structured content.

```python
result = client.deepcast(
    transcript_path: str,                     # Path to transcript JSON
    llm_model: Optional[str] = None,          # LLM model (gpt-4o, claude-3-opus, etc.)
    analysis_type: str = "outline",           # Type: brief, quotes, outline, full
    out_dir: Optional[str] = None,            # Output directory
    provider_keys: Optional[Dict] = None,     # API keys
) -> DeepcastResponse
```

**Returns:** `DeepcastResponse` with markdown analysis and usage stats.

**Analysis Types:**
- `brief` - Quick summary with key points
- `quotes` - Extracted notable quotes
- `outline` - Structured outline with topics and timestamps
- `full` - Comprehensive analysis with all sections

**Example:**

```python
result = client.deepcast(
    transcript_path="transcript-diarized.json",
    llm_model="gpt-4o",
    analysis_type="outline"
)

if result.success:
    print(f"Analysis: {result.markdown_path}")
    print(f"Model: {result.model_used}")
    if result.usage:
        print(f"Tokens: {result.usage}")
```

#### `export()`

Export transcript to different formats.

```python
result = client.export(
    transcript_path: str | Path,              # Path to transcript JSON
    formats: list[str],                       # List of formats: txt, srt, vtt, md
    output_dir: Optional[Path] = None,        # Output directory
) -> ExportResponse
```

**Returns:** `ExportResponse` with paths to exported files.

**Supported Formats:**
- `txt` - Plain text transcript
- `srt` - SubRip subtitles (with timestamps)
- `vtt` - WebVTT subtitles (for web video)
- `md` - Markdown formatted transcript

**Example:**

```python
result = client.export(
    transcript_path="transcript-diarized.json",
    formats=["txt", "srt", "vtt", "md"]
)

if result.success:
    print(f"Exported to {len(result.formats)} formats:")
    for fmt, path in result.output_files.items():
        print(f"  {fmt.upper()}: {path}")
```

#### `publish_to_notion()`

Publish deepcast analysis to a Notion database.

```python
result = client.publish_to_notion(
    markdown_path: str | Path,                # Path to markdown file
    notion_token: str,                        # Notion integration token
    database_id: str,                         # Notion database ID
    episode_meta: Optional[Dict] = None,      # Additional metadata
) -> NotionResponse
```

**Returns:** `NotionResponse` with Notion page URL and ID.

**Example:**

```python
result = client.publish_to_notion(
    markdown_path="episode-outline.md",
    notion_token="secret_xxx",  # Get from notion.so/my-integrations
    database_id="abc123",       # Get from database URL
    episode_meta={
        "title": "Episode Title",
        "date": "2024-01-20",
        "show": "Podcast Name"
    }
)

if result.success:
    print(f"Published to: {result.page_url}")
    print(f"Page ID: {result.page_id}")
```

### AsyncPodxClient Methods

The async client provides async versions of long-running operations with progress support.

#### `transcribe()` (Async)

```python
result = await client.transcribe(
    audio_path: str | Path,
    model: Optional[str] = None,
    asr_provider: str = "auto",
    compute: str = "auto",
    output_dir: Optional[Path] = None,
    progress_callback: Optional[AsyncProgressCallback] = None,
) -> TranscribeResponse
```

**Progress callback receives:**
```python
{
    "type": "progress",
    "stage": "transcribing",
    "message": "Processing audio...",
    "percent": 45  # Optional progress percentage
}
```

**Example:**

```python
async def on_progress(update: dict):
    print(f"[{update.get('percent', 0)}%] {update.get('message')}")

result = await client.transcribe(
    audio_path="podcast.mp3",
    model="base",
    progress_callback=on_progress
)
```

#### `transcribe_stream()` (Async Generator)

Stream progress updates as an async generator.

```python
async for update in client.transcribe_stream(
    audio_path: str | Path,
    model: Optional[str] = None,
    asr_provider: str = "auto",
    compute: str = "auto",
    output_dir: Optional[Path] = None,
) -> AsyncIterator[Dict[str, Any] | TranscribeResponse]:
    # Yields progress dicts, then final TranscribeResponse
    pass
```

**Example:**

```python
async for update in client.transcribe_stream("podcast.mp3"):
    if isinstance(update, dict):
        # Progress update
        print(f"Progress: {update['message']}")
    else:
        # Final TranscribeResponse
        print(f"Complete: {update.transcript_path}")
```

#### `diarize()` (Async)

```python
result = await client.diarize(
    transcript_path: str | Path,
    audio_path: Optional[str | Path] = None,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[AsyncProgressCallback] = None,
) -> DiarizeResponse
```

#### `diarize_stream()` (Async Generator)

Similar to `transcribe_stream()`, yields progress updates then final result.

## Response Models

All API methods return Pydantic models with type safety and validation.

### FetchResponse

```python
class FetchResponse(BaseModel):
    episode_meta: Dict[str, Any]          # Episode metadata (title, show, date, etc.)
    audio_meta: Optional[Dict[str, Any]]  # Audio file metadata
    audio_path: str                       # Path to downloaded audio
    metadata_path: Optional[str]          # Path to metadata JSON
    success: bool = True                  # Whether fetch succeeded
    error: Optional[str] = None           # Error message if failed

    def to_dict() -> Dict[str, Any]:
        """Convert to dictionary."""
```

### TranscribeResponse

```python
class TranscribeResponse(BaseModel):
    transcript_path: str                  # Path to transcript JSON
    duration_seconds: int                 # Audio duration in seconds
    model_used: Optional[str]             # ASR model used
    segments_count: Optional[int]         # Number of transcript segments
    audio_path: Optional[str]             # Path to audio file
    success: bool = True                  # Whether transcription succeeded
    error: Optional[str] = None           # Error message if failed

    def to_dict() -> Dict[str, Any]:
        """Convert to dictionary."""
```

### DiarizeResponse

```python
class DiarizeResponse(BaseModel):
    transcript_path: str                  # Path to diarized transcript
    speakers_found: int                   # Number of unique speakers
    transcript: Optional[Dict[str, Any]]  # Full transcript data
    success: bool = True                  # Whether diarization succeeded
    error: Optional[str] = None           # Error message if failed

    def to_dict() -> Dict[str, Any]:
        """Convert to dictionary."""
```

### DeepcastResponse

```python
class DeepcastResponse(BaseModel):
    markdown_path: str                    # Path to markdown file
    json_path: Optional[str]              # Path to JSON output (if generated)
    usage: Optional[Dict[str, int]]       # Token usage stats
    prompt_used: Optional[str]            # Prompt used for analysis
    model_used: Optional[str]             # LLM model used
    analysis_type: Optional[str]          # Type of analysis
    success: bool = True                  # Whether analysis succeeded
    error: Optional[str] = None           # Error message if failed

    def to_dict() -> Dict[str, Any]:
        """Convert to dictionary."""
```

### ExportResponse

```python
class ExportResponse(BaseModel):
    output_files: Dict[str, str]          # Format -> file path mapping
    formats: list[str]                    # List of exported formats
    success: bool = True                  # Whether export succeeded
    error: Optional[str] = None           # Error message if failed

    def to_dict() -> Dict[str, Any]:
        """Convert to dictionary."""
```

### NotionResponse

```python
class NotionResponse(BaseModel):
    page_url: str                         # URL of Notion page
    page_id: str                          # Notion page ID
    database_id: Optional[str]            # Database ID where page was created
    success: bool = True                  # Whether publish succeeded
    error: Optional[str] = None           # Error message if failed

    def to_dict() -> Dict[str, Any]:
        """Convert to dictionary."""
```

## Error Handling

### Response-Based Error Handling

All methods return response objects with `success` and `error` fields:

```python
result = client.transcribe("audio.mp3")

if result.success:
    # Handle success
    process_transcript(result.transcript_path)
else:
    # Handle error
    logger.error(f"Transcription failed: {result.error}")
    notify_user(result.error)
```

### Exception Handling

Validation errors are raised as exceptions:

```python
from podx.errors import ValidationError, AudioError

try:
    result = client.transcribe(
        audio_url="",  # Invalid: empty path
        asr_model="base"
    )
except ValidationError as e:
    print(f"Invalid input: {e}")
except AudioError as e:
    print(f"Audio processing failed: {e}")
```

### Async Error Handling

```python
try:
    result = await async_client.transcribe(
        audio_path="nonexistent.mp3"
    )

    if not result.success:
        # Operation failed but didn't raise exception
        logger.error(f"Failed: {result.error}")

except ValidationError as e:
    # Input validation failed
    print(f"Invalid input: {e}")
except Exception as e:
    # Unexpected error
    logger.exception("Unexpected error", exc_info=e)
```

## Best Practices

### 1. Use Configuration for Defaults

```python
from pathlib import Path
from podx.api.client import PodxClient, ClientConfig

# Configure once, use everywhere
config = ClientConfig(
    default_model="base",
    default_llm_model="gpt-4o",
    output_dir=Path("./episodes"),
    cache_enabled=True,
    validate_inputs=True,
)

client = PodxClient(config=config)

# Now methods use configured defaults
result = client.transcribe("audio.mp3")  # Uses config.default_model
```

### 2. Check Success Before Proceeding

```python
# Bad: Assuming success
result = client.transcribe("audio.mp3")
process_file(result.transcript_path)  # May fail if result.success is False!

# Good: Check success
result = client.transcribe("audio.mp3")
if result.success:
    process_file(result.transcript_path)
else:
    handle_error(result.error)
```

### 3. Use Async for Web Applications

```python
from fastapi import FastAPI, WebSocket
from podx.api.client import AsyncPodxClient

app = FastAPI()
client = AsyncPodxClient()

@app.websocket("/ws/transcribe")
async def transcribe_websocket(websocket: WebSocket):
    await websocket.accept()

    # Stream progress via WebSocket
    async def send_progress(update: dict):
        await websocket.send_json({
            "type": "progress",
            "data": update
        })

    result = await client.transcribe(
        audio_path="audio.mp3",
        progress_callback=send_progress
    )

    await websocket.send_json({
        "type": "complete",
        "data": result.to_dict()
    })
```

### 4. Process Multiple Files in Parallel

```python
import asyncio
from podx.api.client import AsyncPodxClient

async def process_batch(files: list[str]):
    client = AsyncPodxClient()

    # Create tasks for parallel processing
    tasks = [
        client.transcribe(audio_path=f, model="base")
        for f in files
    ]

    # Wait for all to complete
    results = await asyncio.gather(*tasks)

    # Process results
    for file, result in zip(files, results):
        if result.success:
            print(f"✓ {file}")
        else:
            print(f"✗ {file}: {result.error}")

# Run batch
asyncio.run(process_batch([
    "episode1.mp3",
    "episode2.mp3",
    "episode3.mp3"
]))
```

### 5. Use Type Hints

```python
from podx.api.client import PodxClient
from podx.api.models import TranscribeResponse

def process_podcast(audio_path: str, client: PodxClient) -> TranscribeResponse:
    """Process podcast with type safety."""
    result: TranscribeResponse = client.transcribe(
        audio_url=audio_path,
        asr_model="base"
    )

    return result
```

### 6. Log Errors Properly

```python
import logging
from podx.api.client import PodxClient

logger = logging.getLogger(__name__)

def safe_transcribe(audio_path: str) -> bool:
    """Transcribe with proper error logging."""
    client = PodxClient()

    try:
        result = client.transcribe(audio_url=audio_path)

        if result.success:
            logger.info(f"Transcription complete: {result.transcript_path}")
            return True
        else:
            logger.error(
                f"Transcription failed",
                extra={
                    "audio_path": audio_path,
                    "error": result.error
                }
            )
            return False

    except Exception as e:
        logger.exception(
            f"Unexpected error during transcription",
            exc_info=e,
            extra={"audio_path": audio_path}
        )
        return False
```

## Advanced: Multi-Provider LLM Support

**NEW in Phase 6:** PodX supports multiple LLM providers through a unified abstraction layer. This allows you to easily switch between OpenAI, Anthropic, OpenRouter, and local models (Ollama) without changing your code.

### Using LLM Providers

```python
from podx.llm import get_provider

# OpenAI (GPT-4, GPT-4o, GPT-4o-mini)
openai = get_provider("openai", api_key="sk-...")
response = openai.complete(
    messages=[{"role": "user", "content": "Summarize this transcript"}],
    model="gpt-4o"
)
print(response.content)

# Anthropic (Claude 3.5 Sonnet, Haiku)
anthropic = get_provider("anthropic", api_key="sk-ant-...")
response = anthropic.complete(
    messages=[{"role": "user", "content": "Analyze this podcast"}],
    model="claude-3-5-sonnet-20241022"
)

# OpenRouter (access to many models)
openrouter = get_provider("openrouter", api_key="sk-or-...")
response = openrouter.complete(
    messages=[{"role": "user", "content": "Extract key points"}],
    model="anthropic/claude-3.5-sonnet"
)

# Ollama (local models, FREE)
ollama = get_provider("ollama")
response = ollama.complete(
    messages=[{"role": "user", "content": "Generate summary"}],
    model="llama2"
)
```

### Using LLM Providers with Core Engines

```python
from podx.core.deepcast import DeepcastEngine
from podx.llm import get_provider

# Use Claude for AI analysis
claude = get_provider("anthropic", api_key="sk-ant-...")
engine = DeepcastEngine(llm_provider=claude, model="claude-3-5-sonnet-20241022")

# Process transcript
markdown, insights = engine.deepcast(
    transcript=transcript_data,
    metadata={"title": "Episode 1", "show_name": "My Podcast"}
)

# Or use local Ollama (no API costs)
ollama = get_provider("ollama")
engine = DeepcastEngine(llm_provider=ollama, model="llama2")
markdown, insights = engine.deepcast(transcript, metadata)
```

### Async LLM Support

All LLM providers support async completion for non-blocking operations:

```python
from podx.llm import get_provider
import asyncio

async def analyze_transcript():
    provider = get_provider("openai", api_key="sk-...")

    # Async completion
    response = await provider.complete_async(
        messages=[{"role": "user", "content": "Summarize this"}],
        model="gpt-4o"
    )

    return response.content

# Run async
summary = asyncio.run(analyze_transcript())
```

### Available LLM Providers

| Provider | Models | Cost | Setup |
|----------|--------|------|-------|
| **OpenAI** | gpt-4o, gpt-4, gpt-4o-mini | Paid | API key required |
| **Anthropic** | claude-3-5-sonnet, claude-3-haiku | Paid | API key required |
| **OpenRouter** | 100+ models | Varies | API key required |
| **Ollama** | llama2, mistral, mixtral, phi-2 | FREE | Local installation |

### Custom LLM Provider

You can create your own LLM provider by implementing the `LLMProvider` interface:

```python
from podx.llm.base import LLMProvider, LLMResponse, LLMMessage
from typing import List, Optional

class MyCustomProvider(LLMProvider):
    """Custom LLM provider implementation."""

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key

    def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Synchronous completion."""
        # Your implementation here
        response_text = self._call_custom_api(messages, model)
        return LLMResponse(
            content=response_text,
            model=model,
            usage={"prompt_tokens": 100, "completion_tokens": 50}
        )

    async def complete_async(
        self,
        messages: List[LLMMessage],
        model: str,
        **kwargs
    ) -> LLMResponse:
        """Async completion."""
        # Your async implementation
        pass

# Register custom provider
from podx.llm.factory import register_provider
register_provider("custom", MyCustomProvider)

# Use custom provider
provider = get_provider("custom", api_key="...")
```

**For more details on LLM providers, see [ADVANCED.md](../ADVANCED.md#multi-provider-llm-support).**

---

## Advanced: Progress Reporting with ProgressReporter

For more granular control over progress reporting, you can use the `ProgressReporter` abstraction directly with core engines. This is especially useful for web API integration with Server-Sent Events (SSE) or WebSocket.

### Using APIProgressReporter for Real-Time Updates

```python
from podx.core.transcribe import TranscribeEngine
from podx.progress import APIProgressReporter
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()

@app.post("/transcribe")
async def transcribe_audio(audio_path: str):
    """Stream transcription progress via SSE."""
    progress = APIProgressReporter()

    # Start transcription in background
    async def run_transcription():
        engine = TranscribeEngine(
            model="large-v3",
            progress=progress  # Use ProgressReporter
        )
        return engine.transcribe(audio_path)

    task = asyncio.create_task(run_transcription())
    last_timestamp = 0.0

    # Stream events
    async def event_stream():
        nonlocal last_timestamp
        while not task.done():
            events = progress.get_events(since=last_timestamp)
            for event in events:
                yield f"data: {json.dumps({
                    'type': event.type,
                    'message': event.message,
                    'progress': event.progress
                })}\n\n"
                last_timestamp = event.timestamp
            await asyncio.sleep(0.1)

        result = await task
        yield f"data: {json.dumps({
            'type': 'complete',
            'result': str(result)
        })}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Client-Side JavaScript for SSE

```javascript
const eventSource = new EventSource('/transcribe?audio_path=podcast.mp3');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'update') {
        // Update progress bar
        updateProgressBar(data.progress * 100);
        console.log(data.message);
    } else if (data.type === 'complete') {
        console.log('Transcription complete!');
        eventSource.close();
    }
};
```

### WebSocket Integration

```python
from fastapi import WebSocket
from podx.core.deepcast import DeepcastEngine
from podx.progress import APIProgressReporter

@app.websocket("/ws/deepcast")
async def deepcast_websocket(websocket: WebSocket):
    await websocket.accept()

    # Receive request
    data = await websocket.receive_json()
    transcript = data["transcript"]

    # Setup progress reporter
    progress = APIProgressReporter()
    engine = DeepcastEngine(model="gpt-4o", progress=progress)

    # Run analysis in background
    async def run_analysis():
        return engine.deepcast(transcript)

    task = asyncio.create_task(run_analysis())
    last_timestamp = 0.0

    # Stream progress updates
    while not task.done():
        events = progress.get_events(since=last_timestamp)
        for event in events:
            await websocket.send_json({
                "type": event.type,
                "message": event.message,
                "progress": event.progress
            })
            last_timestamp = event.timestamp
        await asyncio.sleep(0.1)

    # Send result
    result = await task
    await websocket.send_json({
        "type": "complete",
        "result": result
    })
```

**For comprehensive documentation on progress reporting, see [Progress Reporting API](../PROGRESS_REPORTING.md).**

## See Also

- [Progress Reporting API](../PROGRESS_REPORTING.md) - **NEW:** Unified progress reporting for CLI, web API, and testing
- [Examples](../../examples/api/README.md) - Complete working examples
- [CLI Documentation](../cli/README.md) - Command-line interface
- [Architecture](../ARCHITECTURE.md) - System design and patterns

## Support

- GitHub Issues: https://github.com/evanhourigan/podx/issues
- Documentation: https://github.com/evanhourigan/podx/tree/main/docs
