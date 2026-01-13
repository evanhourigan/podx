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

## 🆕 v4.1.0 - Cloud GPU Acceleration

**New Feature: RunPod Cloud Transcription (~20-30x faster!)**

Offload transcription to cloud GPUs for dramatically faster processing:
- 1-hour podcast: ~60-90 minutes → ~2-4 minutes
- Cost: ~$0.05-0.10 per hour of audio
- Automatic fallback to local if cloud fails

```bash
# One-time setup
podx cloud setup

# Transcribe with cloud GPU
podx transcribe --model runpod:large-v3-turbo ./episode/

# Full pipeline with cloud
podx run --model runpod:large-v3-turbo ./episode/
```

**v4.0.0 Changes:**
- Directory-based workflow (no more stdin/stdout JSON piping)
- `deepcast` renamed to `analyze`
- Interactive mode when no arguments provided
- Simplified file naming: `transcript.json`, `analysis.json`

**Migrating from v3.x?** Key changes: directory-based workflow, `deepcast` → `analyze`, simplified CLI options.

---

## 🌟 What is PodX?

PodX is a **podcast processing pipeline** that transforms raw audio into transcripts, speaker labels, and AI-powered analysis.

**Three ways to use PodX:**

1. **Interactive CLI** - Simple commands with interactive prompts (v4.0+)
2. **Direct CLI** - Scriptable commands with arguments
3. **Python API** - Full programmatic access for web apps

```bash
# Interactive CLI: Just run the command
podx run                      # Full pipeline wizard

# Direct CLI: Specify arguments for scripting
podx fetch --show "Lex Fridman Podcast" --date 2024-11-24
podx transcribe ./Lex_Fridman/2024-11-24-ep/
podx analyze ./Lex_Fridman/2024-11-24-ep/
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
# Interactive mode - follow the prompts
podx run

# Or specify show/date directly
podx fetch --show "Lex Fridman Podcast"   # Browse episodes, select one
podx transcribe ./Lex_Fridman/2024-11-24-ep/
podx diarize ./Lex_Fridman/2024-11-24-ep/
podx analyze ./Lex_Fridman/2024-11-24-ep/

# Output structure:
# Lex_Fridman_Podcast/2024-11-24-episode-slug/
#   ├── episode-meta.json                  # Episode metadata
#   ├── audio.mp3                          # Downloaded audio
#   ├── audio.wav                          # Transcoded for ASR
#   ├── transcript.json                    # Transcript (with speaker labels if diarized)
#   └── analysis.json                      # AI analysis
```

### Initial Setup

```bash
# Setup wizard - checks requirements, configures API keys
podx init

# Or manually set environment variables
export OPENAI_API_KEY="sk-..."       # For cloud transcription and GPT analysis
export ANTHROPIC_API_KEY="sk-ant-..." # For Claude analysis models
export HUGGINGFACE_TOKEN="hf_..."     # For improved speaker diarization
```

View available models: `podx models`

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
- **📺 YouTube Integration** - Direct processing of YouTube videos via URL
- **⚡ Multi-Provider Transcription** - Local (faster-whisper), OpenAI, or HuggingFace models
- **🎭 Speaker Diarization** - PyAnnote-powered speaker identification
- **🧠 AI-Powered Analysis** - GPT-4/Claude with 10 format-based templates (interview, panel, debate, etc.)
- **📊 Multiple Export Formats** - SRT, VTT, TXT, Markdown
- **📝 Notion Publishing** - Direct integration with Notion databases
- **🎨 Interactive CLI** - Simple numbered selection for episode browsing

### Developer Features

