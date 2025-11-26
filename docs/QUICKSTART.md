# 🚀 PodX Quick Start Guide

Get up and running with PodX in minutes! This guide will walk you through installation, basic usage, and your first podcast processing workflow.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Basic Configuration](#basic-configuration)
- [Your First Episode](#your-first-episode)
- [Understanding the Output](#understanding-the-output)
- [Next Steps](#next-steps)

---

## Prerequisites

### System Requirements

- **Python**: 3.9 or higher
- **FFmpeg**: For audio processing
- **Disk Space**: ~2GB for models + space for audio files

### Check Your System

```bash
# Check Python version
python --version  # Should be 3.9+

# Check FFmpeg
ffmpeg -version  # Should show version info
```

### Install FFmpeg (if needed)

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg

# Or download from: https://ffmpeg.org/download.html
```

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/evanhourigan/podx.git
cd podx
```

### Step 2: Install PodX

Choose your installation based on what features you need:

#### Minimal Installation (Local transcription only)

```bash
pip install -e ".[asr]"
```

#### Recommended Installation (All features)

```bash
pip install -e ".[asr,whisperx,llm,notion,search,audio-analysis]"
```

#### Installation Options Explained

- `asr` - Local transcription with faster-whisper (required)
- `whisperx` - Advanced diarization with WhisperX (recommended)
- `llm` - AI analysis with GPT-4/Claude (optional)
- `notion` - Notion publishing (optional)
- `search` - **NEW!** Transcript search & analysis (optional)
- `audio-analysis` - **NEW!** Audio quality analysis (optional)

### Step 3: Verify Installation

```bash
# Check PodX is installed
podx --version

# List available commands
podx --help

# Check individual commands
podx fetch --help
podx transcribe --help
```

---

## Basic Configuration

### 🧙 Interactive Setup Wizard (Recommended - NEW in v2.1.0!)

The easiest way to configure PodX is with the interactive setup wizard:

```bash
podx init
```

This will guide you through:
- API key configuration (OpenAI, Anthropic, OpenRouter, Notion)
- Default transcription settings
- Default AI model selection
- Output preferences
- Optional features (shell completion, profiles)

### Manual API Key Setup (Alternative)

PodX works without API keys for local transcription. Add keys for optional features:

#### OpenAI (for GPT-4 analysis or whisper-1 transcription)

```bash
export OPENAI_API_KEY="sk-..."
```

#### Anthropic (for Claude analysis)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### Notion (for publishing)

```bash
export NOTION_TOKEN="secret_..."
export NOTION_DATABASE_ID="abc123..."
```

### Make API Keys Permanent (Optional)

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
# Add to ~/.zshrc (macOS) or ~/.bashrc (Linux)
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc
source ~/.zshrc
```

---

## Your First Episode

Let's process your first podcast episode! We'll use the "Lex Fridman Podcast" as an example.

### Option 1: Full Pipeline (Recommended)

Process everything in one command:

```bash
podx run --show "Lex Fridman Podcast" --date 2024-10-15
```

This will:
1. 🔍 Find the episode from the show's RSS feed
2. ⬇️  Download the audio file
3. 🎵 Normalize audio for processing
4. 🎙️ Transcribe with speech-to-text
5. 🎭 Add speaker labels (diarization)
6. 🧠 Generate AI-powered summary (if API key set)
7. 📊 Export to multiple formats

### Option 2: Step-by-Step

Process the pipeline step by step:

```bash
# 1. Fetch the episode
podx fetch --show "Lex Fridman Podcast" --date 2024-10-15 | tee fetch.json

# 2. Transcode audio (normalize)
podx transcode < fetch.json | tee transcode.json

# 3. Transcribe to text
podx transcribe < transcode.json | tee transcript.json

# 4. Add speaker labels
podx diarize < transcript.json | tee diarized.json

# 5. Export to formats
podx export --formats txt,srt,vtt < diarized.json
```

### Option 3: Quick Transcription Only

Just transcribe without extra features:

```bash
podx run --show "Lex Fridman Podcast" --date 2024-10-15 \
  --no-deepcast --no-notion --no-export
```

---

## Understanding the Output

After processing, you'll find your files in a structured directory:

```
Lex_Fridman_Podcast/2024-10-15-yann-lecun-meta-ai/
├── audio.mp3                          # Original downloaded audio
├── audio-transcoded.wav               # Normalized for processing
├── transcript-large-v3-turbo.json     # Base transcript
├── transcript-diarized.json           # With speaker labels
├── deepcast-outline.md                # AI analysis (if enabled)
├── exports/                           # Exported formats
│   ├── transcript.txt                 # Plain text
│   ├── transcript.srt                 # Subtitles
│   ├── transcript.vtt                 # WebVTT
│   └── transcript.md                  # Markdown
└── notion-page-url.txt                # Notion URL (if published)
```

### Key Files Explained

#### `transcript-large-v3-turbo.json`

Raw transcript with timestamps:

```json
{
  "text": "Full transcript text...",
  "segments": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Welcome to the podcast."
    }
  ],
  "language": "en"
}
```

#### `transcript-diarized.json`

Same as above, but with speaker labels:

```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Welcome to the podcast.",
      "speaker": "SPEAKER_00"
    },
    {
      "start": 3.5,
      "end": 7.2,
      "text": "Thanks for having me.",
      "speaker": "SPEAKER_01"
    }
  ]
}
```

#### `deepcast-outline.md`

AI-generated summary and insights:

```markdown
# Episode Title

