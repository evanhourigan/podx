# PodX Quick Start Guide

Get started with PodX v2.0 in minutes! This guide covers the three ways to use PodX:
1. **CLI Commands** - Composable command-line tools
2. **PodX Studio** - Interactive terminal UI
3. **Python SDK** - Programmatic API

## Installation

```bash
# Install PodX with all features
pip install podx[asr,llm,whisperx,notion]

# Or install only what you need
pip install podx              # Core only
pip install podx[asr]         # + local transcription
pip install podx[llm]         # + AI analysis
pip install podx[notion]      # + Notion integration
```

## 1. CLI Commands (Composable Pipeline)

PodX provides individual CLI commands that can be piped together:

### Fetch a Podcast Episode

```bash
# Search and download from RSS feed
podx-fetch --show "Lenny's Podcast" --date 2024-03-15 > episode.json

# Download from YouTube
podx-fetch --youtube-url "https://youtube.com/watch?v=xyz"
```

### Transcribe Audio

```bash
# Transcribe with Whisper (local)
cat episode.json | podx-transcribe --model base > transcript.json

# Or with OpenAI Whisper API
cat episode.json | podx-transcribe --model openai:large-v3-turbo > transcript.json
```

### Diarize (Speaker Identification)

```bash
# Add speaker labels using WhisperX
cat transcript.json | podx-diarize > diarized.json
```

### AI Analysis with Deepcast

```bash
# Generate summary, quotes, and analysis
cat transcript.json | podx-deepcast --model gpt-4.1 > analysis.json
```

### Export to Multiple Formats

```bash
# Export to TXT, SRT, VTT, MD
cat transcript.json | podx-export --formats txt,srt,vtt,md
```

### Full Pipeline Example

```bash
# Complete workflow in one command chain
podx-fetch --show "Lenny's Podcast" --date 2024-03-15 | \
  podx-transcribe --model base | \
  podx-diarize | \
  podx-deepcast --model gpt-4.1 | \
  podx-export --formats txt,srt,md
```

### Orchestrator Command

Or use the `podx run` orchestrator to handle the full pipeline:

```bash
# Interactive mode - pick from your library
podx run --interactive

# Process specific episode end-to-end
podx run --show "Lenny's Podcast" --date 2024-03-15 \
  --transcribe --diarize --deepcast --export
```

## 2. PodX Studio (Interactive TUI)

Launch the beautiful terminal UI for interactive processing:

```bash
podx-studio
```

**Features:**
- 📥 Browse and fetch podcast episodes
- 🎙️ Process audio through the pipeline
- 📊 View processed episodes
- ⚙️ Configure settings
- ⌨️ Keyboard shortcuts for power users

**Navigation:**
- Arrow keys / Tab - Navigate
- Enter - Select
- Escape / q - Back / Quit

## 3. Python SDK (Programmatic)

Use PodX as a library in your Python code:

### Basic Transcription

```python
from podx import TranscriptionEngine
from pathlib import Path

# Initialize engine
engine = TranscriptionEngine(model="base", compute_type="int8")

# Transcribe audio
transcript = engine.transcribe(Path("audio.wav"))

print(f"Transcribed {len(transcript['segments'])} segments")
print(f"Language: {transcript['language']}")
```

### Full Pipeline

```python
from podx import (
    TranscriptionEngine,
    DiarizationEngine,
    DeepcastEngine,
    ExportEngine,
)
from pathlib import Path

# Step 1: Transcribe
transcription_engine = TranscriptionEngine(model="base")
transcript = transcription_engine.transcribe(Path("audio.wav"))

# Step 2: Diarize (speaker identification)
diarization_engine = DiarizationEngine()
diarized = diarization_engine.diarize(
    audio_path=Path("audio.wav"),
    transcript=transcript
)

# Step 3: AI Analysis
deepcast_engine = DeepcastEngine(model="gpt-4.1", temperature=0.2)
analysis = deepcast_engine.analyze(diarized)

print(f"Summary: {analysis['summary']}")
print(f"Key Points: {len(analysis['key_points'])}")

# Step 4: Export
export_engine = ExportEngine()
export_engine.export_all(
    transcript=diarized,
    output_dir=Path("output"),
    formats=["txt", "srt", "vtt", "md"]
)
```

