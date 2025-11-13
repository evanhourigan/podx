# 🎙️ PodX

**Production-Grade Podcast Processing Platform**

Transform podcast audio into structured insights with AI-powered transcription, speaker diarization, and intelligent analysis.

[![CI](https://github.com/evanhourigan/podx/actions/workflows/ci.yml/badge.svg)](https://github.com/evanhourigan/podx/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/podx.svg)](https://badge.fury.io/py/podx)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![security: pip-audit](https://img.shields.io/badge/security-pip--audit-blue)](https://github.com/pypa/pip-audit)

---

## 🌟 What is PodX?

PodX is a **composable podcast processing pipeline** that transforms raw audio into searchable, structured data with speaker attribution and AI-powered analysis. Built on the Unix philosophy of simple, composable tools that do one thing well.

**Three ways to use PodX:**

1. **CLI Pipeline** - Composable commands with UNIX pipes
2. **Python API** - Import and use core engines programmatically
3. **High-Level Client** - Simple Python API with progress callbacks for web apps

```bash
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

---

## ✨ Features

### Core Capabilities

- **🎯 Smart Episode Discovery** - Search by show name, date, or RSS feed
- **⚡ Multi-Provider Transcription** - Local (faster-whisper), OpenAI, or HuggingFace
- **🎭 Speaker Diarization** - PyAnnote-powered speaker identification
- **🧠 AI-Powered Analysis** - GPT-4/Claude integration for summaries and insights
- **📊 Multiple Export Formats** - SRT, VTT, TXT, Markdown
- **📝 Notion Publishing** - Direct integration with Notion databases

### Developer Features

- **🐍 Python API** - Use as a library in your own applications
- **⚡ Async Support** - Real-time progress callbacks for web UIs
- **📤 JSON Output** - All CLI commands support `--json` for automation
- **🔄 UNIX Composability** - Pipe commands together
- **📋 Manifest Tracking** - Track processing state across pipeline
- **🎨 Interactive UI** - TUI browser for episode selection

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
| `podx-fetch` | Download episodes | - | `AudioMeta` |
| `podx-transcode` | Normalize audio | `AudioMeta` | `AudioMeta` |
| `podx-transcribe` | Speech-to-text | `AudioMeta` | `Transcript` |
| `podx-diarize` | Add speakers | `Transcript` | `DiarizedTranscript` |
| `podx-deepcast` | AI analysis | `Transcript` | `Deepcast` |
| `podx-export` | Format conversion | `Transcript` | `ExportPaths` |
| `podx-notion` | Publish to Notion | `Deepcast + Meta` | `NotionURL` |
| `podx run` | Full pipeline | - | All outputs |

### JSON Output Mode

All commands support `--json` for machine-readable output:

```bash
# Structured JSON output
podx-transcribe --json < audio.json
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
podx-transcribe --progress-json < audio.json
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
podx-fetch --show "My Podcast" --date 2024-10-15 \
  | podx-transcode \
  | podx-transcribe --model large-v3-turbo \
  | podx-diarize \
  | podx-deepcast --type outline \
  | podx-notion

# Save intermediate results
podx-fetch --show "My Podcast" --date 2024-10-15 \
  | tee fetch.json \
  | podx-transcribe --model large-v3-turbo \
  | tee transcript.json \
  | podx-export --formats srt,txt
```

### Interactive Mode

Browse and select episodes visually:

```bash
# Interactive episode browser
podx-fetch --show "Huberman Lab" --interactive

# Interactive transcription with model selection
podx-transcribe --interactive --scan-dir ./episodes
```

### Common Workflows

```bash
# Quick transcription (no AI)
podx run --show "My Show" --date 2024-10-15 --no-deepcast --no-notion

# Specific model
podx run --show "Lex Fridman" --date 2024-10-15 --model large-v3

# Skip diarization (faster)
podx-fetch --show "Reply All" --date 2024-10-15 \
  | podx-transcribe \
  | podx-export --formats txt,srt

# Export existing transcript
podx-export --input transcript.json --formats srt,vtt,md
```

---

## ⚡ Performance & GPU Acceleration

### Automatic Device Detection

PodX automatically detects and uses the best available hardware:

- **Apple Silicon (M1/M2/M3)**: MPS GPU for diarization, optimized CPU for transcription
- **NVIDIA GPUs**: CUDA for both transcription and diarization
- **CPU fallback**: Optimized compute types (int8/float16) for CPU-only

```bash
# Auto-detect best device (default)
podx-transcribe --compute auto

# Or specify manually
podx-transcribe --compute int8_float16
```

### ASR Provider Options

Choose the best transcription provider for your needs:

```bash
# Local (faster-whisper) - Best for privacy, no API costs
podx-transcribe --model large-v3-turbo --asr-provider local

# OpenAI API - Fastest, requires API key
podx-transcribe --model whisper-1 --asr-provider openai

# HuggingFace - Alternative cloud option
podx-transcribe --model large-v3 --asr-provider hf
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
│   │   ├── transcribe.py     # podx-transcribe command
│   │   ├── diarize.py        # podx-diarize command
│   │   ├── deepcast.py       # podx-deepcast command
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
