# PodX Python API Examples

This directory contains examples demonstrating how to use the PodX Python API for podcast processing.

## Files

### `basic_usage.py`
Demonstrates the synchronous `PodxClient` for straightforward operations:
- Fetching podcast episodes
- Transcribing audio files
- Adding speaker identification (diarization)
- AI analysis with deepcast
- Exporting to different formats
- Publishing to Notion
- Complete pipeline examples

**Best for**: Simple scripts, batch processing, CLI tools

### `async_usage.py`
Demonstrates the asynchronous `AsyncPodxClient` with real-time progress updates:
- Progress callbacks for real-time updates
- Streaming progress with async generators
- Parallel processing of multiple files
- WebSocket integration patterns
- Error handling
- Complete async pipelines

**Best for**: Web applications, UIs, monitoring tools, long-running operations

## Quick Start

### Synchronous API

```python
from podx.api.client import PodxClient

client = PodxClient()

# Transcribe an audio file
result = client.transcribe(
    audio_url="podcast.mp3",
    asr_model="base",
    out_dir="./output"
)

if result.success:
    print(f"Transcript: {result.transcript_path}")
else:
    print(f"Error: {result.error}")
```

### Asynchronous API with Progress

```python
import asyncio
from podx.api.client import AsyncPodxClient

async def main():
    client = AsyncPodxClient()

    # Progress callback
    async def on_progress(update: dict):
        print(f"Progress: {update.get('message')}")

    # Transcribe with real-time updates
    result = await client.transcribe(
        audio_path="podcast.mp3",
        model="base",
        progress_callback=on_progress
    )

    print(f"Done! {result.transcript_path}")

asyncio.run(main())
```

### Streaming Progress (Async Generator)

```python
async def main():
    client = AsyncPodxClient()

    # Stream progress updates
    async for update in client.transcribe_stream("podcast.mp3"):
        if isinstance(update, dict):
            # Progress update
            print(f"Progress: {update['message']}")
        else:
            # Final result
            print(f"Complete: {update.transcript_path}")

asyncio.run(main())
```

## Common Use Cases

### Web Application Backend

Use `AsyncPodxClient` with WebSocket or Server-Sent Events to stream progress to frontend:

```python
from fastapi import FastAPI, WebSocket
from podx.api.client import AsyncPodxClient

app = FastAPI()
client = AsyncPodxClient()

@app.websocket("/transcribe")
async def transcribe_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Progress callback sends updates via WebSocket
    async def send_progress(update: dict):
        await websocket.send_json({
            "type": "progress",
            "data": update
        })

    # Transcribe with progress streaming
    result = await client.transcribe(
        audio_path="episode.mp3",
        progress_callback=send_progress
    )

    # Send final result
    await websocket.send_json({
        "type": "complete",
        "data": result.to_dict()
    })
```

### Batch Processing

Process multiple files in parallel:

```python
import asyncio
from podx.api.client import AsyncPodxClient

async def process_episodes(files: list[str]):
    client = AsyncPodxClient()

    # Create tasks for all files
    tasks = [
        client.transcribe(audio_path=f, model="base")
        for f in files
    ]

    # Process in parallel
    results = await asyncio.gather(*tasks)

    # Check results
    for f, result in zip(files, results):
        if result.success:
            print(f"✓ {f}: {result.transcript_path}")
        else:
            print(f"✗ {f}: {result.error}")

# Run
asyncio.run(process_episodes([
    "episode1.mp3",
    "episode2.mp3",
    "episode3.mp3"
]))
```

### Complete Pipeline

Process an episode from start to finish:

```python
from pathlib import Path
from podx.api.client import PodxClient, ClientConfig

# Configure client
client = PodxClient(
    config=ClientConfig(
        default_model="base",
        default_llm_model="gpt-4o",
        output_dir=Path("./episodes")
    )
)

# 1. Fetch episode
fetch_result = client.fetch_episode(
    show_name="Lex Fridman Podcast",
    date="2024-01-20"
)

# 2. Transcribe
transcript_result = client.transcribe(
    audio_url=fetch_result.audio_path
)

# 3. Identify speakers
diarize_result = client.diarize(
    transcript_path=transcript_result.transcript_path,
    num_speakers=2
)

# 4. Analyze with AI
analysis_result = client.deepcast(
    transcript_path=diarize_result.transcript_path,
    analysis_type="outline"
)

# 5. Export to formats
export_result = client.export(
    transcript_path=diarize_result.transcript_path,
    formats=["txt", "srt", "md"]
)

print(f"Pipeline complete!")
print(f"Analysis: {analysis_result.markdown_path}")
```

## Response Models

All API methods return Pydantic models with type safety:

- `FetchResponse` - Episode fetch results
- `TranscribeResponse` - Transcription results
- `DiarizeResponse` - Speaker diarization results
- `DeepcastResponse` - AI analysis results
- `ExportResponse` - Export results
- `NotionResponse` - Notion publishing results

Each response includes:
- `success: bool` - Whether operation succeeded
- `error: Optional[str]` - Error message if failed
- Type-specific fields (paths, metadata, stats)

## Error Handling

All methods return responses with `success` and `error` fields instead of raising exceptions:

```python
result = client.transcribe("audio.mp3")

if result.success:
    # Process successful result
    print(f"Transcript: {result.transcript_path}")
else:
    # Handle error
    print(f"Failed: {result.error}")
```

For async operations, exceptions may still be raised for validation errors:

```python
try:
    result = await client.transcribe(
        audio_path="nonexistent.mp3"
    )
except ValidationError as e:
    print(f"Invalid input: {e}")
```

## Running Examples

```bash
# Run basic examples
python examples/api/basic_usage.py

# Run async examples
python examples/api/async_usage.py
```

Uncomment specific examples in the `__main__` section to run them.

## API Documentation

See the main API documentation in `docs/api/` for complete reference.

## Support

For issues or questions:
- GitHub Issues: https://github.com/evanhourigan/podx/issues
- Documentation: See `docs/` directory