## Summary
A concise overview of the episode...

## Key Topics
- Topic 1
- Topic 2

## Insights
Detailed analysis...
```

---

## Common Use Cases

### 1. Process Recent Episode

```bash
# Get today's episode
podx run --show "The Daily" --date $(date +%Y-%m-%d)

# Get yesterday's episode
podx run --show "The Daily" --date $(date -d yesterday +%Y-%m-%d)
```

### 2. Batch Process Multiple Episodes (NEW in v2.1.0!)

```bash
# Auto-detect and transcribe all new episodes (parallel processing!)
podx batch transcribe --auto-detect --parallel 4

# Full pipeline for multiple episodes
podx batch pipeline --auto-detect --steps transcribe,diarize,export --parallel 2

# Check batch status
podx batch status
```

**Old method (still works):**
```bash
# Process a week of episodes
for day in {01..07}; do
  podx run --show "My Podcast" --date "2024-10-$day"
done
```

### 3. Use Custom RSS Feed

```bash
# Process from direct RSS URL
podx run --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-15
```

### 4. Export Only

If you already have a transcript and just want to export:

```bash
podx export --input transcript.json --formats txt,srt,vtt,md
```

---

## Quick Troubleshooting

### "Command not found: podx"

The installation didn't complete properly. Try:

```bash
pip install -e ".[asr,whisperx,llm,notion]"
```

### "FFmpeg not found"

Install FFmpeg using the instructions in [Prerequisites](#prerequisites).

### "Model download is slow"

The first run downloads ~1-2GB of models. Subsequent runs will be much faster.

Use a smaller model for faster downloads:

```bash
podx run --show "My Podcast" --date 2024-10-15 --model base
```

### "Out of memory"

Use a smaller model or enable CPU-only mode:

```bash
# Use smaller model
podx run --model base

# Force CPU (slower but less memory)
podx transcribe --device cpu
```

### "Episode not found"

- Check the show name spelling
- Try `--interactive` mode to browse episodes visually
- Use `--rss-url` for direct RSS access

```bash
# Interactive mode
podx fetch --show "My Podcast" --interactive
```

---

## Next Steps

Now that you've processed your first episode, explore more features:

### 📚 Learn More

- **[Advanced Usage](ADVANCED.md)** - Custom models, batch processing, Python API
- **[CLI Reference](CLI.md)** - Complete command documentation
- **[Python API](api/python-api.md)** - Use PodX in your own applications
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[FAQ](FAQ.md)** - Frequently asked questions

### 🎯 Try These Features

1. **🔍 Search & Analysis (NEW!)**: Search your transcript library
   ```bash
   # Index a transcript
   podx search index transcript.json --episode-id ep001

   # Keyword search
   podx search query "artificial intelligence"

   # Extract quotes
   podx analyze quotes transcript.json

   # Speaker analytics
   podx analyze speakers transcript.json
   ```

2. **🎨 PDF & HTML Export (NEW!)**: Beautiful exports with dark mode
   ```bash
   podx export transcript.json --formats pdf,html
   ```

3. **⚡ Quick Commands (NEW!)**: Use preset profiles
   ```bash
   podx quick podcast.mp3   # Fast transcription
   podx full podcast.mp3    # Complete pipeline
   podx hq podcast.mp3      # High-quality processing
   ```

4. **💰 Cost Estimation (NEW!)**: Know before you spend
   ```bash
   podx estimate --duration 3600 --llm-model gpt-4o
   ```

5. **Interactive Mode**: Browse episodes visually
   ```bash
   podx fetch --show "Huberman Lab" --interactive
   ```

6. **Python API**: Use PodX in your own code
   ```python
   from podx.api import PodxClient
   client = PodxClient()
   result = client.transcribe("episode.mp3")
   ```

---

## Getting Help

- **Documentation**: [docs/](.)
- **Issues**: [GitHub Issues](https://github.com/evanhourigan/podx/issues)
- **Discussions**: [GitHub Discussions](https://github.com/evanhourigan/podx/discussions)

---

**Happy podcasting! 🎙️**
