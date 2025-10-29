<div align="center">

# 🎙️ PodX

**Production-Grade Podcast Processing Platform**

Transform podcast audio into structured insights with AI-powered transcription, analysis, and multi-platform publishing.

[![Version 2.0.0](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/yourusername/podx/releases/tag/v2.0.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests 285+](https://img.shields.io/badge/tests-285%2B%20passing-success.svg)](tests/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Features](#-features) •
[Quick Start](#-quick-start) •
[Documentation](#-documentation) •
[Examples](#-examples) •
[Contributing](#-contributing)

</div>

---

## 🌟 Why PodX?

Traditional podcast processing is **manual, time-consuming, and doesn't scale**. PodX transforms hours of audio into actionable insights in minutes through an intelligent, composable pipeline:

```bash
# From raw podcast URL to searchable transcript + AI analysis + Notion page
podx run --show "Lenny's Podcast" --date 2024-10-15 \
  --diarize --deepcast --notion
```

**Result:** Word-level transcripts with speaker attribution, AI-generated summaries, key insights, and beautifully formatted Notion pages—all automated.

---

## 🎉 What's New in v2.0 - The iPhone Moment

**Major simplification!** PodX v2.0 dramatically streamlines the user experience by removing complexity and making intelligent defaults:

### User Experience Improvements
- **🎯 Unified Alignment** - Word-level timing now integrated into `podx-diarize` (removed separate `podx-align` command)
- **📊 Smart Defaults** - Diarization, preprocessing, deepcast, and markdown extraction enabled by default
- **🔥 Removed Fidelity System** - No more confusing 1-5 fidelity levels; use explicit flags instead
- **⚡ Removed Workflow Presets** - No more `--quick`/`--analyze`/`--publish`; clearer explicit options
- **🧹 Simplified Export** - `podx-export` now focuses solely on transcript format conversion
- **📝 Cleaner CLI** - Removed redundant options, simplified flag structure

### Architecture Revolution - Core/CLI Separation
**NEW in v2.0:** Complete separation of business logic from UI concerns:

- **🏗️ Core Modules** - 9 pure business logic engines in `podx.core.*` (3,014 lines)
- **🎨 CLI Wrappers** - Thin UI layer around core engines
- **✅ 97% Test Coverage** - 285+ tests with comprehensive mocking
- **🔌 Reusable API** - Use core engines programmatically without CLI
- **📚 Full Documentation** - Complete API reference and architecture guide

**Benefits:**
- Use PodX as a Python library (no CLI needed)
- Build custom UIs (TUI, web, GUI) on core engines
- Test business logic without UI mocking
- Clear, maintainable codebase

**The result?** PodX v2.0 is simpler, more intuitive, easier to use, AND easier to extend and integrate.

**Upgrading from v1.x?** Most changes are backward compatible. Remove `--fidelity` flags and workflow presets from your scripts. See [Migration Guide](docs/MIGRATION_V2.md) for details.

---

## ✨ Features

### 🚀 Core Capabilities

- **🎯 Smart Episode Discovery** - Search by show name, date, or RSS feed with interactive browsing
- **⚡ High-Fidelity Transcription** - Local Whisper models (large-v3, turbo) with precision/recall presets
- **🎭 Speaker Diarization** - Automatic speaker identification and attribution using WhisperX
- **🧠 AI-Powered Analysis** - Context-aware summaries, key insights, and quotes using GPT-4/Claude
- **📊 Multi-Platform Publishing** - Notion, Discord, Slack, webhooks, and custom integrations
- **🔌 Extensible Plugin System** - 7 builtin plugins + easy custom plugin development

### 🛠️ Production-Ready Features

- **📝 YAML Configuration** - Podcast-specific settings with intelligent defaults
- **🔄 Resume & Recovery** - Automatic state management and crash recovery
- **🎨 Rich Output Formats** - SRT, VTT, TXT, Markdown, JSON, Notion pages
- **🌊 Unix Philosophy** - Composable CLI tools with JSON stdin/stdout
- **📦 Comprehensive Testing** - 285+ tests with 97% coverage (183 core module tests + unit/integration)

### 🎓 Advanced Capabilities

- **Semantic Restoration** - AI-powered correction of transcription errors
- **Length-Adaptive Analysis** - More insights from longer episodes, concise for shorter ones
- **Interactive Workflows** - Visual episode browsers with pagination and filtering
- **Two-Phase Processing** - Interactive transcript and episode selection for preprocessing and diarization
- **State Persistence** - Run-state tracking for large batch processing
- **Plugin Marketplace** - Pip-installable extensions via entry points

---

## 🏗️ Architecture

PodX follows a **composable pipeline architecture** where each command does one thing well and outputs JSON:

```
                          ┌──────────────────────────────────────┐
                          │         podx run                     │
                          │    (Intelligent Orchestrator)        │
                          └──────────────────┬───────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
           ┌────────▼────────┐      ┌───────▼────────┐      ┌───────▼────────┐
           │  P1: SOURCE     │      │  P2: AUDIO     │      │  P3: ASR       │
           │  podx-fetch     │─────▶│  podx-transcode│─────▶│  podx-transcribe│
           │  (Get Episodes) │      │  (Normalize)   │      │  (Whisper AI)  │
           └─────────────────┘      └────────────────┘      └────────┬───────┘
                                                                      │
                    ┌─────────────────────────────────────────────────┤
                    │                                                 │
           ┌───────────────┐      ┌─────────▼───────┐
           │  P4: DIARIZE  │      │  P5: EXPORT     │
           │  podx-diarize │─────▶│  podx-export    │
           │  (Speakers +  │      │  (SRT/TXT/MD)   │
           │   Alignment)  │      │                 │
           └───────────────┘      └─────────┬───────┘
                                                                      │
                    ┌─────────────────────────────────────────────────┤
                    │                                                 │
           ┌────────▼────────┐      ┌───────────────┐       ┌────────▼────────┐
           │  P6: ANALYSIS   │      │  P7: PUBLISH  │       │  UTILITIES      │
           │  podx-deepcast  │─────▶│  podx-notion  │       │  podx-models    │
           │  (AI Insights)  │      │  (Integrate)  │       │  podx-list      │
           └─────────────────┘      └───────────────┘       └─────────────────┘

                            📊 All steps output JSON for piping
                            🔄 Resume from any point with state tracking
                            🎯 Use individual commands or run full pipeline
```

### Key Design Principles

1. **Unix Philosophy** - Each tool does one thing well, composable via pipes
2. **JSON I/O** - Structured data between steps enables automation
3. **State Management** - Automatic detection of completed steps, resume from crashes
4. **Plugin Architecture** - Extend any pipeline stage with custom logic
5. **Progressive Enhancement** - Start with basic transcription, add features incrementally

---

## 🚀 Quick Start

### ⚡ 5-Minute Quickstart

Get your first podcast processed in under 5 minutes:

```bash
# 1. Install (30 seconds)
pipx install git+https://github.com/your-org/podx.git

# 2. Optional: Set up AI features (if you want analysis + Notion)
export OPENAI_API_KEY=sk-...    # For AI analysis
export NOTION_TOKEN=secret_...   # For Notion publishing

# 3. Run! (2-4 minutes depending on episode length)
podx run --show "Lex Fridman" --date 2024-10-15 --full

# That's it! Check your output:
# 📁 Lex_Fridman_Podcast/2024-10-15/
#    ├── transcript-diarized.json      (Word-level transcript with speakers)
#    ├── transcript.txt, transcript.srt (Human-readable formats)
#    ├── deepcast.md                   (AI analysis with insights)
#    └── notion.out.json               (Notion page URL)
```

**What just happened?**
- ✅ Downloaded episode audio from RSS feed
- ✅ Transcribed with Whisper (large-v3-turbo)
- ✅ Added word-level timestamps and identified speakers (via diarization)
- ✅ Generated AI summary with key insights
- ✅ Published to Notion with rich formatting

**No AI keys?** No problem! Skip `--full` and use `--no-deepcast --no-notion` for just transcription with speaker diarization.

---

### Installation

```bash
# Install with pipx (recommended - global availability)
pipx install git+https://github.com/your-org/podx.git

# Or with pip in a virtual environment
pip install git+https://github.com/your-org/podx.git
```

### Your First Podcast

```bash
# 1. Configure API keys (optional, for AI analysis)
export OPENAI_API_KEY=sk-...
export NOTION_TOKEN=secret_...

# 2. Process a podcast with one command
podx run --show "Lex Fridman Podcast" --date 2024-10-15 \
  --diarize --deepcast --notion

# Output:
# ✅ Transcript saved to Lex_Fridman_Podcast/2024-10-15/transcript-diarized.json
# ✅ Analysis saved to Lex_Fridman_Podcast/2024-10-15/deepcast.md
# ✅ Notion page created: https://notion.so/...
```

**That's it!** You now have:
- 📝 Word-level transcript with timestamps
- 🎭 Speaker-attributed dialogue
- 🧠 AI-generated summary with key insights
- 📊 Beautifully formatted Notion page

### Using Configuration (Recommended)

```bash
# 1. Initialize configuration
podx config init

# 2. Edit ~/.podx/config.yaml with your podcast preferences
# 3. Run with automatic settings
podx run --show "Lenny's Podcast" --date 2024-10-15
# ↳ Auto-applies: --diarize --deepcast --notion --extract-markdown
# ↳ Uses: interview_guest_focused analysis type
# ↳ Routes to: work Notion database
```

---

## 🐍 Using PodX as a Python Library

**NEW in v2.0:** Use PodX's core engines programmatically without the CLI!

```python
from podx.core.transcribe import TranscribeEngine
from podx.core.diarize import DiarizeEngine
from podx.core.deepcast import DeepcastEngine

# Transcribe audio
transcribe = TranscribeEngine(model="large-v3-turbo")
transcript = transcribe.transcribe("audio.wav")

# Add speaker diarization
diarize = DiarizeEngine()
diarized = diarize.diarize("audio.wav", transcript["segments"])

# Generate AI analysis
deepcast = DeepcastEngine(model="gpt-4o", analysis_type="interview_guest_focused")
markdown, insights = deepcast.deepcast({"segments": diarized}, metadata)

print(f"Found {len(insights['key_points'])} key points")
```

**Perfect for:**
- Building custom workflows and automation
- Integrating into existing Python applications
- Creating new UIs (TUI, web, desktop)
- Batch processing scripts

See [Core API Reference](docs/CORE_API.md) for complete documentation.

---

## 📚 Documentation

### Core Guides

- **[Core API Reference](docs/CORE_API.md)** ⭐ NEW - Complete API for all 9 core modules
- **[Architecture Guide](docs/ARCHITECTURE_V2.md)** ⭐ NEW - Deep dive into core/CLI separation
- **[Testing Guide](docs/TESTING.md)** ⭐ NEW - Testing patterns and best practices
- **[Configuration Guide](docs/CONFIGURATION.md)** - YAML setup and podcast-specific settings
- **[Plugin System](docs/PLUGINS.md)** - Creating and using plugins

### Quick References

| Command | Purpose | Example |
|---------|---------|---------|
| `podx run` | Complete pipeline | `podx run --show "NPR" --date 2024-10-15` |
| `podx-fetch` | Download episodes | `podx-fetch --show "The Daily" --interactive` |
| `podx-transcribe` | Transcribe audio | `podx-transcribe --model large-v3 < audio.json` |
| `podx-deepcast` | AI analysis | `podx-deepcast < transcript.json` |
| `podx plugin` | Plugin management | `podx plugin list --type publish` |
| `podx config` | Configuration | `podx config show` |

### CLI Tools Reference

```bash
# Episode Management
podx-fetch          # Download episodes (iTunes, RSS, YouTube)
podx-transcode      # Convert audio formats (wav, mp3, aac)

# Transcription Pipeline
podx-transcribe     # Speech-to-text (Whisper models)
podx-diarize        # Speaker identification + word-level timestamps (WhisperX)
podx-preprocess     # Transcript normalization & restoration

# Analysis & Export
podx-deepcast       # AI-powered analysis (GPT-4, Claude)
podx-export         # Format conversion (SRT, VTT, TXT, MD)

# Publishing
podx-notion         # Upload to Notion
podx plugin list    # Show available publishers

# Utilities
podx run            # Orchestrate complete pipeline
podx config         # Manage configuration
podx plugin         # Plugin management
```

---

## 🎯 Examples

### Interactive Episode Discovery

Browse episodes visually with pagination and search:

```bash
podx-fetch --show "Huberman Lab" --interactive

# Output:
# 🎙️  Episodes for "Huberman Lab"
# ┌────┬────────────┬─────────────────────────────┬──────────┐
# │ #  │ Date       │ Title                       │ Duration │
# ├────┼────────────┼─────────────────────────────┼──────────┤
# │ 1  │ 2024-10-15 │ Dr. Peter Attia on Longevity│ 02:45:32 │
# │ 2  │ 2024-10-08 │ Science of Sleep           │ 01:52:18 │
# ...
# Select episode (1-10, N/P, F=filter, Q=quit): _
```

### Composable Unix Pipeline

Build custom workflows with stdin/stdout:

```bash
# Basic pipeline
podx-fetch --show "Reply All" --date 2024-10-15 \
  | podx-transcode --to wav16 \
  | podx-transcribe --model large-v3 \
  | podx-export --formats srt,txt

# Advanced pipeline with analysis
cat transcript.json \
  | podx-diarize --audio audio.wav \
  | podx-deepcast --model gpt-4 \
  | tee analysis.json \
  | podx-notion --db $NOTION_DB_ID
```

### Multi-Podcast Configuration

Manage different podcasts with YAML config:

```yaml
# ~/.podx/config.yaml
podcasts:
  lenny:
    names: ["Lenny's Podcast", "Lenny Rachitsky"]
    analysis:
      type: "interview_guest_focused"
      custom_prompts: "Focus on product management frameworks..."
    pipeline:
      diarize: true
      deepcast: true
      notion: true
    notion_database: "work"

  huberman:
    names: ["Huberman Lab"]
    analysis:
      type: "solo_commentary"
    pipeline:
      deepcast: true
    notion_database: "personal"

notion_databases:
  work:
    database_id: "your-work-db-id"
    token: "secret_work_token"
  personal:
    database_id: "your-personal-db-id"
    token: "secret_personal_token"
```

Then simply run:

```bash
podx run --show "Lenny's Podcast" --date 2024-10-15
# ↳ Automatically applies all lenny config settings
```

---

## ⚡ Performance Benchmarks

Real-world performance on a MacBook Pro M2 (16GB RAM).

**v1.0 Optimizations:**
- **20x faster preprocessing** - Batch LLM restore (100 segments: ~200s → ~10s)
- **10x faster export** - Manifest caching (100 episodes: ~50s → ~5s)
- **4x faster deepcast** - Parallel chunk processing (10 chunks: ~40s → ~10s)

### Transcription Speed

| Episode Length | Model | Fidelity | Time | Real-time Factor |
|----------------|-------|----------|------|------------------|
| 30 min | tiny | 1 (fast) | 1.2 min | 25x faster |
| 30 min | small | 1 (fast) | 2.1 min | 14x faster |
| 30 min | large-v3-turbo | 2 (balanced) | 3.8 min | 8x faster |
| 30 min | large-v3 | 3 (precision) | 5.2 min | 6x faster |
| 60 min | large-v3-turbo | 2 (balanced) | 7.5 min | 8x faster |
| 120 min | large-v3-turbo + align | 3 (precision) | 18 min | 7x faster |

### Full Pipeline Performance

| Pipeline Stage | 30min Episode | 60min Episode | 120min Episode |
|----------------|---------------|---------------|----------------|
| Fetch + Transcode | 15s | 25s | 45s |
| Transcribe (large-v3-turbo) | 3.8min | 7.5min | 15min |
| Align (WhisperX) | 45s | 1.5min | 3min |
| Diarize (WhisperX) | 30s | 1min | 2min |
| Preprocess + Restore | 6s | 12s | 25s |
| Deepcast (GPT-4) | 12s | 23s | 45s |
| Export + Notion | 10s | 15s | 25s |
| **Total (Fidelity 3)** | **~6min** | **~11min** | **~22min** |

### Cost Estimates (per episode)

| Configuration | 30min | 60min | 120min | Notes |
|---------------|-------|-------|--------|-------|
| Basic (local only) | $0.00 | $0.00 | $0.00 | Transcription only |
| + OpenAI Whisper API | $0.18 | $0.36 | $0.72 | At $0.006/min |
| + GPT-4 analysis | $0.24 | $0.42 | $0.78 | Includes API costs |
| + Claude Sonnet | $0.15 | $0.28 | $0.52 | More affordable |
| Full (local + GPT-4) | $0.06 | $0.12 | $0.24 | Best value |

**Key Takeaways:**
- 🚀 **8-25x faster than real-time** for transcription
- ⚡ **v1.0 is 4-20x faster** than v0.x (optimized preprocessing, deepcast, export)
- 💰 **$0.06-0.78 per episode** depending on configuration
- 🎯 **Complete processing in ~20% of episode length** (full pipeline with diarization)
- 💻 **Runs entirely on your machine** (except optional AI features)

### Optimization Tips

```bash
# 1. Skip unnecessary steps for faster processing
podx run --no-diarize  # If you don't need speaker labels
podx run --no-deepcast  # Skip AI analysis for quick transcription

# 2. Use turbo models for speed
podx run --model large-v3-turbo  # 30% faster, 95% accuracy

# 3. Batch process multiple episodes
for date in 2024-10-{01..15}; do
  podx run --show "My Podcast" --date $date
done

# 4. Use preprocessing only when needed
podx run --no-preprocess  # Skip normalization/restoration if not needed
```

---

### Advanced Command Chaining

PodX commands are designed to pipe together like Unix tools:

```bash
# Example 1: Custom preprocessing pipeline
podx-fetch --show "Lex Fridman" --date 2024-10-15 \
  | podx-transcode --to wav16 \
  | podx-transcribe --model large-v3 --preset precision \
  | podx-preprocess --merge --normalize \
  | podx-diarize \
  | podx-deepcast --model gpt-4 --type interview_guest_focused \
  | tee result.json \
  | jq '.summary'  # Extract just the summary

# Example 2: Parallel processing with xargs
cat episodes.txt | xargs -P 4 -I {} \
  podx run --show "My Show" --date {}

# Example 3: Custom analysis workflow
podx-transcribe < audio-meta.json \
  | podx-preprocess --restore --restore-model gpt-4-mini \
  | podx-deepcast --type panel_discussion \
  | podx-export --pdf \
  | podx-notion --db MY_DB_ID
```

### Batch Processing Patterns

```bash
# Process entire podcast backlog
podx-list --scan-dir ~/podcasts \
  | jq -r '.[] | .show + " " + .date' \
  | while read show date; do
      podx run --show "$show" --date "$date"
    done

# Resume failed runs automatically
find ~/podcasts -name "episode-meta.json" -exec dirname {} \; \
  | xargs -I {} podx run --workdir {}

# Weekly automation with cron
# Add to crontab: 0 9 * * MON /path/to/weekly-podx.sh
# weekly-podx.sh:
#!/bin/bash
SHOWS=("Lex Fridman" "Huberman Lab" "Lenny's Podcast")
LAST_MONDAY=$(date -d "last monday" +%Y-%m-%d)

for show in "${SHOWS[@]}"; do
  podx run --show "$show" --date "$LAST_MONDAY" \
    --notion --notion-db "$NOTION_DB"
done
```

---

## 🔌 Plugin System

Extend PodX with custom functionality:

### Using Plugins

```bash
# List available plugins
podx plugin list

# Validate a plugin
podx plugin validate webhook-publish --config-file config.json

# Create a new plugin
podx plugin create my-custom source --output-dir ./plugins
```

### Built-in Plugins

| Plugin | Type | Description |
|--------|------|-------------|
| **YouTube Source** | Source | Download from YouTube |
| **Dropbox Source** | Source | Download from Dropbox |
| **Google Drive Source** | Source | Download from Google Drive |
| **Anthropic Analysis** | Analysis | Claude-powered analysis |
| **Discord Publisher** | Publish | Post to Discord channels |
| **Slack Publisher** | Publish | Post to Slack channels |
| **Webhook Publisher** | Publish | Generic HTTP webhooks |

### Creating Custom Plugins

```python
from podx.plugins import PublishPlugin, PluginMetadata, PluginType

class MyPublisher(PublishPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="my-publisher",
            version="1.0.0",
            description="Publish to my platform",
            author="Your Name",
            plugin_type=PluginType.PUBLISH,
        )

    def publish_content(self, content, **kwargs):
        # Your implementation
        return {"success": True, "url": "https://..."}
```

**See [Plugin Documentation](docs/PLUGINS.md) for complete guide.**

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      PodX Platform                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Sources    │  │ Processors   │  │  Publishers  │     │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤     │
│  │ • iTunes     │  │ • Transcribe │  │ • Notion     │     │
│  │ • RSS Feeds  │→ │ • Align      │→ │ • Discord    │     │
│  │ • YouTube    │  │ • Diarize    │  │ • Slack      │     │
│  │ • Dropbox    │  │ • Deepcast   │  │ • Webhooks   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Plugin System (Entry Points)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │     State Management & Configuration Layer          │   │
│  │  • YAML Config  • Run State  • Artifact Detection   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Episode URL → Fetch → Audio → Transcode → WAV
                                            ↓
                    JSON ← Transcript ← Transcribe
                      ↓
              ┌───────┴───────┐
              ↓               ↓
          Align           Diarize
              ↓               ↓
         [timestamps]   [speakers]
              ↓               ↓
              └───────┬───────┘
                      ↓
                  Deepcast (AI)
                      ↓
              ┌───────┴───────┐
              ↓               ↓
           Notion         Discord/Slack
```

### Modular Design

- **🔧 Domain Layer** - Type-safe models and enums
- **🗄️ State Layer** - Artifact detection and recovery
- **⚙️ Service Layer** - Business logic and orchestration
- **🖥️ UI Layer** - Interactive CLI components
- **🔌 Plugin Layer** - Extensible integrations

---

## 🎓 Use Cases

### For Content Creators

- **Searchable Archives** - Make your entire podcast catalog searchable
- **Show Notes Automation** - Generate summaries, key points, and timestamps
- **Multi-Platform Publishing** - Automatically publish to Notion, Discord, Slack

### For Researchers

- **Interview Analysis** - Extract insights from expert interviews
- **Thematic Coding** - Identify recurring themes and patterns
- **Quote Extraction** - Find and attribute key quotes with timestamps

### For Enterprises

- **Meeting Transcription** - Convert recorded meetings to searchable text
- **Knowledge Management** - Integrate insights into internal wikis
- **Compliance & Archival** - Maintain searchable records with speaker attribution

### For Developers

- **Data Pipeline** - Integrate podcast data into existing workflows
- **Custom Plugins** - Extend functionality for specific use cases
- **Batch Processing** - Process entire podcast catalogs programmatically

---

## 🧪 Development

### Prerequisites

```bash
# macOS with Homebrew
brew install ffmpeg direnv jq

# Python 3.9+
python --version  # Should be 3.9 or higher
```

### Setup

```bash
# Clone repository
git clone https://github.com/your-org/podx.git
cd podx

# Setup environment
cp .env.example .env
direnv allow  # Auto-creates venv and loads .env

# Install development dependencies
pip install -e ".[dev,asr,whisperx,llm,notion]"

# Run tests
pytest -v
```

### Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/unit/test_plugin_system.py

# Run with coverage
pytest --cov=podx --cov-report=html

# Run fast tests only (skip integration)
pytest -m "not slow"
```

### Project Structure

```
podx/
├── podx/                       # Main package
│   ├── domain/                 # Domain models and enums
│   ├── state/                  # State management
│   ├── services/               # Business logic
│   ├── ui/                     # Interactive components
│   ├── api/                    # Public API
│   ├── builtin_plugins/        # Built-in plugins
│   └── *.py                    # Core modules
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
├── docs/                       # Documentation
├── pyproject.toml             # Package configuration
└── README.md                  # This file
```

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Quick Contribution Guide

1. **Fork the repository** and clone your fork
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** and add tests
4. **Run the test suite**: `pytest`
5. **Commit your changes**: `git commit -m 'Add amazing feature'`
6. **Push to your fork**: `git push origin feature/amazing-feature`
7. **Open a Pull Request** with a clear description

### Contribution Ideas

- 🐛 **Bug Reports** - Found a bug? Open an issue with reproduction steps
- ✨ **Feature Requests** - Have an idea? Start a discussion
- 📝 **Documentation** - Improve guides, add examples, fix typos
- 🔌 **Plugins** - Create and share custom plugins
- 🧪 **Tests** - Increase test coverage
- 🌍 **Translations** - Help internationalize PodX

### Development Best Practices

- **Code Style**: We use `ruff` for formatting and linting
- **Type Hints**: All functions should have type annotations
- **Tests**: Add tests for new features (aim for 80%+ coverage)
- **Documentation**: Update docs for user-facing changes
- **Commits**: Write clear, descriptive commit messages

**See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.**

---

## 📊 Roadmap

### Current Version: 0.2.0-alpha

- ✅ Core transcription pipeline
- ✅ AI-powered analysis
- ✅ Plugin system
- ✅ Notion integration
- ✅ YAML configuration
- ✅ Interactive workflows

### Upcoming Features

**v0.3.0 - Performance & Scale**
- ⏳ Parallel processing for batch jobs
- ⏳ Streaming transcription for real-time processing
- ⏳ Caching layer for faster repeated processing
- ⏳ Progress tracking for long-running jobs

**v0.4.0 - Enhanced Analysis**
- ⏳ Custom analysis templates
- ⏳ Topic extraction and tagging
- ⏳ Sentiment analysis
- ⏳ Multi-model comparison workflows

**v0.5.0 - Ecosystem**
- ⏳ Web UI for visual pipeline management
- ⏳ REST API for programmatic access
- ⏳ Plugin marketplace
- ⏳ Cloud deployment guides

### Community Requests

Vote on features in [GitHub Discussions](https://github.com/your-org/podx/discussions)!

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### What This Means

- ✅ **Commercial use** - Use PodX in commercial projects
- ✅ **Modification** - Modify and adapt the code
- ✅ **Distribution** - Share the software
- ✅ **Private use** - Use privately without disclosure
- ℹ️ **Liability** - No warranty provided
- ℹ️ **License notice** - Include copyright notice in distributions

---

## 🙏 Acknowledgments

### Built With

- **[faster-whisper](https://github.com/guillaumekln/faster-whisper)** - Fast ASR inference
- **[WhisperX](https://github.com/m-bain/whisperX)** - Alignment and diarization
- **[OpenAI API](https://openai.com)** - GPT-4 analysis
- **[Anthropic API](https://anthropic.com)** - Claude analysis
- **[Notion API](https://developers.notion.com)** - Page creation
- **[Click](https://click.palletsprojects.com)** - CLI framework
- **[Pydantic](https://pydantic.dev)** - Data validation
- **[Rich](https://rich.readthedocs.io)** - Terminal UI

### Contributors

Thanks to all our contributors! 🎉

<!-- Contributors will be auto-generated -->

### Inspiration

PodX draws inspiration from:
- Unix philosophy of composable tools
- Modern data pipeline architectures
- AI-powered knowledge management systems

---

## 📞 Support & Community

### Getting Help

- 📖 **[Documentation](docs/)** - Comprehensive guides and references
- 💬 **[Discussions](https://github.com/your-org/podx/discussions)** - Ask questions and share ideas
- 🐛 **[Issues](https://github.com/your-org/podx/issues)** - Report bugs and request features
- 💼 **[LinkedIn](https://linkedin.com/in/your-profile)** - Connect with the maintainer

### Stay Updated

- ⭐ **Star this repo** to show support and stay notified
- 👁️ **Watch** for release notifications
- 🐦 **Follow** on Twitter/X: [@your_handle](https://twitter.com/your_handle)

---

## 🌟 Show Your Support

If PodX has helped you or your organization, consider:

- ⭐ **Starring** this repository
- 🐛 **Reporting** bugs and suggesting features
- 📝 **Sharing** your use case in Discussions
- 🔗 **Linking** to PodX from your project
- 💼 **Mentioning** on LinkedIn or Twitter

---

<div align="center">

**Built with ❤️ by developers who love podcasts**

[⬆ Back to Top](#-podx)

</div>
