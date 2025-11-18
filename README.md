# 🎙️ PodX

**Production-Grade Podcast Processing Platform**

Transform podcast audio into structured insights with AI-powered transcription, speaker diarization, and intelligent analysis.

[![CI](https://github.com/evanhourigan/podx/actions/workflows/ci.yml/badge.svg)](https://github.com/evanhourigan/podx/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/evanhourigan/podx/branch/main/graph/badge.svg)](https://codecov.io/gh/evanhourigan/podx)
[![PyPI version](https://badge.fury.io/py/podx.svg)](https://badge.fury.io/py/podx)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![security: pip-audit](https://img.shields.io/badge/security-pip--audit-blue)](https://github.com/pypa/pip-audit)

---

## 🆕 v3.0.0 - Unified CLI

**Breaking Change:** All `podx-verb` commands are now `podx verb` subcommands.

```bash
# OLD (v2.x)                 # NEW (v3.0)
podx-run ...              →  podx run ...
podx transcribe ...       →  podx transcribe ...
podx-quick ...            →  podx run --profile quick ...
```

**[See MIGRATION_V3.md for full migration guide →](MIGRATION_V3.md)**

---

## 🌟 What is PodX?

PodX is a **composable podcast processing pipeline** that transforms raw audio into searchable, structured data with speaker attribution and AI-powered analysis. Built on the Unix philosophy of simple, composable tools that do one thing well.

**Four ways to use PodX:**

1. **Web API Server** - Production REST API with real-time progress streaming (NEW in v3.0)
2. **CLI Pipeline** - Composable commands with UNIX pipes
3. **Python API** - Import and use core engines programmatically
4. **High-Level Client** - Simple Python API with progress callbacks for web apps

```bash
# Web API Server: Production-ready REST API
podx server start
# → http://localhost:8000/docs for interactive API documentation

# CLI: From podcast URL to complete analysis
podx run --show "Lex Fridman Podcast" --date 2024-10-15
```

```python
# Python API: Build custom workflows
from podx.api import PodxClient

client = PodxClient()
result = client.transcribe("episode.mp3", model="large-v3")
print(f"Transcript: {result.transcript_path}")
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/evanhourigan/podx.git
cd podx
pip install -e ".[asr,whisperx,llm,notion]"

# Verify installation
podx --help
```

### System Requirements

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Python 3.9+ required
python --version
```

### Your First Episode

```bash
# Process a complete episode
podx run --show "Lex Fridman Podcast" --date 2024-10-15

# Output structure:
# Lex_Fridman_Podcast/2024-10-15/
#   ├── audio.mp3                          # Downloaded audio
#   ├── audio-transcoded.wav               # Normalized for processing
#   ├── transcript-large-v3-turbo.json     # Base transcript
#   ├── transcript-diarized.json           # With speaker labels
#   ├── deepcast-outline.md                # AI analysis
#   └── notion-page-url.txt                # Notion URL
```

### Initial Setup

**Quick Start (Recommended):**
```bash
# Interactive setup wizard - configures everything in one go
podx init

# Follow the prompts to configure:
# - API keys (OpenAI, Anthropic, etc.)
# - Default settings (models, output formats)
# - Optional features (shell completion, profiles)
```

**Manual Configuration:**
```bash
# Configure API keys interactively
podx models --configure

# Or set environment variables
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Check configuration status
podx models --status
```

**Supported Providers:**
- **OpenAI** - GPT-4, GPT-3.5 models
- **Anthropic** - Claude Opus, Sonnet, Haiku
- **OpenRouter** - Access multiple models through one API
- **Ollama** - Local models (no API key required)

---

## 🌐 Web API Server (v3.0+)

PodX now includes a production-grade REST API server for integrating podcast processing into web applications.

### Quick Start

```bash
# Install with server dependencies
pip install -e ".[server]"

# Start the server
podx server start

# Server is now running at http://localhost:8000
# Interactive API docs: http://localhost:8000/docs
```

### Features

- **REST API** - FastAPI-powered HTTP endpoints for all operations
- **Real-Time Progress** - Server-Sent Events (SSE) for live progress updates
- **Job Management** - Persistent job queue with SQLite storage
- **File Upload** - Support for large audio file uploads
- **Authentication** - Optional API key protection
- **Rate Limiting** - Built-in rate limiting and CORS support
- **Health Checks** - Kubernetes-ready liveness and readiness probes
- **Metrics** - Optional Prometheus metrics endpoint
- **Auto-Documentation** - Interactive Swagger UI and ReDoc

### API Example (Python)

```python
import requests

# Upload file
files = {"file": open("podcast.mp3", "rb")}
response = requests.post("http://localhost:8000/upload", files=files)
upload_id = response.json()["upload_id"]

# Create job
response = requests.post(
    "http://localhost:8000/jobs",
    json={"upload_id": upload_id, "profile": "quick"}
)
job_id = response.json()["job_id"]

# Stream progress (SSE)
with requests.get(f"http://localhost:8000/jobs/{job_id}/stream", stream=True) as r:
    for line in r.iter_lines():
        if line.startswith(b"data: "):
            print(line.decode()[6:])  # Real-time progress updates
```

See [examples/](examples/) for complete client examples in Python, JavaScript, and curl.

### Deployment Options

**Docker:**
```bash
docker-compose up -d
```

**Kubernetes:**
```bash
kubectl apply -f k8s/
```

**VPS/Systemd:**
```bash
# Copy service file
sudo cp examples/podx-server.service /etc/systemd/system/

# Start service
sudo systemctl enable --now podx-server
```

For detailed deployment guides, see:
- [DOCKER.md](DOCKER.md) - Docker and docker-compose
- [KUBERNETES.md](KUBERNETES.md) - Kubernetes manifests and helm
- [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md) - VPS deployment with Nginx

---

## ✨ Features

### Core Capabilities

- **🎯 Smart Episode Discovery** - Search by show name, date, or RSS feed
- **⚡ Multi-Provider Transcription** - Local (faster-whisper), OpenAI, or HuggingFace models
- **🎭 Speaker Diarization** - PyAnnote-powered speaker identification
- **🧠 AI-Powered Analysis** - GPT-4/Claude integration for summaries and insights
- **📊 Multiple Export Formats** - SRT, VTT, TXT, Markdown
- **📝 Notion Publishing** - Direct integration with Notion databases
- **🎨 Interactive UI** - TUI browser for episode selection

### Developer Features

- **🌐 Web API Server** - Production REST API with real-time progress (v3.0+)
- **🐍 Python API** - Use as a library in your own applications
- **⚡ Async Support** - Real-time progress callbacks for web UIs
- **📤 JSON Output** - All CLI commands support `--json` for automation
- **🔄 UNIX Composability** - Pipe commands together
- **📋 Manifest Tracking** - Track processing state across pipeline

### Production Ready

- **✅ Automated CI/CD** - GitHub Actions with multi-platform testing
- **🔒 Security Scanning** - pip-audit and safety checks
- **📊 Code Coverage** - Comprehensive test suite
- **🏷️ Standardized Exit Codes** - Consistent error handling
- **📝 Type Safety** - Full type annotations with mypy

---

## 🏗️ Architecture

PodX follows a **composable pipeline** where each step can be used independently or chained together:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   FETCH     │───▶│  TRANSCODE  │───▶│ TRANSCRIBE  │───▶│   DIARIZE   │
│ Get Episode │    │ Normalize   │    │  ASR Model  │    │  Speakers   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                  │
                   ┌─────────────┐    ┌─────────────┐           │
                   │   NOTION    │◀───│  DEEPCAST   │◀──────────┘
                   │   Publish   │    │ AI Analysis │
                   └─────────────┘    └─────────────┘
                                              │
                                      ┌───────▼────────┐
                                      │     EXPORT     │
                                      │ SRT/VTT/TXT/MD │
                                      └────────────────┘
```

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────┐
│  CLI Layer (podx.cli.*)                                 │
│  - Click commands with --json output                    │
│  - Interactive mode with Rich/Textual                   │
│  - Progress display and user interaction                │
└─────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│  API Layer (podx.api.*)                                 │
│  - PodxClient: Synchronous high-level API               │
│  - AsyncPodxClient: Async with progress callbacks       │
│  - Pydantic response models for type safety             │
└─────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────┐
│  Core Layer (podx.core.*)                               │
│  - Pure business logic engines                          │
│  - TranscriptionEngine, DiarizationEngine, etc.         │
│  - No CLI dependencies, fully reusable                  │
└─────────────────────────────────────────────────────────┘
```

---

## 🐍 Python API

**NEW in v2.0:** Three levels of Python API for different use cases!

### 1. High-Level Client API (Recommended)

Simple, type-safe API with automatic error handling:

```python
from podx.api import PodxClient

client = PodxClient()

# Fetch an episode
fetch_result = client.fetch_episode(
    show_name="Lex Fridman Podcast",
    date="2024-10-15"
)

# Transcribe audio
transcribe_result = client.transcribe(
    audio_url=fetch_result.audio_path,
    asr_model="large-v3-turbo"
)

# Add speaker labels
diarize_result = client.diarize(
    transcript_path=transcribe_result.transcript_path
)

# AI analysis
analysis_result = client.deepcast(
    transcript_path=diarize_result.transcript_path,
    llm_model="gpt-4o"
)

# Export to formats
export_result = client.export(
    transcript_path=diarize_result.transcript_path,
    formats=["txt", "srt", "vtt", "md"]
)

# Publish to Notion
notion_result = client.publish_to_notion(
    markdown_path=analysis_result.markdown_path,
    notion_token="secret_xxx",
    database_id="abc123"
)
```

### 2. Async Client with Progress (For Web Apps)

Real-time progress updates for UIs:

```python
import asyncio
from podx.api import AsyncPodxClient

async def process_with_progress():
    client = AsyncPodxClient()

    # Progress callback
    async def on_progress(update: dict):
        print(f"[{update.get('percent', 0)}%] {update['message']}")
        # Or send via WebSocket:
        # await websocket.send_json(update)

    # Transcribe with progress
    result = await client.transcribe(
        audio_path="episode.mp3",
        model="large-v3-turbo",
        progress_callback=on_progress
    )

    print(f"Done: {result.transcript_path}")

# Or use async generator for streaming:
async def stream_progress():
    client = AsyncPodxClient()

    async for update in client.transcribe_stream("episode.mp3"):
        if isinstance(update, dict):
            # Progress update
            print(f"Progress: {update['message']}")
        else:
            # Final result (TranscribeResponse)
            print(f"Complete: {update.transcript_path}")

asyncio.run(process_with_progress())
```

### 3. Core Engines (Low-Level)

Direct access to business logic for maximum control:

```python
from pathlib import Path
from podx.core.transcribe import TranscriptionEngine
from podx.core.diarize import DiarizationEngine
from podx.core.deepcast import DeepcastEngine

# Transcribe with specific settings
engine = TranscriptionEngine(
    model="large-v3-turbo",
    provider="local",  # or "openai", "hf"
    device=None,  # Auto-detect: MPS/CUDA/CPU
    compute_type=None,  # Auto-select optimal
)
transcript = engine.transcribe(Path("audio.wav"))

# Add speaker labels
diarizer = DiarizationEngine(language="en")
diarized = diarizer.diarize(
    audio_path=Path("audio.wav"),
    segments=transcript["segments"]
)

# AI analysis
analyzer = DeepcastEngine(
    model="gpt-4o",
    provider="openai"
)
metadata = {"title": "Episode 1", "show_name": "My Podcast"}
markdown, insights = analyzer.deepcast(diarized, metadata)
```

**📖 See [docs/api/python-api.md](docs/api/python-api.md) for complete API reference.**

---

## 🔧 CLI Usage

### Pipeline Commands

All commands support JSON I/O for composability:

| Command | Purpose | JSON Input | JSON Output |
|---------|---------|------------|-------------|
| `podx fetch` | Download episodes | - | `AudioMeta` |
| `podx transcode` | Normalize audio | `AudioMeta` | `AudioMeta` |
| `podx transcribe` | Speech-to-text | `AudioMeta` | `Transcript` |
| `podx diarize` | Add speakers | `Transcript` | `DiarizedTranscript` |
| `podx deepcast` | AI analysis | `Transcript` | `Deepcast` |
| `podx export` | Format conversion | `Transcript` | `ExportPaths` |
| `podx notion` | Publish to Notion | `Deepcast + Meta` | `NotionURL` |
| `podx run` | Full pipeline | - | All outputs |

### JSON Output Mode

All commands support `--json` for machine-readable output:

```bash
# Structured JSON output
podx transcribe --json < audio.json
{
  "success": true,
  "transcript": {...},
  "files": {
    "transcript": "transcript-large-v3-turbo.json"
  },
  "stats": {
    "model": "large-v3-turbo",
    "segments": 847,
    "duration": 3612
  }
}
```

### Progress Streaming

Long-running commands support `--progress-json`:

```bash
# Newline-delimited JSON progress
podx transcribe --progress-json < audio.json
{"type": "progress", "stage": "loading", "message": "Loading model..."}
{"type": "progress", "stage": "transcribing", "message": "Processing...", "percent": 25}
{"type": "progress", "stage": "transcribing", "message": "Processing...", "percent": 50}
{"type": "progress", "stage": "transcribing", "message": "Processing...", "percent": 75}
{"success": true, "transcript": {...}}
```

### Composable Pipelines

Use UNIX pipes for custom workflows:

```bash
# Full pipeline
podx fetch --show "My Podcast" --date 2024-10-15 \
  | podx transcode \
  | podx transcribe --model large-v3-turbo \
  | podx diarize \
  | podx deepcast --type outline \
  | podx notion

# Save intermediate results
podx fetch --show "My Podcast" --date 2024-10-15 \
  | tee fetch.json \
  | podx transcribe --model large-v3-turbo \
  | tee transcript.json \
  | podx export --formats srt,txt
```

### Search & Analysis

**NEW in v2.1:** Search transcripts and extract insights!

```bash
# Index a transcript for searching
podx search index transcript.json --episode-id ep001 --title "AI Safety"

# Keyword search
podx search query "artificial intelligence"

# Semantic search (requires: pip install podx[search])
podx search query "dangers of AI" --semantic

# Extract notable quotes
podx analyze quotes transcript.json

# Find highlight moments
podx analyze highlights transcript.json

# Topic clustering (semantic search required)
podx analyze topics ep001 --clusters 10

# Speaker statistics
podx analyze speakers transcript.json
```

### Interactive Mode

Browse and select episodes visually:

```bash
# Interactive episode browser
podx fetch --show "Huberman Lab" --interactive

# Interactive transcription with model selection
podx transcribe --interactive --scan-dir ./episodes
```

### Common Workflows

```bash
# Quick transcription (no AI)
podx run --show "My Show" --date 2024-10-15 --no-deepcast --no-notion

# Specific model
podx run --show "Lex Fridman" --date 2024-10-15 --model large-v3

# Skip diarization (faster)
podx fetch --show "Reply All" --date 2024-10-15 \
  | podx transcribe \
  | podx export --formats txt,srt

# Export existing transcript
podx export --input transcript.json --formats srt,vtt,md
```

---

## 📖 Usage Examples

### Basic Usage

```bash
# Fetch and transcribe a podcast episode
podx fetch --show 'This American Life' --date 2024-01-15 | podx transcribe

# Complete pipeline with smart directory
podx run --show 'Radio Lab' --date 2024-01-15
```

### Advanced Pipeline

```bash
# Full pipeline with AI analysis
podx run --show 'The Podcast' --date 2024-01-15 --diarize --deepcast

# Upload to Notion
podx run --show 'The Podcast' --date 2024-01-15 --deepcast --notion
```

### Unix-style Piping

```bash
# Chain commands manually
podx fetch --show 'Radiolab' --date 2024-01-15 \
| podx transcode --to wav16 \
| podx transcribe \
| podx export --formats txt,srt
```

### RSS Feeds

```bash
# Use direct RSS URL
podx fetch --rss-url 'https://feeds.example.com/podcast.xml' --date 2024-01-15

# Private podcast with full pipeline
podx run --rss-url 'https://private-feed.com/feed.xml' --date 2024-01-15 --deepcast
```

### Multi-Provider LLM Examples

```bash
# Use OpenAI (default)
export OPENAI_API_KEY="sk-..."
podx run --show "My Podcast" --date 2024-10-15 --llm-provider openai --llm-model gpt-4o

# Use Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..."
podx run --show "My Podcast" --date 2024-10-15 --llm-provider anthropic --llm-model claude-3-5-sonnet-20241022

# Use OpenRouter (access to many models)
export OPENROUTER_API_KEY="sk-or-..."
podx run --show "My Podcast" --date 2024-10-15 --llm-provider openrouter --llm-model anthropic/claude-3.5-sonnet

# Use Ollama (local, FREE)
podx run --show "My Podcast" --date 2024-10-15 --llm-provider ollama --llm-model llama2
```

### Batch Processing

```bash
# Process a week of episodes sequentially
for day in {01..07}; do
  podx run --show "Daily Podcast" --date "2024-10-$day"
done

# Process multiple episodes in parallel
cat episode_dates.txt | parallel -j 4 podx run --show "My Podcast" --date {}

# Batch process all MP3 files in a directory
for file in *.mp3; do
  podx transcribe --input "$file"
  podx export --input "${file%.mp3}-transcript.json" --formats txt,srt
done

# Process multiple shows from a list
while IFS=',' read -r show date; do
  podx run --show "$show" --date "$date" &
done < shows.csv
wait
```

### Custom Export Workflows

```bash
# Export to all formats
podx export --input transcript.json --formats txt,srt,vtt,md,json

# Export with custom output directory
podx export --input transcript.json --formats txt,srt --output-dir exports/

# Generate subtitles only
podx run --show "Video Podcast" --date 2024-10-15 --no-deepcast --no-notion
podx export --input transcript.json --formats srt,vtt

# Create searchable text archive
for transcript in **/*-diarized.json; do
  podx export --input "$transcript" --formats txt --output-dir archive/
done
```

### Model Selection & Optimization

```bash
# Fast transcription with base model
podx transcribe --model base --input audio.mp3  # ~0.3x real-time on GPU

# Balanced: large-v3-turbo (recommended)
podx transcribe --model large-v3-turbo --input audio.mp3  # ~0.5x real-time on GPU

# Maximum accuracy with large-v3
podx transcribe --model large-v3 --input audio.mp3  # ~1x real-time on GPU

# Force CPU mode (no GPU required)
podx transcribe --device cpu --compute-type int8 --input audio.mp3

# Use OpenAI Whisper API (fastest, paid)
export OPENAI_API_KEY="sk-..."
podx transcribe --asr-provider openai --input audio.mp3
```

### Diarization Examples

```bash
# Auto-detect speakers
podx diarize --input transcript.json

# Specify exact number of speakers
podx diarize --num-speakers 2 --input transcript.json

# Specify speaker range
podx diarize --min-speakers 2 --max-speakers 4 --input transcript.json

# Use WhisperX for better diarization
podx diarize --engine whisperx --input transcript.json

# Skip diarization (faster processing)
podx run --show "Solo Podcast" --date 2024-10-15 --no-diarize
```

### Web Integration Examples

```python
# FastAPI endpoint with SSE progress
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from podx.api import AsyncPodxClient
from podx.progress import APIProgressReporter
import json

app = FastAPI()

@app.post("/transcribe")
async def transcribe_endpoint(audio_url: str):
    reporter = APIProgressReporter()
    client = AsyncPodxClient()

    async def event_stream():
        # Start transcription in background
        task = asyncio.create_task(
            client.transcribe(audio_url, progress_reporter=reporter)
        )

        # Stream progress events
        while not task.done():
            events = reporter.get_events(since=last_timestamp)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.5)

        # Send final result
        result = await task
        yield f"data: {json.dumps({'done': True, 'result': result.dict()})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# Flask endpoint with polling
from flask import Flask, jsonify
from podx.api import PodxClient
from podx.progress import APIProgressReporter
import threading

app = Flask(__name__)
tasks = {}

@app.post("/transcribe")
def transcribe_flask():
    task_id = str(uuid.uuid4())
    reporter = APIProgressReporter()
    client = PodxClient()

    def process():
        tasks[task_id]["result"] = client.transcribe(
            audio_url,
            progress_reporter=reporter
        )

    tasks[task_id] = {"reporter": reporter, "result": None}
    threading.Thread(target=process).start()

    return jsonify({"task_id": task_id})

@app.get("/progress/<task_id>")
def get_progress(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    events = task["reporter"].get_events()
    return jsonify({
        "events": events,
        "done": task["result"] is not None,
        "result": task["result"].dict() if task["result"] else None
    })
```

### Preprocess & Restore

```bash
# Preprocess transcript (merge + normalize)
podx preprocess --merge --normalize -i transcript.json -o transcript-preprocessed.json

# Run with orchestrator (with semantic restore)
podx run --rss-url '...' --date 2024-01-15 --preprocess --restore --deepcast
```

### Automation & Scripting

```bash
# Daily automation script
#!/bin/bash
# process-daily-podcast.sh

SHOW="The Daily"
DATE=$(date +%Y-%m-%d)

# Process today's episode
podx run --show "$SHOW" --date "$DATE" \
  --llm-provider ollama --llm-model llama2 \
  --notion

# Archive transcripts
find . -name "transcript-diarized.json" -mtime 0 \
  -exec podx export --input {} --formats txt \;

# Notify on completion
echo "Processed $SHOW episode for $DATE" | mail -s "PodX Complete" admin@example.com

# Cron schedule: daily at 6 AM
# 0 6 * * * /path/to/process-daily-podcast.sh
```

### Research & Analysis

```python
# Analyze multiple episodes for research
from podx.api import PodxClient
import pandas as pd

client = PodxClient()

# Process a series of episodes
episodes = [
    {"show": "Podcast", "date": f"2024-10-{day:02d}"}
    for day in range(1, 31)
]

results = []
for ep in episodes:
    # Transcribe
    transcript = client.transcribe_episode(**ep)

    # Analyze
    analysis = client.deepcast(
        transcript.transcript_path,
        llm_provider="anthropic",
        llm_model="claude-3-5-sonnet-20241022"
    )

    # Extract insights
    results.append({
        "date": ep["date"],
        "duration": transcript.stats["duration"],
        "word_count": len(transcript.text.split()),
        "summary": analysis.summary
    })

# Create DataFrame for analysis
df = pd.DataFrame(results)
df.to_csv("podcast_analysis.csv")
print(df.describe())
```

**📖 See [docs/QUICKSTART.md](docs/QUICKSTART.md) for beginner guides and [docs/ADVANCED.md](docs/ADVANCED.md) for advanced usage.**

---

## ⚡ Performance & GPU Acceleration

### Automatic Device Detection

PodX automatically detects and uses the best available hardware:

- **Apple Silicon (M1/M2/M3)**: MPS GPU for diarization, optimized CPU for transcription
- **NVIDIA GPUs**: CUDA for both transcription and diarization
- **CPU fallback**: Optimized compute types (int8/float16) for CPU-only

```bash
# Auto-detect best device (default)
podx transcribe --compute auto

# Or specify manually
podx transcribe --compute int8_float16
```

### ASR Provider Options

Choose the best transcription provider for your needs:

```bash
# Local (faster-whisper) - Best for privacy, no API costs
podx transcribe --model large-v3-turbo --asr-provider local

# OpenAI API - Fastest, requires API key
podx transcribe --model whisper-1 --asr-provider openai

# HuggingFace - Alternative cloud option
podx transcribe --model large-v3 --asr-provider hf
```

### Performance Tips

```bash
# Use turbo model for 2x speed
podx run --model large-v3-turbo

# Skip optional steps
podx run --no-deepcast --no-notion  # Just transcription

# Parallel processing of multiple episodes
for date in 2024-10-{01..31}; do
  podx run --show "Daily Show" --date $date &
done
wait
```

---

## 📚 Documentation

### Getting Started

- **[Quick Start Guide](docs/QUICKSTART.md)** - Beginner-friendly installation and first steps
- **[Advanced Usage](docs/ADVANCED.md)** - Multi-provider LLMs, batch processing, Python API
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[FAQ](docs/FAQ.md)** - Frequently asked questions

### User Guides

- **[Python API Reference](docs/api/python-api.md)** - Complete API documentation
- **[CLI Reference](docs/CLI.md)** - Command-line usage guide
- **[Configuration Guide](docs/CONFIGURATION.md)** - YAML config and environment variables
- **[Examples](examples/api/)** - Working code examples

### Developer Docs

- **[Architecture](docs/ARCHITECTURE_V2.md)** - System design and patterns
- **[Testing Guide](docs/TESTING.md)** - Running and writing tests
- **[Contributing](CONTRIBUTING.md)** - How to contribute

### Migration & Changelog

- **[v2.0 Migration Guide](docs/MIGRATION_V2.md)** - Upgrading from v1.x
- **[Changelog](CHANGELOG.md)** - Release history

---

## 🧪 Development

### Setup

```bash
# Clone repository
git clone https://github.com/evanhourigan/podx.git
cd podx

# Install with all dependencies
pip install -e ".[dev,asr,whisperx,llm,notion]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=podx --cov-report=html

# Run specific test file
pytest tests/unit/test_transcribe.py

# Run linters
ruff check .
black --check .
mypy podx
```

### Project Structure

```
podx/
├── podx/
│   ├── core/                 # Business logic engines
│   │   ├── transcribe.py     # TranscriptionEngine
│   │   ├── diarize.py        # DiarizationEngine
│   │   ├── deepcast.py       # DeepcastEngine
│   │   ├── fetch.py          # PodcastFetcher
│   │   ├── export.py         # ExportEngine
│   │   └── notion.py         # NotionEngine
│   ├── cli/                  # CLI commands
│   │   ├── transcribe.py     # podx transcribe command
│   │   ├── diarize.py        # podx diarize command
│   │   ├── deepcast.py       # podx deepcast command
│   │   └── orchestrate.py    # podx run command
│   ├── api/                  # Python API
│   │   ├── client.py         # PodxClient, AsyncPodxClient
│   │   └── models.py         # Pydantic response models
│   ├── ui/                   # TUI components
│   ├── domain/               # Domain models
│   │   └── exit_codes.py     # Standardized exit codes
│   ├── config.py             # Configuration
│   ├── schemas.py            # Pydantic schemas
│   └── ...
├── tests/                    # Test suite
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
├── examples/                 # Example code
│   └── api/                  # API usage examples
├── docs/                     # Documentation
└── .github/workflows/        # CI/CD pipelines
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Run linters: `ruff check . && black . && mypy podx`
6. Commit: `git commit -m 'Add amazing feature'`
7. Push: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Code Standards

- **Type Annotations**: Required for all functions
- **Tests**: Required for new features
- **Documentation**: Update docs for user-facing changes
- **Linting**: Code must pass ruff, black, and mypy
- **Commits**: Use conventional commits format

---

## 🔒 Security

- **Security Scanning**: Automated pip-audit and safety checks in CI
- **Dependency Updates**: Dependabot for automated updates
- **Secrets**: Never commit API keys or tokens
- **Reporting**: Report security issues to [security contact]

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

### Core Technologies

- **[faster-whisper](https://github.com/guillaumekln/faster-whisper)** - Fast ASR inference engine
- **[WhisperX](https://github.com/m-bain/whisperX)** - Alignment and diarization
- **[PyAnnote](https://github.com/pyannote/pyannote-audio)** - Speaker diarization
- **[OpenAI API](https://openai.com)** - GPT-4 for analysis
- **[Anthropic API](https://anthropic.com)** - Claude for analysis

### Frameworks & Libraries

- **[Click](https://click.palletsprojects.com)** - CLI framework
- **[Pydantic](https://pydantic.dev)** - Data validation
- **[Rich](https://rich.readthedocs.io)** - Terminal UI
- **[Textual](https://textual.textualize.io)** - TUI framework
- **[pytest](https://pytest.org)** - Testing framework

---

## 📞 Support

- **Documentation**: Browse [docs/](docs/) directory
- **Issues**: [GitHub Issues](https://github.com/evanhourigan/podx/issues)
- **Discussions**: [GitHub Discussions](https://github.com/evanhourigan/podx/discussions)

---

<div align="center">

**Built with ❤️ for podcast enthusiasts and developers**

⭐ Star this repo if you find it useful!

[Getting Started](#-quick-start) • [Python API](#-python-api) • [CLI Guide](#-cli-usage) • [Documentation](docs/)

</div>