- **🌐 Web API Server** - Production REST API with real-time progress (v3.0+)
- **🐍 Python API** - Use as a library in your own applications
- **⚡ Async Support** - Real-time progress callbacks for web UIs
- **📤 JSON Output** - All CLI commands support `--json` for automation
- **📁 Directory-Based Workflow** - Commands operate on episode directories (v4.0+)
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
│ Get Episode │    │ (automatic) │    │  ASR Model  │    │  Speakers   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                  │
                   ┌─────────────┐    ┌─────────────┐             │
                   │   NOTION    │◀───│   ANALYZE   │◀────────────┘
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
│  - Interactive mode with Rich console UI                │
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
analysis_result = client.analyze(
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
from podx.core.analyze import AnalyzeEngine

# Transcribe with specific settings
engine = TranscriptionEngine(
    model="large-v3-turbo",   # Model name without provider prefix
    provider="local",         # Provider: "local", "openai", or "hf"
    device=None,              # Auto-detect: MPS/CUDA/CPU
    compute_type=None,        # Auto-select optimal
)
transcript = engine.transcribe(Path("audio.wav"))

# Add speaker labels
diarizer = DiarizationEngine(language="en")
diarized = diarizer.diarize(
    audio_path=Path("audio.wav"),
    segments=transcript["segments"]
)

# AI analysis
analyzer = AnalyzeEngine(
    model="gpt-4o",
    provider="openai"
)
metadata = {"title": "Episode 1", "show_name": "My Podcast"}
markdown, insights = analyzer.analyze(diarized, metadata)
```

**📖 See [docs/api/python-api.md](docs/api/python-api.md) for complete API reference.**

---

## 🔧 CLI Usage

### Command Overview

| Command | Purpose |
|---------|---------|
| `podx fetch` | Download podcast episodes |
| `podx transcribe` | Convert audio to text |
| `podx diarize` | Add speaker labels |
| `podx cleanup` | Clean up transcript, filter ads |
| `podx analyze` | Generate AI analysis |
| `podx export` | Export to various formats |
| `podx run` | Full pipeline wizard |
| `podx notion` | Publish to Notion |
| `podx models` | List models with pricing |
| `podx config` | Manage configuration |
| `podx templates` | Manage analysis templates |
| `podx init` | Setup wizard |

### Interactive Mode (v4.0+)

Run any command without arguments for interactive mode:

```bash
podx fetch           # Search podcasts, browse episodes, download
podx transcribe      # Select episode, transcribe audio
podx diarize         # Select episode, add speaker labels
podx cleanup         # Select episode, clean up transcript
podx analyze         # Select episode, generate AI analysis
podx run             # Full pipeline wizard
```

Navigation in interactive mode:
- Enter number to select
- `n` next page, `p` previous page
- `b` back, `q` quit

### Direct Mode (for scripting)

Specify paths/options for automation:

```bash
# Download specific episode
podx fetch --show "Lex Fridman" --date 2024-11-24

# Process episode directory
podx transcribe ./Show/2024-11-24-ep/
podx diarize ./Show/2024-11-24-ep/
podx analyze ./Show/2024-11-24-ep/

# Export to formats
podx export transcript ./ep/ -f md,srt,vtt
podx export analysis ./ep/ -f md,html
```

### Analysis Templates

Templates customize AI output for different podcast formats:

```bash
# List available templates
podx templates list

# Use specific template
podx analyze ./ep/ --template interview-1on1
```

Available templates:
- `general` - Works for any podcast (default)
- `interview-1on1` - Host interviewing a single guest
- `panel-discussion` - Multiple hosts/guests
- `solo-commentary` - Single host
- `technical-deep-dive` - In-depth technical content
- And more: `lecture-presentation`, `debate-roundtable`, `news-analysis`, `case-study`, `business-strategy`, `research-review`

See [docs/TEMPLATES.md](docs/TEMPLATES.md) for complete guide.

---

## 📖 Usage Examples

### Basic Usage

```bash
# Interactive - just run and follow prompts
podx run

# Direct - specify show and date
podx fetch --show "Lex Fridman" --date 2024-11-24
podx transcribe ./Lex_Fridman/2024-11-24-ep/
podx analyze ./Lex_Fridman/2024-11-24-ep/
```

### Scripting Workflows

```bash
# Process multiple episodes
for date in 2024-11-{20..24}; do
  podx fetch --show "Daily Show" --date $date
  podx transcribe "./Daily_Show/$date-*/"
  podx analyze "./Daily_Show/$date-*/"
done

# Export all transcripts to SRT
for dir in ./*/; do
  podx export transcript "$dir" -f srt
done
```

### RSS Feeds

```bash
# Use direct RSS URL - browse episodes interactively
podx fetch --rss 'https://feeds.example.com/podcast.xml'

# Direct download with date filter
podx fetch --rss 'https://feeds.example.com/podcast.xml' --date 2024-01-15

# Spotify Creators URLs are automatically converted to RSS feeds
podx fetch --rss 'https://creators.spotify.com/pod/profile/showname/episodes/episode-title'
```

### YouTube Videos

```bash
# Download YouTube video
podx fetch --url 'https://www.youtube.com/watch?v=VIDEO_ID'

# Then process the downloaded directory
podx transcribe ./YouTube/2024-11-24-video-title/
podx analyze ./YouTube/2024-11-24-video-title/
```

### Multi-Provider LLM Examples

```bash
# Use OpenAI (default)
export OPENAI_API_KEY="sk-..."
podx analyze ./ep/ --model openai:gpt-4o

# Use Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..."
podx analyze ./ep/ --model anthropic:claude-sonnet-4-5

# Use Ollama (local, FREE)
podx analyze ./ep/ --model ollama:llama2
```

### Batch Processing

```bash
# Process a week of episodes sequentially
for day in {01..07}; do
  podx fetch --show "Daily Podcast" --date "2024-10-$day"
  podx transcribe "./Daily_Podcast/2024-10-$day-*/"
  podx analyze "./Daily_Podcast/2024-10-$day-*/"
done

# Process all episode directories
for dir in ./Show/*/; do
  podx transcribe "$dir"
  podx diarize "$dir"
  podx analyze "$dir"
done

# Export all transcripts to SRT
for dir in ./*/; do
  podx export transcript "$dir" -f srt,vtt
done
```

### Custom Export Workflows

```bash
# Export transcript to multiple formats
podx export transcript ./ep/ -f txt,srt,vtt,md

# Export analysis to markdown and HTML
podx export analysis ./ep/ -f md,html

# Create searchable text archive for all episodes
for dir in ./*/; do
  podx export transcript "$dir" -f txt
done
```

### Model Selection & Optimization

```bash
# Fast transcription with base model
podx transcribe ./ep/ --model local:base  # ~0.3x real-time on GPU

# Balanced: large-v3-turbo (recommended, default)
podx transcribe ./ep/ --model local:large-v3-turbo  # ~0.5x real-time on GPU

# Maximum accuracy with large-v3
podx transcribe ./ep/ --model local:large-v3  # ~1x real-time on GPU

# Use OpenAI Whisper API (fastest, paid)
export OPENAI_API_KEY="sk-..."
podx transcribe ./ep/ --model openai:whisper-1
```

### Diarization Examples

```bash
# Auto-detect speakers (default)
podx diarize ./ep/

# Specify exact number of speakers
podx diarize ./ep/ --speakers 2

# Specify speaker range
podx diarize ./ep/ --min-speakers 2 --max-speakers 4
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

### Automation & Scripting

```bash
# Daily automation script
#!/bin/bash
# process-daily-podcast.sh

SHOW="The Daily"
DATE=$(date +%Y-%m-%d)

# Process today's episode
podx fetch --show "$SHOW" --date "$DATE"
podx transcribe "./The_Daily/$DATE-*/"
podx diarize "./The_Daily/$DATE-*/"
podx analyze "./The_Daily/$DATE-*/"

# Export transcripts to text
podx export transcript "./The_Daily/$DATE-*/" -f txt

# Cron schedule: daily at 6 AM
# 0 6 * * * /path/to/process-daily-podcast.sh
```

### Research & Analysis

```python
# Analyze multiple episodes for research
from podx.api import PodxClient
from pathlib import Path

client = PodxClient()

# Process episode directories
episode_dirs = list(Path("./Podcast").glob("2024-10-*"))

for ep_dir in episode_dirs:
    # Transcribe
    client.transcribe(ep_dir)

    # Diarize
    client.diarize(ep_dir)

    # Analyze
    client.analyze(ep_dir, model="gpt-4o")

print(f"Processed {len(episode_dirs)} episodes")
```

**📖 See [docs/QUICKSTART.md](docs/QUICKSTART.md) for beginner guides and [docs/ADVANCED.md](docs/ADVANCED.md) for advanced usage.**

---

## ⚡ Performance & GPU Acceleration

### Automatic Device Detection

PodX automatically detects and uses the best available hardware:

- **Apple Silicon (M1/M2/M3)**: MPS GPU for diarization, optimized CPU for transcription
- **NVIDIA GPUs**: CUDA for both transcription and diarization
- **CPU fallback**: Optimized compute types (int8/float16) for CPU-only

Hardware is detected automatically - no configuration needed.

### ASR Provider Options

Choose the best transcription provider for your needs:

```bash
# Local (faster-whisper) - Best for privacy, no API costs
podx transcribe ./ep/ --model local:large-v3-turbo

# OpenAI API - Fastest, requires API key
podx transcribe ./ep/ --model openai:whisper-1

# See all available models and pricing
podx models
```

### Performance Tips

```bash
# Use turbo model for 2x speed (default)
podx transcribe ./ep/ --model local:large-v3-turbo

# Process multiple episode directories in parallel
for dir in ./Show/*/; do
  podx transcribe "$dir" &
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
- **[Templates Guide](docs/TEMPLATES.md)** - Analysis templates for different formats
- **[Configuration Guide](docs/CONFIG.md)** - YAML config and environment variables
- **[Examples](docs/EXAMPLES.md)** - Working code examples

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
│   │   ├── analyze.py        # AnalyzeEngine
│   │   ├── fetch.py          # PodcastFetcher
│   │   ├── export.py         # ExportEngine
│   │   └── notion.py         # NotionEngine
│   ├── cli/                  # CLI commands
│   │   ├── transcribe.py     # podx transcribe command
│   │   ├── diarize.py        # podx diarize command
│   │   ├── analyze.py        # podx analyze command
│   │   └── commands/run.py   # podx run command
│   ├── api/                  # Python API
│   │   ├── client.py         # PodxClient, AsyncPodxClient
│   │   └── models.py         # Pydantic response models
│   ├── ui/                   # Interactive CLI components
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
- **[Rich](https://rich.readthedocs.io)** - Terminal formatting
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
