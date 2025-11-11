# 🎙️ PodX

**Production-Grade Podcast Processing Platform**

Transform podcast audio into structured insights with AI-powered transcription, speaker diarization, and intelligent analysis.

[![CI](https://github.com/evanhourigan/podx/actions/workflows/ci.yml/badge.svg)](https://github.com/evanhourigan/podx/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/evanhourigan/podx/branch/main/graph/badge.svg)](https://codecov.io/gh/evanhourigan/podx)
[![PyPI version](https://badge.fury.io/py/podx.svg)](https://badge.fury.io/py/podx)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![security: pip-audit](https://img.shields.io/badge/security-pip--audit-blue)](https://github.com/pypa/pip-audit)

---

## 🌟 What is PodX?

PodX is a **composable podcast processing pipeline** that transforms raw audio into searchable, structured data with speaker attribution and AI-powered analysis. Built on the Unix philosophy of simple, composable tools that do one thing well.

```bash
# From podcast URL to complete analysis in one command
podx run --show "Lex Fridman Podcast" --date 2024-10-15

# Result: Word-level transcript with speaker labels, AI analysis, and Notion publishing
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

### Your First Episode

```bash
# Process a podcast episode (transcription + diarization)
podx run --show "Lex Fridman Podcast" --date 2024-10-15

# Output directory structure:
# Lex_Fridman_Podcast/2024-10-15/
#   ├── audio.mp3                      (downloaded audio)
#   ├── audio-transcoded.wav           (normalized audio)
#   ├── transcript-large-v3.json       (base transcript)
#   ├── transcript-diarized-large-v3.json (with speakers)
#   ├── deepcast.md                    (AI analysis)
#   └── notion.out.json                (Notion page URL)
```

---

## ✨ Features

### Core Capabilities

- **🎯 Smart Episode Discovery** - Search by show name, date, or RSS feed with interactive browsing
- **⚡ GPU-Accelerated Transcription** - Automatic device detection (MPS/CUDA/CPU) for optimal performance
- **🎭 Speaker Diarization** - WhisperX-powered speaker identification with word-level timing
- **🧠 AI-Powered Analysis** - GPT-4/Claude integration for intelligent episode summaries
- **📊 Multi-Platform Publishing** - Notion, Discord, Slack integration
- **🔌 Python API** - Use core engines programmatically without CLI

### Production Features

- **📝 YAML Configuration** - Podcast-specific settings with intelligent defaults
- **🔄 Pipeline State Management** - Resume from any step, automatic crash recovery
- **🎨 Rich Output Formats** - SRT, VTT, TXT, Markdown, JSON
- **🌊 Unix Philosophy** - Composable CLI tools with JSON stdin/stdout
- **🎓 TUI Studio** - Interactive terminal UI for browsing and processing episodes

---

## 🎉 What's New in v2.0

### The "iPhone Moment" - Simplified User Experience

**v2.0 represents a fundamental rethinking of PodX's architecture and user experience:**

#### Core/CLI Separation
- **Pure business logic** extracted into `podx.core.*` modules
- **Thin CLI wrappers** in `podx.cli.*` for terminal interaction
- **Reusable Python API** - use core engines in your own applications
- **Clear separation** between what to do (core) and how to present it (CLI)

#### Intelligent Defaults
- **Integrated alignment** - Word-level timing now built into `podx-diarize`
- **Removed complexity** - No more fidelity levels or confusing presets
- **Smart device detection** - Automatic GPU acceleration on Apple Silicon/NVIDIA
- **Manifest system** - Track episode state across the entire pipeline

#### Developer Experience
- **9 core modules** with pure business logic (3,000+ lines)
- **285+ tests** with comprehensive mocking
- **Complete API documentation** - See [docs/CORE_API.md](docs/CORE_API.md)
- **Architecture guide** - See [docs/ARCHITECTURE_V2.md](docs/ARCHITECTURE_V2.md)

---

## 🏗️ Pipeline Architecture

PodX follows a **composable pipeline** where each step outputs JSON for the next:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   FETCH     │───▶│  TRANSCODE  │───▶│ TRANSCRIBE  │───▶│   DIARIZE   │
│ Get Episode │    │ Normalize   │    │  Whisper    │    │  Speakers   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                  │
                   ┌─────────────┐    ┌─────────────┐           │
                   │   NOTION    │◀───│  DEEPCAST   │◀──────────┘
                   │   Publish   │    │ AI Analysis │
                   └─────────────┘    └─────────────┘
```

### Pipeline Commands

| Command | Purpose | Input | Output |
|---------|---------|-------|--------|
| `podx-fetch` | Download episodes | Show/date/RSS | AudioMeta JSON |
| `podx-transcode` | Normalize audio | AudioMeta | AudioMeta (updated) |
| `podx-transcribe` | Speech-to-text | AudioMeta | Transcript JSON |
| `podx-diarize` | Add speakers + timing | Transcript + audio | DiarizedTranscript JSON |
| `podx-deepcast` | AI analysis | Transcript | Deepcast markdown |
| `podx-notion` | Publish to Notion | Deepcast + metadata | Notion URL |
| `podx run` | Orchestrate pipeline | Episode selector | Complete output |

### Composable Design

```bash
# Full pipeline in one command
podx run --show "My Podcast" --date 2024-10-15

# Or compose individual steps with pipes
podx-fetch --show "My Podcast" --date 2024-10-15 \
  | podx-transcode \
  | podx-transcribe --model large-v3 \
  | podx-diarize \
  | podx-deepcast \
  | podx-notion
```

---

## 🐍 Python API

**NEW in v2.0:** Use PodX's core engines programmatically!

```python
from pathlib import Path
from podx.core.transcribe import TranscriptionEngine
from podx.core.diarize import DiarizationEngine
from podx.core.deepcast import DeepcastEngine

# Transcribe audio with GPU acceleration
engine = TranscriptionEngine(
    model="large-v3",
    device=None,  # Auto-detect: MPS/CUDA/CPU
    compute_type=None,  # Auto-select optimal
)
transcript = engine.transcribe(Path("audio.wav"))

# Add speaker diarization
diarizer = DiarizationEngine(
    language="en",
    device=None,  # Auto-detect: MPS/CUDA/CPU
)
diarized = diarizer.diarize(Path("audio.wav"), transcript["segments"])

# Generate AI analysis
analyzer = DeepcastEngine(
    model="gpt-4o",
    analysis_type="interview_guest_focused",
)
metadata = {"title": "Episode 1", "show_name": "My Podcast"}
markdown, insights = analyzer.deepcast(diarized, metadata)

print(f"Identified {len(set(w['speaker'] for seg in diarized['segments'] for w in seg.get('words', [])))} speakers")
print(f"Generated {len(insights['key_points'])} key insights")
```

**See [docs/CORE_API.md](docs/CORE_API.md) for complete API reference.**

---

## ⚡ Performance & GPU Acceleration

**NEW in v2.0:** Automatic GPU detection and optimization!

### Device Detection

PodX automatically detects and uses the best available hardware:

- **Apple Silicon (M1/M2/M3)**: MPS GPU for diarization, CPU for transcription
- **NVIDIA GPUs**: CUDA for both transcription and diarization
- **CPU fallback**: Optimized compute types for CPU-only systems

### Performance Benchmarks

Real-world performance on **MacBook Pro M2** (16-core GPU, 10-core CPU):

| Task | Hardware | 60min Episode | Speedup vs CPU |
|------|----------|---------------|----------------|
| **Transcription** | CPU (CTranslate2) | ~7.5 min | Baseline |
| **Diarization** | MPS GPU | ~1-2 min | **3-6x faster** |
| **Full Pipeline** | Mixed | ~10-12 min | ~5x realtime |

### Optimization Tips

```bash
# Use faster models for speed
podx run --model large-v3-turbo --show "My Show" --date 2024-10-15

# Skip optional steps
podx run --no-deepcast --no-notion  # Just transcription + diarization

# Use auto compute type (default in v2.0)
podx-transcribe --compute auto < audio.json
```

---

## 📚 Documentation

### Core Documentation

- **[Core API Reference](docs/CORE_API.md)** - Complete Python API documentation
- **[Architecture Guide](docs/ARCHITECTURE_V2.md)** - Core/CLI separation deep dive
- **[Testing Guide](docs/TESTING.md)** - Testing patterns and best practices
- **[Processing Pipeline](docs/PROCESSING_PIPELINE.md)** - Pipeline architecture details
- **[Plugin System](docs/PLUGINS.md)** - Creating custom plugins

### Command Reference

```bash
# Episode management
podx-fetch          # Download episodes from RSS/iTunes/YouTube
podx-transcode      # Normalize audio format

# Transcription pipeline
podx-transcribe     # Whisper-based speech-to-text
podx-diarize        # Speaker identification + word timing

# Analysis & export
podx-deepcast       # AI-powered analysis
podx-export         # Format conversion (SRT/VTT/TXT/MD)

# Publishing
podx-notion         # Publish to Notion

# Utilities
podx run            # Orchestrate complete pipeline
podx-models         # Manage Whisper models
```

---

## 🎯 Usage Examples

### Interactive Episode Browser

```bash
# Browse episodes with visual interface
podx-fetch --show "Huberman Lab" --interactive

# Output:
# 🎙️  Episodes for "Huberman Lab"
# ┌────┬────────────┬─────────────────────────────┬──────────┐
# │ #  │ Date       │ Title                       │ Duration │
# ├────┼────────────┼─────────────────────────────┼──────────┤
# │ 1  │ 2024-10-15 │ Dr. Peter Attia on Longevity│ 02:45:32 │
# │ 2  │ 2024-10-08 │ Science of Sleep           │ 01:52:18 │
# ...
```

### Custom Workflows

```bash
# Process with specific model
podx run --show "Lex Fridman" --date 2024-10-15 --model large-v3

# Skip AI analysis
podx run --show "My Podcast" --date 2024-10-15 --no-deepcast

# Custom pipeline with pipes
podx-fetch --show "Reply All" --date 2024-10-15 \
  | podx-transcode \
  | podx-transcribe --model large-v3 \
  | tee transcript.json \
  | podx-export --formats srt,txt
```

### Configuration-Driven Processing

```yaml
# ~/.podx/config.yaml
podcasts:
  lenny:
    names: ["Lenny's Podcast"]
    analysis:
      type: "interview_guest_focused"
    pipeline:
      deepcast: true
      notion: true
    notion_database: "work"

notion_databases:
  work:
    database_id: "your-db-id"
    token: "secret_token"
```

```bash
# Automatically applies config
podx run --show "Lenny's Podcast" --date 2024-10-15
```

---

## 🧪 Development

### Setup

```bash
# Clone repository
git clone https://github.com/evanhourigan/podx.git
cd podx

# Install with development dependencies
pip install -e ".[dev,asr,whisperx,llm,notion]"

# Run tests
pytest

# Run with coverage
pytest --cov=podx --cov-report=html
```

### Project Structure

```
podx/
├── podx/
│   ├── core/              # Pure business logic (9 modules)
│   │   ├── transcribe.py  # Transcription engine
│   │   ├── diarize.py     # Diarization engine
│   │   ├── deepcast.py    # Analysis engine
│   │   └── ...
│   ├── cli/               # CLI wrappers
│   │   ├── transcribe.py  # Click CLI for transcription
│   │   ├── diarize.py     # Click CLI for diarization
│   │   └── orchestrate.py # podx run command
│   ├── device.py          # GPU/device detection
│   ├── config.py          # Configuration management
│   └── ...
├── tests/                 # Test suite (285+ tests)
├── docs/                  # Documentation
└── pyproject.toml        # Package configuration
```

### Testing

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/unit/test_transcribe.py

# Run with coverage
pytest --cov=podx --cov-report=html

# Open coverage report
open htmlcov/index.html
```

---

## 🔧 System Requirements

### Required Dependencies

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Python 3.9+
python --version  # Should be 3.9 or higher
```

### Optional Dependencies

- **Hugging Face Token** - For speaker diarization (free account required)
- **OpenAI API Key** - For GPT-4 analysis
- **Notion Token** - For Notion publishing

### Hardware Recommendations

- **Minimum**: 8GB RAM, CPU-only (works but slower)
- **Recommended**: 16GB RAM, Apple Silicon or NVIDIA GPU
- **Optimal**: 32GB RAM, M2/M3 Pro/Max or RTX 3000+

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** and add tests
4. **Run the test suite**: `pytest`
5. **Commit your changes**: `git commit -m 'Add amazing feature'`
6. **Push to your fork**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Guidelines

- **Code Style**: Use `ruff` for formatting and linting
- **Type Hints**: All functions must have type annotations
- **Tests**: Add tests for new features
- **Documentation**: Update docs for user-facing changes

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

### Built With

- **[faster-whisper](https://github.com/guillaumekln/faster-whisper)** - Fast ASR inference
- **[WhisperX](https://github.com/m-bain/whisperX)** - Alignment and diarization
- **[OpenAI API](https://openai.com)** - GPT-4 analysis
- **[Click](https://click.palletsprojects.com)** - CLI framework
- **[Pydantic](https://pydantic.dev)** - Data validation
- **[Rich](https://rich.readthedocs.io)** - Terminal UI
- **[Textual](https://textual.textualize.io)** - TUI framework

---

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/evanhourigan/podx/issues)
- **Discussions**: [GitHub Discussions](https://github.com/evanhourigan/podx/discussions)

---

<div align="center">

**Built with ❤️ for podcast enthusiasts and developers**

⭐ Star this repo to show support!

</div>
