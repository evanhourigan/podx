# ⚡ PodX Advanced Usage Guide

Master PodX's advanced features for power users, developers, and production deployments.

---

## Table of Contents

- [Multi-Provider LLM Support](#multi-provider-llm-support)
- [Custom Models & Providers](#custom-models--providers)
- [Progress Reporting & Real-Time Updates](#progress-reporting--real-time-updates)
- [Batch Processing & Automation](#batch-processing--automation)
- [Python API Deep Dive](#python-api-deep-dive)
- [Performance Optimization](#performance-optimization)
- [Integration Examples](#integration-examples)
- [Production Deployment](#production-deployment)

---

## Multi-Provider LLM Support

PodX supports multiple LLM providers for AI analysis. Choose based on your needs:

### Supported Providers

| Provider | Models | Best For |
|----------|---------|----------|
| **OpenAI** | GPT-4, GPT-4-turbo, GPT-4o | Production, quality |
| **Anthropic** | Claude Sonnet, Claude Opus | Long context, analysis |
| **OpenRouter** | Multi-model access | Flexibility, testing |
| **Ollama** | Local models (Llama, etc.) | Privacy, no API costs |

### Using Different Providers

#### OpenAI (Default)

```bash
export OPENAI_API_KEY="sk-..."
podx deepcast --model gpt-4o < transcript.json
```

#### Anthropic Claude

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
podx deepcast --provider anthropic --model claude-3-opus < transcript.json
```

#### OpenRouter (Multi-Model)

```bash
export OPENROUTER_API_KEY="sk-or-..."
podx deepcast --provider openrouter --model gpt-4 < transcript.json
```

#### Ollama (Local Models)

```bash
# Start Ollama server
ollama serve

# Pull a model
ollama pull llama2

# Use in PodX
podx deepcast --provider ollama --model llama2 < transcript.json
```

### Python API with Multiple Providers

```python
from podx.llm import get_provider

# OpenAI
openai_provider = get_provider("openai", api_key="sk-...")
response = openai_provider.complete(
    messages=[{"role": "user", "content": "Hello"}],
    model="gpt-4o"
)

# Anthropic
anthropic_provider = get_provider("anthropic", api_key="sk-ant-...")
response = anthropic_provider.complete(
    messages=[{"role": "user", "content": "Hello"}],
    model="claude-3-opus"
)

# Ollama (local)
ollama_provider = get_provider("ollama")
response = ollama_provider.complete(
    messages=[{"role": "user", "content": "Hello"}],
    model="llama2"
)
```

---

## Custom Models & Providers

### ASR Provider Selection

PodX supports three ASR (Automatic Speech Recognition) providers:

#### 1. Local (faster-whisper) - Default

**Pros**: Privacy, no API costs, good quality
**Cons**: Slower than cloud, requires more disk space

```bash
podx transcribe --asr-provider local --model large-v3-turbo
```

**Available Models**:
- `tiny`, `tiny.en`
- `base`, `base.en`
- `small`, `small.en`
- `medium`, `medium.en`
- `large-v2`, `large-v3`, `large-v3-turbo`

#### 2. OpenAI API

**Pros**: Fastest, always up-to-date
**Cons**: Costs money, requires internet

```bash
export OPENAI_API_KEY="sk-..."
podx transcribe --asr-provider openai --model whisper-1
```

#### 3. HuggingFace

**Pros**: Alternative cloud option, more model choices
**Cons**: Slower than OpenAI, requires API key

```bash
export HF_TOKEN="hf_..."
podx transcribe --asr-provider hf --model large-v3
```

### Model Aliases & Shortcuts

PodX provides convenient aliases:

```bash
# These are equivalent:
podx transcribe --model large-v3-turbo
podx transcribe --model local:large-v3-turbo
podx transcribe --asr-provider local --model large-v3-turbo

# OpenAI shortcuts:
podx transcribe --model openai:whisper-1
podx transcribe --asr-provider openai --model whisper-1

# HuggingFace shortcuts:
podx transcribe --model hf:distil-large-v3
podx transcribe --asr-provider hf --model distil-whisper/distil-large-v3
```

### Expert Transcription Flags

Fine-tune transcription quality (local provider only):

```bash
# Voice Activity Detection (removes silence)
podx transcribe --vad-filter

# Use previous text for context (improves accuracy)
podx transcribe --condition-on-previous-text

# Initial prompt for better accuracy
podx transcribe --initial-prompt "This is a technical podcast about AI and machine learning"

# Combine all expert flags
podx transcribe --expert
```

---

## Progress Reporting & Real-Time Updates

### CLI Progress

JSON progress for monitoring:

```bash
# Progress as newline-delimited JSON
podx transcribe --progress-json < audio.json

# Output:
# {"type":"progress","stage":"loading","message":"Loading model..."}
# {"type":"progress","stage":"transcribing","percent":25,"message":"Processing..."}
# {"type":"progress","stage":"transcribing","percent":50,"message":"Processing..."}
# {"success":true,"transcript":{...}}
```

### Python API Progress Callbacks

#### Sync Client with Callback

```python
from podx.api import PodxClient

def on_progress(update: dict):
    print(f"[{update.get('percent', 0)}%] {update['message']}")

client = PodxClient()
result = client.transcribe(
    audio_path="episode.mp3",
    progress_callback=on_progress
)
```

#### Async Client with Real-Time Updates

```python
import asyncio
from podx.api import AsyncPodxClient

async def process_with_progress():
    client = AsyncPodxClient()

    async def on_progress(update: dict):
        # Send via WebSocket, SSE, etc.
        await websocket.send_json(update)

    result = await client.transcribe(
        audio_path="episode.mp3",
        progress_callback=on_progress
    )

asyncio.run(process_with_progress())
```

#### Streaming Progress (Generator Pattern)

```python
async def stream_progress():
    client = AsyncPodxClient()

    async for update in client.transcribe_stream("episode.mp3"):
        if isinstance(update, dict):
            # Progress update
            print(f"Progress: {update['message']}")
        else:
            # Final result (TranscribeResponse)
            print(f"Done: {update.transcript_path}")
```

### Web API Integration

Example FastAPI server with Server-Sent Events:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from podx.api import AsyncPodxClient
import json

app = FastAPI()

@app.post("/transcribe")
async def transcribe(audio_path: str):
    client = AsyncPodxClient()

    async def event_stream():
        async for update in client.transcribe_stream(audio_path):
            if isinstance(update, dict):
                # Progress update
                yield f"data: {json.dumps(update)}\n\n"
            else:
                # Final result
                yield f"data: {json.dumps({'status': 'complete', 'result': update.dict()})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## Batch Processing & Automation

### Process Multiple Episodes

#### Sequential Processing

```bash
# Process a date range
for date in 2024-10-{01..31}; do
  echo "Processing $date..."
  podx run --show "Daily Podcast" --date $date
done
```

#### Parallel Processing

```bash
# Process multiple episodes in parallel (use with caution - heavy on resources)
for date in 2024-10-{01..07}; do
  podx run --show "Daily Podcast" --date $date &
done
wait  # Wait for all background jobs
```

#### From File List

```bash
# episodes.txt contains one date per line
while read date; do
  podx run --show "My Podcast" --date "$date"
done < episodes.txt
```

### Python Batch Processing

```python
from podx.api import PodxClient
from pathlib import Path
import concurrent.futures

def process_episode(audio_path: Path):
    client = PodxClient()
    return client.transcribe(audio_path, model="large-v3-turbo")

# Process multiple files
audio_files = list(Path("audio_files/").glob("*.mp3"))

# Parallel processing (adjust max_workers based on your system)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    results = list(executor.map(process_episode, audio_files))

print(f"Processed {len(results)} episodes")
```

### Scheduled Processing with Cron

```bash
# Edit crontab
crontab -e

# Add daily processing at 3 AM
0 3 * * * cd /path/to/podx && podx run --show "Daily Show" --date $(date +\%Y-\%m-\%d) >> /var/log/podx.log 2>&1
```

---

## Python API Deep Dive

### Core Engines (Low-Level API)

Direct access to business logic for maximum control:

#### Custom Transcription Engine

```python
from podx.core.transcribe import TranscriptionEngine
from pathlib import Path

# Initialize with custom settings
engine = TranscriptionEngine(
    model="large-v3-turbo",
    provider="local",
    device="cuda",  # or "cpu", "mps", None (auto-detect)
    compute_type="int8_float16",  # or "float16", "int8", "float32"
    batch_size=16,
    language="en"
)

# Transcribe
transcript = engine.transcribe(Path("audio.wav"))

# Access raw data
print(f"Language: {transcript['language']}")
print(f"Segments: {len(transcript['segments'])}")
for segment in transcript['segments'][:5]:
    print(f"{segment['start']:.2f}s - {segment['end']:.2f}s: {segment['text']}")
```

#### Custom Diarization

```python
from podx.core.diarize import DiarizationEngine

# Initialize
diarizer = DiarizationEngine(
    language="en",
    min_speakers=2,
    max_speakers=5
)

# Diarize
diarized = diarizer.diarize(
    audio_path=Path("audio.wav"),
    segments=transcript["segments"]
)

# Group by speaker
from collections import defaultdict
speaker_text = defaultdict(list)
for seg in diarized["segments"]:
    speaker_text[seg["speaker"]].append(seg["text"])

for speaker, texts in speaker_text.items():
    print(f"\n{speaker}:")
    print(" ".join(texts[:3]) + "...")
```

#### Custom AI Analysis

```python
from podx.core.deepcast import DeepcastEngine
from podx.llm import get_provider

# Use different LLM provider
llm = get_provider("anthropic", api_key="sk-ant-...")

engine = DeepcastEngine(
    llm_provider=llm,
    model="claude-3-opus",
    temperature=0.2,
    max_chars_per_chunk=24000
)

# Custom prompts
system_prompt = "You are an expert podcast analyst."
map_instructions = "Summarize the key points from this segment."
reduce_instructions = "Create a comprehensive outline from these summaries."

markdown, json_data = engine.deepcast(
    transcript=diarized,
    system_prompt=system_prompt,
    map_instructions=map_instructions,
    reduce_instructions=reduce_instructions,
    want_json=True
)

print(markdown)
if json_data:
    print("Structured data:", json_data)
```

### Progress Reporting Abstraction

Create custom progress reporters for different contexts:

#### Console Progress Reporter

```python
from podx.progress import ConsoleProgressReporter
from podx.core.transcribe import TranscriptionEngine

# Rich-based console output
progress = ConsoleProgressReporter()

engine = TranscriptionEngine(progress=progress)
transcript = engine.transcribe(Path("audio.wav"))
```

#### API Progress Reporter (for Web Apps)

```python
from podx.progress import APIProgressReporter
from podx.core.transcribe import TranscriptionEngine
import asyncio

async def transcribe_with_api_progress():
    # Create event queue
    progress = APIProgressReporter()

    # Start transcription in background
    async def run_transcription():
        engine = TranscriptionEngine(progress=progress)
        return engine.transcribe(Path("audio.wav"))

    task = asyncio.create_task(run_transcription())

    # Poll for events
    last_timestamp = 0.0
    while not task.done():
        events = progress.get_events(since=last_timestamp)
        for event in events:
            print(f"{event.event_type}: {event.message}")
            last_timestamp = event.timestamp
        await asyncio.sleep(0.1)

    result = await task
    return result
```

#### Silent Progress Reporter (for Testing)

```python
from podx.progress import SilentProgressReporter

# Track calls without output
progress = SilentProgressReporter(track_calls=True)

engine = TranscriptionEngine(progress=progress)
transcript = engine.transcribe(Path("audio.wav"))

# Verify progress was reported
print(f"Progress updates: {len(progress.calls)}")
```

---

## Performance Optimization

### Hardware Acceleration

#### Apple Silicon (M1/M2/M3)

```bash
# MPS for diarization (automatic)
podx diarize --device mps < transcript.json

# CPU for transcription (optimized for M-series)
podx transcribe --compute int8_float16
```

#### NVIDIA GPUs

```bash
# CUDA for both transcription and diarization
podx transcribe --device cuda --compute float16
podx diarize --device cuda
```

#### CPU-Only Optimization

```bash
# Use int8 quantization for faster CPU inference
podx transcribe --compute int8

# Or auto-select optimal settings
podx transcribe --compute auto
```

### Model Selection for Speed

| Model | Speed | Accuracy | Use Case |
|-------|-------|----------|----------|
| `tiny` | Fastest | Lowest | Quick drafts, testing |
| `base` | Very fast | Low | Rough transcripts |
| `small` | Fast | Good | Balanced choice |
| `medium` | Medium | Better | Quality focus |
| `large-v3-turbo` | Fast | Excellent | **Recommended** |
| `large-v3` | Slow | Best | Maximum quality |

```bash
# Speed comparison (approximate, 1-hour audio):
podx transcribe --model tiny       # ~2 minutes
podx transcribe --model base       # ~5 minutes
podx transcribe --model large-v3-turbo  # ~15 minutes (recommended)
podx transcribe --model large-v3   # ~30 minutes
```

### Caching & Intermediate Files

```bash
# Keep intermediate files for faster re-processing
podx run --keep-intermediates

# Skip already-completed steps
podx run --resume  # Resume from last successful step
```

---

## Integration Examples

### FastAPI Web Service

```python
from fastapi import FastAPI, UploadFile, BackgroundTasks
from podx.api import AsyncPodxClient
from pathlib import Path
import uuid

app = FastAPI()

@app.post("/api/transcribe")
async def transcribe_upload(file: UploadFile, background_tasks: BackgroundTasks):
    # Save uploaded file
    file_id = str(uuid.uuid4())
    audio_path = Path(f"/tmp/{file_id}.mp3")

    with audio_path.open("wb") as f:
        f.write(await file.read())

    # Process in background
    async def process():
        client = AsyncPodxClient()
        result = await client.transcribe(audio_path, model="large-v3-turbo")
        # Store result in database, send notification, etc.

    background_tasks.add_task(process)

    return {"id": file_id, "status": "processing"}
```

### Flask Application

```python
from flask import Flask, request, jsonify
from podx.api import PodxClient
import threading

app = Flask(__name__)
client = PodxClient()

@app.route("/transcribe", methods=["POST"])
def transcribe():
    audio_path = request.json["audio_path"]

    def process_async():
        result = client.transcribe(audio_path)
        # Handle result

    thread = threading.Thread(target=process_async)
    thread.start()

    return jsonify({"status": "processing"})
```

### Celery Task Queue

```python
from celery import Celery
from podx.api import PodxClient

app = Celery('podcast_tasks', broker='redis://localhost:6379')

@app.task
def transcribe_episode(audio_path: str):
    client = PodxClient()
    result = client.transcribe(audio_path, model="large-v3-turbo")
    return result.dict()

# Usage:
# task = transcribe_episode.delay("/path/to/audio.mp3")
# result = task.get()  # Wait for completion
```

---

## Production Deployment

### Environment Configuration

```bash
# .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=abc123...

# Model cache directory
PODX_MODEL_CACHE=/var/lib/podx/models

# Log level
PODX_LOG_LEVEL=INFO
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install PodX
WORKDIR /app
COPY . .
RUN pip install -e ".[asr,whisperx,llm,notion]"

# Pre-download models
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo')"

# Entrypoint
CMD ["podx", "--help"]
```

### Kubernetes Deployment

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-podcast-processor
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: podx
            image: podx:latest
            command: ["podx", "run"]
            args:
              - "--show"
              - "Daily Podcast"
              - "--date"
              - "$(date +%Y-%m-%d)"
            env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: podx-secrets
                  key: openai-api-key
            resources:
              requests:
                memory: "4Gi"
                cpu: "2"
              limits:
                memory: "8Gi"
                cpu: "4"
          restartPolicy: OnFailure
```

### Monitoring & Logging

```python
import logging
from podx.api import PodxClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/podx/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Use with error handling
client = PodxClient()

try:
    result = client.transcribe("episode.mp3")
    logger.info(f"Transcribed: {result.transcript_path}")
except Exception as e:
    logger.error(f"Transcription failed: {e}", exc_info=True)
    # Send alert, retry, etc.
```

---

## Best Practices

### 1. Error Handling

```python
from podx.api import PodxClient, PodxError

client = PodxClient()

try:
    result = client.transcribe("episode.mp3")
except FileNotFoundError:
    print("Audio file not found")
except PodxError as e:
    print(f"PodX error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### 2. Resource Management

```python
from contextlib import contextmanager

@contextmanager
def podx_client():
    client = PodxClient()
    try:
        yield client
    finally:
        # Cleanup if needed
        pass

with podx_client() as client:
    result = client.transcribe("episode.mp3")
```

### 3. Result Validation

```python
result = client.transcribe("episode.mp3")

# Validate result
assert result.success
assert result.transcript_path.exists()
assert len(result.transcript["segments"]) > 0
```

---

## Next Steps

- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions
- **[FAQ](FAQ.md)** - Frequently asked questions
- **[API Reference](api/python-api.md)** - Complete API documentation
- **[Architecture](ARCHITECTURE_V2.md)** - System design details

---

**Need help? [Open an issue](https://github.com/evanhourigan/podx/issues) or check the [discussions](https://github.com/evanhourigan/podx/discussions).**
