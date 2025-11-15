# ❓ PodX Frequently Asked Questions

Quick answers to common questions about PodX. For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Table of Contents

- [General Questions](#general-questions)
- [Features and Capabilities](#features-and-capabilities)
- [Installation and Setup](#installation-and-setup)
- [Transcription](#transcription)
- [Diarization](#diarization)
- [AI Analysis](#ai-analysis)
- [Performance](#performance)
- [Costs and Pricing](#costs-and-pricing)
- [Privacy and Data](#privacy-and-data)
- [Integration and API](#integration-and-api)
- [Comparison with Alternatives](#comparison-with-alternatives)

---

## General Questions

### What is PodX?

PodX is a comprehensive podcast processing platform that automates transcription, speaker diarization, and AI-powered analysis. It transforms podcast audio into searchable text, structured transcripts, and insightful summaries.

**Key features:**
- Automatic speech recognition (ASR) with multiple providers
- Speaker diarization (who said what)
- AI-powered analysis and summaries
- Multiple export formats (TXT, SRT, VTT, MD, JSON)
- Batch processing capabilities
- Python API for integration

### Who is PodX for?

PodX is designed for:
- **Podcasters** - Transcribe episodes for show notes and SEO
- **Researchers** - Analyze podcast content at scale
- **Content creators** - Repurpose audio into written content
- **Developers** - Build podcast-related applications
- **Accessibility professionals** - Create captions and transcripts

### Is PodX free?

**Yes, PodX is open source** (MIT License). The software is completely free to use.

**However, some features may incur costs:**
- **Local transcription** (faster-whisper) - FREE
- **OpenAI Whisper API** - Paid ($0.006/minute)
- **AI analysis** (GPT-4, Claude) - Paid (API usage costs)
- **Cloud GPU services** - Optional, paid

You can use PodX entirely for free with local models and no AI analysis.

### What podcasts can I process with PodX?

**Any podcast with a public RSS feed**, including:
- Major platforms (Apple Podcasts, Spotify, Google Podcasts)
- Self-hosted feeds
- Private feeds (with authentication)
- Direct audio file URLs

**You can also process:**
- Local audio files (MP3, WAV, M4A, etc.)
- YouTube videos (audio track)
- Any audio content in supported formats

### Do I need programming knowledge to use PodX?

**No, not for basic usage.** PodX provides CLI commands for all features:

```bash
# Simple command to process an episode
podx run --show "My Podcast" --date 2024-10-15
```

**However, programming knowledge helps for:**
- Advanced customization
- API integration
- Batch processing scripts
- Custom workflows

See [QUICKSTART.md](QUICKSTART.md) for beginner-friendly instructions.

---

## Features and Capabilities

### What transcription providers does PodX support?

PodX supports multiple ASR (Automatic Speech Recognition) providers:

1. **faster-whisper** (Default, Local, FREE)
   - Runs on your machine
   - No API costs
   - Good accuracy
   - Requires GPU for best performance

2. **OpenAI Whisper API** (Cloud, Paid)
   - Very accurate
   - Fast processing
   - $0.006 per minute
   - No GPU required

3. **HuggingFace Whisper** (Cloud, Free/Paid)
   - Various models available
   - Free tier available
   - Good for experimentation

**Usage:**
```bash
# Local (default)
podx run --asr-provider local

# OpenAI API
podx run --asr-provider openai

# HuggingFace
podx run --asr-provider huggingface
```

### What languages are supported?

PodX supports **99+ languages** via Whisper models, including:

**Major languages:**
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Dutch (nl)
- Japanese (ja)
- Chinese (zh)
- Korean (ko)
- Russian (ru)
- Arabic (ar)
- Hindi (hi)

**Usage:**
```bash
# Auto-detect language
podx run --show "My Podcast" --date 2024-10-15

# Force specific language
podx-transcribe --language es --input audio.mp3
```

### Does PodX support speaker diarization?

**Yes!** PodX can identify "who said what" in multi-speaker audio.

**Diarization engines:**
1. **PyAnnote** (Default) - Good accuracy, free
2. **WhisperX** - Better accuracy, requires installation

**Features:**
- Automatic speaker detection
- Configurable speaker count
- Speaker labels in transcripts (SPEAKER_00, SPEAKER_01, etc.)
- Exports with speaker names

**Usage:**
```bash
# Auto-detect speakers
podx run --show "My Podcast" --date 2024-10-15

# Specify exact speaker count
podx-diarize --num-speakers 2 < transcript.json

# Skip diarization
podx run --no-diarize
```

**Limitations:**
- Accuracy varies with audio quality
- Overlapping speech is challenging
- Similar-sounding voices may be confused

### What export formats are available?

PodX exports to multiple formats:

1. **JSON** - Full transcript with metadata
   - Timestamps, speakers, confidence scores
   - Machine-readable

2. **Plain Text (TXT)** - Simple text transcript
   - Easy to read
   - Good for sharing

3. **SRT (SubRip)** - Standard subtitle format
   - For video players
   - Time-synchronized

4. **VTT (WebVTT)** - Web subtitle format
   - HTML5 video
   - Web players

5. **Markdown (MD)** - Formatted text
   - Headers, speaker labels
   - Good for documentation

**Usage:**
```bash
# Export to all formats
podx-export --formats txt,srt,vtt,md,json < transcript.json

# Export single format
podx-export --formats txt < transcript.json
```

### Can PodX generate summaries and insights?

**Yes!** PodX supports AI-powered analysis via **DeepCast**:

**Features:**
- Episode summaries
- Key topics extraction
- Sentiment analysis
- Quote extraction
- Custom analysis prompts

**LLM Providers:**
- OpenAI (GPT-4, GPT-4o, GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet, Haiku)
- OpenRouter (multi-model access)
- Ollama (local models, FREE)

**Usage:**
```bash
# With OpenAI
export OPENAI_API_KEY="sk-..."
podx run --show "My Podcast" --date 2024-10-15

# With Claude
export ANTHROPIC_API_KEY="sk-ant-..."
podx run --llm-provider anthropic

# With local Ollama (free)
podx run --llm-provider ollama --llm-model llama2
```

### Can I process multiple episodes at once?

**Yes!** PodX supports batch processing:

**Option 1: Loop through dates**
```bash
for day in {01..07}; do
  podx run --show "Daily Podcast" --date "2024-10-$day"
done
```

**Option 2: Parallel processing**
```bash
cat dates.txt | parallel -j 4 podx run --show "My Podcast" --date {}
```

**Option 3: Python API**
```python
from podx.api import PodxClient

client = PodxClient()
episodes = [
    {"show": "Podcast 1", "date": "2024-10-15"},
    {"show": "Podcast 2", "date": "2024-10-16"},
]

for ep in episodes:
    client.process_episode(**ep)
```

See [ADVANCED.md](ADVANCED.md#batch-processing-and-automation) for details.

---

## Installation and Setup

### What are the system requirements?

**Minimum requirements:**
- Python 3.9 or higher
- 4GB RAM
- 5GB disk space (for models)
- FFmpeg installed

**Recommended for best performance:**
- Python 3.10+
- 8GB+ RAM
- 10GB+ disk space
- NVIDIA GPU with CUDA (for faster transcription)
- SSD storage

**Operating systems:**
- macOS 10.14+
- Ubuntu 20.04+
- Windows 10+ (with WSL recommended)

### How do I install PodX?

**Quick install:**
```bash
# Clone repository
git clone https://github.com/evanhourigan/podx.git
cd podx

# Install with all features
pip install -e ".[asr,whisperx,llm,notion]"

# Verify installation
podx --version
```

**Minimal install** (local transcription only):
```bash
pip install -e ".[asr]"
```

See [QUICKSTART.md](QUICKSTART.md#installation) for detailed instructions.

### Do I need a GPU?

**No, but it helps significantly.**

**Without GPU (CPU only):**
- Transcription is slower (2-4x real-time)
- Still functional
- Good for small batches

**With GPU (CUDA):**
- Transcription is faster (0.5-1x real-time)
- Better for large batches
- More energy efficient

**Cloud GPU alternatives:**
- Google Colab (free tier)
- AWS EC2 GPU instances
- Lambda Labs
- RunPod

### What API keys do I need?

**Optional API keys:**

1. **OpenAI** (for Whisper API or GPT-4 analysis)
   ```bash
   export OPENAI_API_KEY="sk-proj-..."
   ```

2. **Anthropic** (for Claude analysis)
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

3. **Notion** (for publishing to Notion)
   ```bash
   export NOTION_TOKEN="secret_..."
   export NOTION_DATABASE_ID="abc123..."
   ```

**You can use PodX without any API keys** using local models.

### How do I update PodX?

**Update from git:**
```bash
cd podx
git pull
pip install -e ".[asr,whisperx,llm,notion]"
```

**Verify update:**
```bash
podx --version
git log -1
```

---

## Transcription

### How accurate is the transcription?

**Accuracy depends on several factors:**

**Model size:**
- **base** - 74% accuracy, fast
- **small** - 80% accuracy, balanced
- **medium** - 84% accuracy, slower
- **large-v3** - 88% accuracy, slowest
- **large-v3-turbo** - 86% accuracy, fast (recommended)

**Audio quality:**
- Clear audio - 90%+ accuracy
- Background noise - 75-85% accuracy
- Poor quality - 60-75% accuracy

**Speaker factors:**
- Clear speech - Better accuracy
- Accents/dialects - May reduce accuracy
- Technical jargon - May need custom vocabulary

**Improving accuracy:**
- Use larger models (`--model large-v3`)
- Improve audio quality (good microphone, quiet room)
- Specify language (`--language en`)
- Use OpenAI Whisper API (most accurate)

### How long does transcription take?

**Processing time varies by:**

**Model and hardware:**
- **GPU (CUDA)**: 0.5-1x real-time (1 hour audio = 30-60 minutes)
- **CPU**: 2-4x real-time (1 hour audio = 2-4 hours)

**Model size:**
- **base**: Fastest (0.3x on GPU)
- **large-v3**: Slowest (1.5x on GPU)
- **large-v3-turbo**: Balanced (0.5x on GPU)

**Example times for 1-hour episode:**

| Setup | Model | Time |
|-------|-------|------|
| GPU (RTX 3090) | base | ~20 min |
| GPU (RTX 3090) | large-v3-turbo | ~30 min |
| GPU (RTX 3090) | large-v3 | ~60 min |
| CPU (8-core) | base | ~1 hour |
| CPU (8-core) | large-v3-turbo | ~2 hours |
| OpenAI API | whisper-1 | ~5 min |

### Can I transcribe files I already have?

**Yes!** You can process local audio files:

```bash
# Transcribe local file
podx-transcribe --input /path/to/episode.mp3

# Full pipeline with local file
podx run --input /path/to/episode.mp3

# Batch process directory
for f in *.mp3; do
  podx-transcribe --input "$f"
done
```

**Supported formats:**
- MP3, WAV, M4A, AAC
- FLAC, OGG, WMA
- Any format FFmpeg supports

### Can I use different Whisper models?

**Yes!** PodX supports all Whisper model variants:

**Available models:**
- `tiny` - Fastest, least accurate
- `base` - Fast, decent accuracy
- `small` - Balanced
- `medium` - Good accuracy
- `large-v2` - Very accurate
- `large-v3` - Most accurate
- `large-v3-turbo` - Fast + accurate (recommended)

**Usage:**
```bash
# Use specific model
podx run --model large-v3-turbo --show "Podcast"

# Use smallest/fastest
podx run --model base --show "Podcast"

# Use most accurate
podx run --model large-v3 --show "Podcast"
```

**Model sizes:**
- tiny: ~75MB
- base: ~150MB
- small: ~500MB
- medium: ~1.5GB
- large: ~3GB

---

## Diarization

### What is speaker diarization?

**Speaker diarization** identifies "who said what" in audio with multiple speakers.

**Output example:**
```
SPEAKER_00: Welcome to the podcast.
SPEAKER_01: Thanks for having me.
SPEAKER_00: Let's talk about AI.
SPEAKER_01: Great topic!
```

**Use cases:**
- Interview podcasts
- Panel discussions
- Multi-host shows
- Meeting transcripts

### How many speakers can PodX detect?

**Automatic detection** works for 2-10 speakers.

**Best results:**
- 2-3 speakers - Very good accuracy
- 4-5 speakers - Good accuracy
- 6+ speakers - Accuracy decreases

**Usage:**
```bash
# Auto-detect (recommended)
podx-diarize < transcript.json

# Specify exact count
podx-diarize --num-speakers 2 < transcript.json

# Specify range
podx-diarize --min-speakers 2 --max-speakers 4 < transcript.json
```

### Can I customize speaker names?

**Yes!** You can map speaker labels to names:

```python
from podx.api import PodxClient

client = PodxClient()

# Process with diarization
result = client.diarize("transcript.json")

# Map speakers to names
speaker_map = {
    "SPEAKER_00": "Alice",
    "SPEAKER_01": "Bob"
}

# Export with names
client.export(
    result,
    "output.txt",
    speaker_map=speaker_map
)
```

**Output:**
```
Alice: Welcome to the podcast.
Bob: Thanks for having me.
```

### Why is diarization inaccurate sometimes?

**Common causes:**

1. **Audio quality issues**
   - Background noise
   - Poor microphone quality
   - Overlapping speech

2. **Similar voices**
   - Same gender
   - Similar accents
   - Same speaking style

3. **Short segments**
   - Very brief utterances (<1s)
   - Hard to classify accurately

**Improving accuracy:**
- Use high-quality audio
- Specify exact speaker count
- Use WhisperX engine (more accurate)
- Post-process to fix errors

---

## AI Analysis

### What LLM providers are supported?

PodX supports multiple LLM providers:

1. **OpenAI** (GPT-4, GPT-4o, GPT-4o-mini)
   - Most popular
   - Very capable
   - Moderate cost

2. **Anthropic** (Claude 3.5 Sonnet, Haiku)
   - Excellent quality
   - Large context windows
   - Moderate cost

3. **OpenRouter** (Multi-model access)
   - Access many models
   - Flexible pricing
   - Good for experimentation

4. **Ollama** (Local, FREE)
   - Runs on your machine
   - No API costs
   - Privacy-friendly

**Usage:**
```bash
# OpenAI (default)
export OPENAI_API_KEY="sk-..."
podx run --llm-provider openai

# Claude
export ANTHROPIC_API_KEY="sk-ant-..."
podx run --llm-provider anthropic

# Ollama (local, free)
podx run --llm-provider ollama --llm-model llama2
```

### Can I use local LLMs (no API cost)?

**Yes!** Use Ollama for completely local, free AI analysis:

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download a model
ollama pull llama2

# Use with PodX
podx run --llm-provider ollama --llm-model llama2 --show "Podcast"
```

**Available models:**
- llama2 (7B, 13B, 70B)
- mistral (7B)
- mixtral (8x7B)
- phi-2 (2.7B)

**Trade-offs:**
- FREE (no API costs)
- Private (data stays local)
- Slower than cloud APIs
- Less capable than GPT-4/Claude

### Can I customize the analysis?

**Yes!** You can customize DeepCast analysis:

```python
from podx.api import PodxClient

client = PodxClient()

# Custom analysis prompt
custom_prompt = """
Analyze this podcast and provide:
1. Main topics discussed
2. Key insights and takeaways
3. Notable quotes
4. Controversial points
5. Actionable advice
"""

result = client.deepcast(
    transcript="transcript.json",
    system_prompt=custom_prompt,
    llm_provider="openai",
    llm_model="gpt-4o"
)
```

See [ADVANCED.md](ADVANCED.md#custom-prompts) for more examples.

### How much does AI analysis cost?

**Costs vary by provider and model:**

**OpenAI GPT-4o:**
- Input: $2.50 / 1M tokens
- Output: $10.00 / 1M tokens
- **1-hour podcast**: ~$0.50-2.00

**OpenAI GPT-4o-mini:**
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens
- **1-hour podcast**: ~$0.05-0.20

**Anthropic Claude 3.5 Sonnet:**
- Input: $3.00 / 1M tokens
- Output: $15.00 / 1M tokens
- **1-hour podcast**: ~$0.60-3.00

**Ollama (Local):**
- **FREE** (no API costs)
- Only hardware/electricity costs

**Cost optimization:**
- Use cheaper models (gpt-4o-mini, claude-haiku)
- Skip analysis for unimportant episodes
- Use local models (Ollama) when possible

---

## Performance

### How can I make transcription faster?

**Hardware optimizations:**
1. **Use GPU** (biggest improvement)
   ```bash
   podx run --device cuda
   ```

2. **Use smaller model**
   ```bash
   podx run --model base  # Much faster
   ```

3. **Use OpenAI API** (fastest, but paid)
   ```bash
   podx run --asr-provider openai
   ```

**Software optimizations:**
1. **Enable VAD** (skip silence)
   ```python
   result = client.transcribe("audio.mp3", vad_filter=True)
   ```

2. **Use int8 quantization**
   ```python
   result = client.transcribe("audio.mp3", compute_type="int8")
   ```

3. **Process in parallel** (multiple episodes)
   ```bash
   cat episodes.txt | parallel -j 4 podx run --show "Podcast" --date {}
   ```

See [ADVANCED.md](ADVANCED.md#performance-optimization) for details.

### Why is PodX using so much memory?

**Common causes:**

1. **Large model loaded**
   - `large-v3` uses ~4GB VRAM
   - Solution: Use smaller model

2. **Long audio file**
   - Very long episodes (5+ hours)
   - Solution: Split audio into chunks

3. **Multiple processes**
   - Parallel processing with too many workers
   - Solution: Reduce concurrency

**Solutions:**
```bash
# Use smaller model
podx run --model base

# Use CPU (less memory than GPU)
podx run --device cpu

# Use int8 compute type
podx-transcribe --compute-type int8
```

### Can I process podcasts in the cloud?

**Yes!** Several options:

1. **Google Colab** (Free tier available)
   - Free GPU access
   - Jupyter notebook interface
   - Easy to use

2. **AWS EC2** (Paid)
   - Scalable
   - Various GPU options
   - Pay per use

3. **Lambda Labs** (Paid)
   - GPU-optimized
   - Good pricing
   - Fast setup

4. **RunPod** (Paid)
   - Serverless GPUs
   - Flexible pricing
   - Docker support

**Example Docker setup:**
```dockerfile
FROM python:3.10

RUN apt-get update && apt-get install -y ffmpeg
COPY . /app
WORKDIR /app
RUN pip install -e ".[asr,llm]"

CMD ["podx", "run", "--show", "My Podcast"]
```

---

## Costs and Pricing

### What does PodX cost to run?

**PodX software: FREE** (open source, MIT license)

**Potential costs:**

1. **Transcription:**
   - Local (faster-whisper): FREE
   - OpenAI Whisper API: $0.006/minute ($0.36 per hour)

2. **AI Analysis (optional):**
   - Local (Ollama): FREE
   - GPT-4o-mini: ~$0.05-0.20 per episode
   - GPT-4o: ~$0.50-2.00 per episode
   - Claude: ~$0.60-3.00 per episode

3. **Cloud GPU (optional):**
   - Google Colab: FREE (with limits)
   - AWS EC2 GPU: $0.50-3.00 per hour
   - Lambda Labs: $0.50-2.00 per hour

**Example total cost per episode:**
- **FREE**: Local transcription + no analysis
- **$0.05-0.20**: Local transcription + cheap LLM
- **$0.40-0.60**: OpenAI Whisper + cheap LLM
- **1.00-3.00**: OpenAI Whisper + premium LLM

### Can I run PodX completely free?

**Yes!** Use this setup:

```bash
# Local transcription (FREE)
podx run --asr-provider local --model base

# No AI analysis (FREE)
podx run --no-deepcast

# Or use local LLM (FREE)
# 1. Install Ollama
ollama pull llama2

# 2. Use with PodX
podx run --llm-provider ollama --llm-model llama2
```

**Completely free setup:**
- Local transcription (faster-whisper)
- Local AI analysis (Ollama)
- No cloud services
- No API keys needed

**Trade-offs:**
- Slower processing (without GPU)
- Lower accuracy (smaller models)
- Less capable analysis (vs GPT-4)

---

## Privacy and Data

### Where is my data stored?

**By default: Locally on your machine**

**Data locations:**
- Audio files: Working directory
- Transcripts: Working directory
- Models: `~/.cache/huggingface/`
- Intermediate files: Working directory

**Cloud services (only if you use them):**
- OpenAI API: Audio sent to OpenAI servers
- Anthropic API: Transcripts sent to Anthropic servers
- HuggingFace API: Audio sent to HuggingFace servers

**Privacy-friendly setup:**
```bash
# 100% local processing
podx run --asr-provider local --llm-provider ollama --no-notion
```

### Is my podcast data sent to external services?

**Only if you choose to use external services:**

**Local processing (no external data):**
- faster-whisper transcription
- Ollama analysis
- PyAnnote diarization

**External services (data sent to provider):**
- OpenAI Whisper API (audio sent to OpenAI)
- OpenAI/Anthropic analysis (transcripts sent)
- Notion publishing (transcripts sent)

**You control what data is sent** by choosing providers.

### Can I use PodX offline?

**Mostly yes**, with caveats:

**Offline capabilities:**
- Transcription (if models already downloaded)
- Diarization
- Export to formats

**Requires internet:**
- Initial model download
- Fetching episodes from RSS feeds
- Cloud API services (OpenAI, Anthropic)
- Notion publishing

**Offline setup:**
```bash
# 1. Download models while online
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"

# 2. Process offline with local files
podx run --input local-file.mp3 --no-notion --no-deepcast
```

### Is PodX GDPR compliant?

**PodX itself doesn't collect any data.**

**Your GDPR compliance depends on:**

1. **Podcast content** - Do you have rights to process it?
2. **External services** - Check their compliance:
   - OpenAI: GDPR compliant
   - Anthropic: GDPR compliant
   - HuggingFace: GDPR compliant

3. **Your usage** - How you store/share transcripts

**For sensitive content:**
- Use local processing only (no cloud APIs)
- Encrypt stored transcripts
- Don't publish to Notion without consent

---

## Integration and API

### Can I use PodX in my own application?

**Yes!** PodX provides a Python API:

```python
from podx.api import PodxClient

# Initialize client
client = PodxClient()

# Fetch episode
episode = client.fetch_episode("My Podcast", "2024-10-15")

# Transcribe
transcript = client.transcribe(episode["audio_path"])

# Diarize
diarized = client.diarize(transcript)

# Export
client.export(diarized, "output.txt")
```

See [ADVANCED.md](ADVANCED.md#python-api-deep-dive) for full API documentation.

### Can I integrate PodX with my web application?

**Yes!** Use FastAPI/Flask for web integration:

**FastAPI example:**
```python
from fastapi import FastAPI, BackgroundTasks
from podx.api import PodxClient
from podx.progress import APIProgressReporter

app = FastAPI()
client = PodxClient()

@app.post("/transcribe")
async def transcribe(audio_url: str, background_tasks: BackgroundTasks):
    reporter = APIProgressReporter()

    def process():
        client.transcribe(audio_url, progress_reporter=reporter)

    background_tasks.add_task(process)
    return {"task_id": "123", "status": "processing"}

@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    # Return progress events from reporter
    return reporter.get_events()
```

See [ADVANCED.md](ADVANCED.md#web-api-integration) for complete examples.

### Does PodX have a REST API?

**Not yet**, but you can build one easily:

**Option 1: Use Python API directly**
```python
from podx.api import PodxClient
client = PodxClient()
```

**Option 2: Build REST API wrapper**
```python
# See ADVANCED.md for FastAPI/Flask examples
```

**Option 3: Use as CLI from your app**
```python
import subprocess
result = subprocess.run(["podx", "run", "--show", "Podcast"], capture_output=True)
```

**Future plans:**
- Official REST API server
- WebSocket for real-time progress
- Docker container with API
- Cloud-hosted version

### Can I contribute to PodX?

**Yes! Contributions are welcome.**

**Ways to contribute:**
1. Report bugs (GitHub Issues)
2. Suggest features (GitHub Discussions)
3. Submit pull requests
4. Improve documentation
5. Write tutorials/blog posts
6. Share your use cases

**Getting started:**
```bash
# Fork repository
git clone https://github.com/yourusername/podx.git
cd podx

# Create branch
git checkout -b feature/my-feature

# Make changes, test, commit
pytest
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/my-feature
```

See `CONTRIBUTING.md` (coming soon) for guidelines.

---

## Comparison with Alternatives

### How does PodX compare to Rev.ai/Otter.ai?

| Feature | PodX | Rev.ai | Otter.ai |
|---------|------|--------|----------|
| **Cost** | FREE (local) or $0.006/min (API) | $0.25/min | $8.33/month |
| **Privacy** | Can run 100% locally | Cloud only | Cloud only |
| **Accuracy** | 85-90% (Whisper large) | 90-95% | 85-90% |
| **Diarization** | Yes (free) | Yes (included) | Yes (included) |
| **API** | Python API | REST API | REST API |
| **Self-hosted** | Yes | No | No |
| **Open source** | Yes | No | No |

**PodX advantages:**
- FREE for local processing
- Privacy (self-hosted)
- Customizable
- Open source

**PodX disadvantages:**
- Requires technical setup
- Lower accuracy than Rev.ai (unless using OpenAI API)
- No GUI (yet)

### How does PodX compare to Descript?

| Feature | PodX | Descript |
|---------|------|----------|
| **Transcription** | Yes | Yes |
| **Editing** | No | Yes (advanced) |
| **Cost** | FREE | $15/month |
| **Diarization** | Yes | Yes |
| **Video** | No | Yes |
| **GUI** | No | Yes |
| **API** | Yes | Limited |

**Use PodX if:**
- You want free/low-cost transcription
- You need API integration
- You want self-hosted solution
- You're comfortable with CLI

**Use Descript if:**
- You need video editing
- You want GUI interface
- You need advanced editing features

### Can I replace my paid transcription service with PodX?

**Maybe! It depends on your needs:**

**PodX works well for:**
- High volume (batch processing)
- Budget-conscious projects
- Privacy-sensitive content
- Technical users
- API integration

**Paid services better for:**
- Non-technical users (GUI needed)
- Maximum accuracy required
- Customer support needed
- Video editing
- Collaboration features

**Cost comparison (100 hours/month):**
- PodX (local): **FREE**
- PodX (OpenAI API): **$36/month**
- Rev.ai: **$1,500/month**
- Otter.ai Business: **$20/user/month**

---

## Still have questions?

- **Documentation**: [docs/](.)
- **GitHub Issues**: [Report bugs](https://github.com/evanhourigan/podx/issues)
- **GitHub Discussions**: [Ask questions](https://github.com/evanhourigan/podx/discussions)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