### Fetch from YouTube

```python
from podx import YouTubeEngine

engine = YouTubeEngine()
result = engine.download("https://youtube.com/watch?v=xyz")

print(f"Downloaded: {result['title']}")
print(f"Audio: {result['audio_path']}")
```

### Fetch from RSS Feed

```python
from podx import fetch_episode, find_feed_url

# Find feed
feed_url = find_feed_url("Lenny's Podcast")

# Fetch specific episode
episode = fetch_episode(
    feed_url=feed_url,
    date="2024-03-15"
)

print(f"Title: {episode['title']}")
print(f"Audio: {episode['audio_path']}")
```

## Configuration

PodX uses environment variables and config files for settings:

### Environment Variables

```bash
# OpenAI API (for transcription or deepcast)
export OPENAI_API_KEY="sk-..."

# HuggingFace API (for transcription)
export HF_API_TOKEN="hf_..."

# Notion integration
export NOTION_TOKEN="secret_..."
export NOTION_DB_ID="..."

# Defaults
export PODX_DEFAULT_ASR_MODEL="base"
export PODX_DEFAULT_AI_MODEL="gpt-4.1"
```

### Config File

Create `~/.podx/config.yaml`:

```yaml
default_asr_model: "base"
default_ai_model: "gpt-4.1"
default_compute: "int8"

# Output directories
output_base_dir: "./podcasts"

# Notion databases
notion:
  databases:
    main:
      db_id: "abc123..."
      properties:
        podcast: "Podcast"
        date: "Date"
```

## Next Steps

- **Architecture Deep Dive**: See [ARCHITECTURE_V2.md](./ARCHITECTURE_V2.md)
- **API Reference**: See [CORE_API.md](./CORE_API.md)
- **Migration Guide**: See [MIGRATION_V1_TO_V2.md](./MIGRATION_V1_TO_V2.md)
- **Examples**: See [API_EXAMPLES.md](./API_EXAMPLES.md)

## Common Workflows

### Workflow 1: Quick Transcription

```bash
# CLI
podx-transcribe --input audio.wav --model base

# Python
from podx import TranscriptionEngine
engine = TranscriptionEngine(model="base")
transcript = engine.transcribe("audio.wav")
```

### Workflow 2: YouTube → Notion

```bash
# Fetch, transcribe, analyze, upload to Notion
podx-fetch --youtube-url "https://youtube.com/watch?v=xyz" | \
  podx-transcribe --model base | \
  podx-deepcast --model gpt-4.1 | \
  podx-notion --db YOUR_DB_ID
```

### Workflow 3: Batch Processing

```python
from podx import TranscriptionEngine
from pathlib import Path

engine = TranscriptionEngine(model="base")

for audio_file in Path("audio/").glob("*.wav"):
    print(f"Processing {audio_file}...")
    transcript = engine.transcribe(audio_file)

    # Save transcript
    output = audio_file.with_suffix(".json")
    output.write_text(transcript.model_dump_json(indent=2))
```

## Troubleshooting

### "No module named 'faster_whisper'"

```bash
pip install podx[asr]
```

### "OpenAI API key not found"

```bash
export OPENAI_API_KEY="sk-..."
```

### "WhisperX not available"

```bash
pip install podx[whisperx]
```

## Getting Help

- **GitHub**: https://github.com/evanhourigan/podx
- **Issues**: https://github.com/evanhourigan/podx/issues
- **Documentation**: https://github.com/evanhourigan/podx/tree/main/docs

---

**Happy podcasting! 🎙️**
