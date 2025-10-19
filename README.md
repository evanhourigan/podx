<div align="center">

# 🎙️ Podx

**Production-Grade Podcast Processing Platform**

Transform podcast audio into structured insights with AI-powered transcription, analysis, and multi-platform publishing.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Features](#-features) •
[Quick Start](#-quick-start) •
[Documentation](#-documentation) •
[Examples](#-examples) •
[Contributing](#-contributing)

</div>

---

## 🌟 Why Podx?

Traditional podcast processing is **manual, time-consuming, and doesn't scale**. Podx transforms hours of audio into actionable insights in minutes through an intelligent, composable pipeline:

```bash
# From raw podcast URL to searchable transcript + AI analysis + Notion page
podx run --show "Lenny's Podcast" --date 2024-10-15 \
  --align --diarize --deepcast --notion
```

**Result:** Word-level transcripts with speaker attribution, AI-generated summaries, key insights, and beautifully formatted Notion pages—all automated.

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
- **⚙️ Fidelity Levels** - Presets from "fast preview" to "production quality"
- **🎨 Rich Output Formats** - SRT, VTT, TXT, Markdown, JSON, Notion pages
- **🌊 Unix Philosophy** - Composable CLI tools with JSON stdin/stdout
- **📦 Comprehensive Testing** - 240+ tests with 98% success rate

### 🎓 Advanced Capabilities

- **Dual QA Transcription** - Parallel precision + recall tracks with consensus merging
- **Semantic Restoration** - AI-powered correction of transcription errors
- **Length-Adaptive Analysis** - More insights from longer episodes, concise for shorter ones
- **Interactive Workflows** - Visual episode browsers with pagination and filtering
- **State Persistence** - Run-state tracking for large batch processing
- **Plugin Marketplace** - Pip-installable extensions via entry points

---

## 🚀 Quick Start

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
  --align --diarize --deepcast --notion

# Output:
# ✅ Transcript saved to Lex_Fridman_Podcast/2024-10-15/transcript-large-v3.json
# ✅ Analysis saved to Lex_Fridman_Podcast/2024-10-15/deepcast-brief.md
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
# ↳ Auto-applies: --align --deepcast --notion --extract-markdown
# ↳ Uses: interview_guest_focused analysis type
# ↳ Routes to: work Notion database
```

---

## 📚 Documentation

### Core Guides

- **[Configuration Guide](docs/CONFIGURATION.md)** - YAML setup and podcast-specific settings
- **[Plugin System](docs/PLUGINS.md)** - Creating and using plugins
- **[Interactive Workflows](docs/INTERACTIVE_FETCH.md)** - Visual episode browsing

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
podx-align          # Word-level timestamps (WhisperX)
podx-diarize        # Speaker identification (WhisperX)
podx-preprocess     # Transcript normalization & restoration

# Analysis & Export
podx-deepcast       # AI-powered analysis (GPT-4, Claude)
podx-export         # Format conversion (SRT, VTT, TXT, MD)
podx-agreement      # Compare analyses
podx-consensus      # Merge dual transcripts

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

### Fidelity Levels

Balance speed vs. quality with preset fidelity levels:

```bash
# Fidelity 1: Fast preview (deepcast only, ~2 min)
podx run --show "The Daily" --date 2024-10-15 --fidelity 1

# Fidelity 3: Production quality (precision, align, diarize, ~15 min)
podx run --show "The Daily" --date 2024-10-15 --fidelity 3

# Fidelity 5: Maximum quality (dual QA, preprocessing, restore, ~30 min)
podx run --show "The Daily" --date 2024-10-15 --fidelity 5
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
  | podx-align --audio audio.wav \
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
      align: true
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

## 🔌 Plugin System

Extend Podx with custom functionality:

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
│                      Podx Platform                          │
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
- 🌍 **Translations** - Help internationalize Podx

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
- ⏳ Multi-model analysis with consensus
- ⏳ Custom analysis templates
- ⏳ Topic extraction and tagging
- ⏳ Sentiment analysis

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

- ✅ **Commercial use** - Use Podx in commercial projects
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

Podx draws inspiration from:
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

If Podx has helped you or your organization, consider:

- ⭐ **Starring** this repository
- 🐛 **Reporting** bugs and suggesting features
- 📝 **Sharing** your use case in Discussions
- 🔗 **Linking** to Podx from your project
- 💼 **Mentioning** on LinkedIn or Twitter

---

<div align="center">

**Built with ❤️ by developers who love podcasts**

[⬆ Back to Top](#-podx)

</div>
