# podx

🎙️ **Intelligent Podcast Processing Platform**

Composable podcast tooling with advanced AI analysis, YAML configuration, and multi-database support.

## ✨ Latest Features

- **🎛️ YAML Configuration System** - Human-readable configs with podcast-specific settings
- **🎯 Advanced Prompt Engineering** - Specialized analysis types (guest-focused, host-focused, etc.)
- **🗃️ Multiple Notion Databases** - Route different podcasts to different databases automatically
- **📏 Length-Adaptive Extraction** - More insights from longer episodes, concise summaries for short ones
- **🔌 Plugin Architecture** - Extensible system for custom processing steps
- **⚙️ Smart Defaults** - Eliminate repetitive CLI arguments with intelligent configuration

## 🚀 Quick Start

```bash
# 1. Install globally
pipx install -e ".[asr,whisperx,llm,notion]"

# 2. Initialize configuration
podx config init

# 3. Process any podcast with one simple command
podx run --show "Lenny's Podcast" --date 2025-08-17
# ↳ Automatically applies: --align --deepcast --extract-markdown --notion
# ↳ Uses guest-focused analysis with product management prompts
# ↳ Routes to work Notion database with work API token
```

**📖 [Complete Configuration Guide →](CONFIGURATION.md)**

## 🎯 Intelligent Podcast Processing

### Advanced Analysis Types

| Analysis Type             | Focus                            | Perfect For                       |
| ------------------------- | -------------------------------- | --------------------------------- |
| `interview_guest_focused` | Guest insights & expertise       | Lenny's Podcast, Tim Ferriss Show |
| `interview_host_focused`  | Host questions & frameworks      | Lex Fridman Podcast               |
| `business`                | Strategy & market insights       | Y Combinator, startup content     |
| `tech`                    | Technical depth & implementation | Developer podcasts                |
| `educational`             | Learning concepts & frameworks   | Academic content                  |

### YAML Configuration Example

```yaml
# ~/.podx/config.yaml
podcasts:
  lenny:
    names: ["Lenny's Podcast", "Lenny Rachitsky"]
    analysis:
      type: "interview_guest_focused"
      custom_prompts: |
        Focus on product management insights,
        frameworks, and actionable advice...
    pipeline:
      align: true
      deepcast: true
      notion: true
    notion_database: "work" # Auto-routes to work DB
```

### Multiple Notion Databases

```yaml
notion_databases:
  personal:
    database_id: "personal-db-id"
    token: "personal-token"
  work:
    database_id: "work-db-id"
    token: "work-token"
```

## Installation

### Option 1: Global Installation (Recommended)

Install globally so commands are available from anywhere:

```bash
# Clone and install globally
git clone <repo>
cd podx
pipx install -e ".[asr,whisperx,llm,notion]"
```

### Option 2: Local Development Installation

For development with virtual environment:

```bash
# Clone and install locally
git clone <repo>
cd podx
pip install -e ".[asr,whisperx,llm,notion]"
```

**Note**: With Option 1 (pipx), all `podx-*` commands will be available globally. With Option 2, you need to activate the virtual environment or be in the project directory.

- `podx-fetch`: Find & download an episode by show/date/title or RSS URL (supports `--interactive` for browsing)
- `podx-transcode`: `ffmpeg` to `wav` (16k mono) / `mp3` / `aac` (supports `--interactive` for browsing downloaded episodes)
- `podx-transcribe`: `faster-whisper` (fast pass) (supports `--interactive` with model selection)
- `podx-align`: `WhisperX` alignment (word-level timings) (supports `--interactive` for browsing transcripts)
- `podx-diarize`: `WhisperX` diarization (speaker labels) (supports `--interactive` for browsing aligned transcripts)
- `podx-export`: Write `SRT`/`VTT`/`TXT`/`MD`
- `podx-deepcast`: AI-powered transcript analysis and summarization
- `podx-notion`: Upload Deepcast output to Notion as formatted pages
- `podx run`: Convenience orchestrator that chains steps

### 🎛️ Configuration Management

- `podx config init`: Create example YAML configuration
- `podx config show`: View current configuration (syntax highlighted)
- `podx config validate`: Validate configuration syntax and settings
- `podx config databases`: List configured Notion databases
- `podx podcast list`: Show all podcast-specific configurations
- `podx podcast create`: Create new podcast configuration
- `podx plugin list`: Show available plugins

## Setup

```bash
brew install direnv ffmpeg jq
# hook direnv into your shell once:
# echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
# source ~/.zshrc

# clone & enter
cd ~/code
git clone <your-repo> podx
cd podx

# env and venv
cp .env.example .env
direnv allow

# For global installation (recommended):
pipx install -e ".[asr,whisperx,llm,notion]"

# For local development:
pip install -U pip
pip install -e ".[asr]" # faster-whisper backend
# Optional for alignment/diarization:
pip install -e ".[whisperx]"
# Optional for AI analysis:
pip install -e ".[llm]"
# Optional for Notion integration:
pip install -e ".[notion]"
```

## Quick start

### Interactive Episode Selection

Browse and download episodes with a visual interface:

```bash
# Interactive browsing - shows paginated episode list, saves to <SHOW>/<DATE>/
podx-fetch --show "The Podcast" --interactive
```

This saves both the audio file and `episode-meta.json` to the episode directory.

**📖 [Interactive Fetch Guide →](INTERACTIVE_FETCH.md)**

### Interactive Transcoding

Browse downloaded episodes and transcode them:

```bash
# Browse all episodes in current directory and subdirectories
podx-transcode --interactive

# Scan a specific directory
podx-transcode --interactive --scan-dir /path/to/podcasts
```

This shows all episodes with `episode-meta.json`, indicates which have already been transcoded (✓ Done vs ○ New), and saves the transcoded audio and `audio-meta.json` in the episode directory.

### Interactive Transcription

Browse transcoded episodes and select ASR model for transcription:

```bash
# Browse all transcoded episodes and select model interactively
podx-transcribe --interactive

# Scan a specific directory
podx-transcribe --interactive --scan-dir /path/to/podcasts
```

Features:

- Shows all transcoded episodes (with `audio-meta.json`)
- Displays which models have already been used (e.g., "✓ base, large-v3")
- Two-step selection: choose episode, then choose ASR model
- Model selection shows recommendations and prevents accidental re-transcription
- Saves to `transcript-{model}.json` (e.g., `transcript-large-v3.json`)
- Each model creates a separate transcript file - no overwriting!

### Interactive Alignment

Browse existing transcripts and align them with audio for word-level timings:

```bash
# Browse all transcripts (transcript-{model}.json files)
podx-align --interactive

# Scan a specific directory
podx-align --interactive --scan-dir /path/to/podcasts
```

Features:

- Shows all existing transcripts with their ASR models
- Displays alignment status (✓ if `aligned-transcript-{model}.json` exists)
- Confirmation prompt when re-aligning existing aligned transcripts
- Saves to `aligned-transcript-{model}.json` in episode directory
- Multiple transcripts per episode (one per ASR model)

### Interactive Diarization

Browse aligned transcripts and add speaker identification:

```bash
# Browse all aligned transcripts (aligned-transcript-{model}.json files)
podx-diarize --interactive

# Scan a specific directory
podx-diarize --interactive --scan-dir /path/to/podcasts
```

Features:

- Shows all existing aligned transcripts with their ASR models
- Displays diarization status (✓ if `diarized-transcript-{model}.json` exists)
- Confirmation prompt when re-diarizing existing diarized transcripts
- Saves to `diarized-transcript-{model}.json` in episode directory
- Multiple transcripts per episode (one per ASR model)

### Unix-style pipeline (JSON on stdout/stdin):

```bash
# Using show name (iTunes search) - files stay organized in smart directories
podx-fetch --show "The Podcast" --date 2024-10-02 \
| podx-transcode --to wav16 \
| podx-transcribe \
| tee "The Podcast/2024-10-02/base.json" \
| podx-export --txt "The Podcast/2024-10-02/base.txt" --srt "The Podcast/2024-10-02/base.srt"

# Using RSS URL (for private/unlisted podcasts)
podx-fetch --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-02 \
| podx-transcode --to wav16 \
| podx-transcribe \
| tee "The Podcast/2024-10-02/base.json" \
| podx-export --txt "The Podcast/2024-10-02/base.txt" --srt "The Podcast/2024-10-02/base.srt"
```

### Add alignment/diarization only when needed:

```bash
cat "The Podcast/2024-10-02/base.json" \
| podx-align --audio "$(jq -r .audio_path "The Podcast/2024-10-02/base.json")" \
| tee "The Podcast/2024-10-02/aligned.json" \
| podx-diarize --audio "$(jq -r .audio_path "The Podcast/2024-10-02/base.json")" \
| tee "The Podcast/2024-10-02/diar.json" \
| podx-export --srt "The Podcast/2024-10-02/episode.srt" --vtt "The Podcast/2024-10-02/episode.vtt" --txt "The Podcast/2024-10-02/episode.txt"
```

### One-shot convenience:

```bash
# Using show name (iTunes search)
# Minimal happy-path (fast pass; fetch → transcode → transcribe → export)
podx run --show "The Podcast" --date 2024-10-02 --workdir work/

# Add alignment & diarization
podx run --show "The Podcast" --date 2024-10-02 --align --diarize --workdir work/

# Add Deepcast (AI analysis)
export OPENAI_API_KEY=sk-...
podx run --show "The Podcast" --date 2024-10-02 --align --diarize --deepcast --workdir work/

# Add Notion upload (complete pipeline)
export NOTION_TOKEN=secret_xxx
export NOTION_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
podx run --show "The Podcast" --date 2024-10-02 --align --diarize --deepcast --notion --workdir work/

# Using RSS URL (for private/unlisted podcasts)
podx run --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-02 --workdir work/

# Using smart workdir for organized output (automatic)
podx run --show "The Podcast" --date 2024-02-02

# Advanced usage with content replacement and cleanup
podx run --show "The Podcast" --date 2024-10-02 --align --diarize --deepcast --notion \
  --append-content --clean --no-keep-audio --workdir work/

# Minimal upload with aggressive cleanup
podx run --show "The Podcast" --date 2024-10-02 --notion --clean --no-keep-audio --workdir work/

# Export with smart file updates (only overwrite if changed)
podx-export --formats txt,srt --output-dir work --replace

# Notion upload with cover image and content replacement
podx-notion --input work/brief.json --meta work/latest.json \
  --db "$NOTION_DB_ID" --append-content --cover-image
```

### AI-powered analysis with deepcast:

```bash
# Fast pass → deepcast (no alignment/diarization)
podx-fetch --show "The Podcast" --date 2024-10-02 \
| podx-transcode --to wav16 --outdir work \
| podx-transcribe \
| tee work/base.json \
| podx-deepcast --output work/brief.json

# With alignment & diarization → deepcast
cat work/base.json \
| podx-align --audio "$(jq -r .audio_path work/base.json)" \
| tee work/aligned.json \
| podx-diarize --audio "$(jq -r .audio_path work/base.json)" \
| tee work/diar.json \
| podx-deepcast --output work/brief.json
```

### Complete workflow:

```bash
# Run everything and then deepcast
podx run --show "The Podcast" --date 2024-10-02 --align --diarize --workdir work/ \
--model small.en --compute int8

# Then deepcast the final artifact
podx-deepcast --input work/latest.json --output work/brief.json
```

## Notes & tweaks

- **`direnv`**: `.envrc` auto-creates `.venv` and loads `.env`. Run `direnv allow` after editing `.envrc`.
- **Global install**: `pipx install -e .` makes `podx-*` commands available from anywhere.
- **Local install**: `pip install -e .` for development (requires virtual environment).
- **Optional deps**: Keep `WhisperX` and `llm` optional to keep base install light.
- **Testing**: `pip install -e .[dev] && pytest -q`
- **Notion integration**: Use `podx-notion` to upload Deepcast output to Notion as formatted pages.

### Deepcast Configuration

- **Models**: Default is `OPENAI_MODEL` env (e.g., `gpt-4.1-mini`). Override with `--model`.
- **Big episodes**: Increase `--chunk-chars` if you have a high-context model; otherwise keep ~24k chars.
- **Determinism**: Keep temperature low (0.1-0.3) for consistent outlines.
- **Timestamps**: If you skip alignment/diarization, you still have coarse segment start/end; it will use them. If your base JSON lacks start/end, timecodes are omitted.

### How deepcast adapts automatically

- **Base transcript (no speakers)**: Quotes contain text only (timecodes omitted if no start/end).
- **Aligned (timecodes available)**: Quotes include `[HH:MM:SS]`.
- **Diarized (speakers present)**: Quotes include both `[HH:MM:SS] Speaker: "..."`.

## Notion Integration

The `podx-notion` tool takes Deepcast output and creates beautifully formatted Notion pages.

### Setup

1. **Install Notion dependencies:**

   ```bash
   pip install -e ".[notion]"
   ```

2. **Configure environment variables in `.env`:**

   ```bash
   NOTION_TOKEN=secret_xxx                    # Your Notion integration token
   NOTION_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Target database ID
   NOTION_TITLE_PROP=Name                     # Title property name (default: "Name")
   NOTION_DATE_PROP=Date                      # Date property name (default: "Date")
   ```

3. **Create a Notion integration:**
   - Go to [notion.so/my-integrations](https://notion.so/my-integrations)
   - Create a new integration
   - Copy the "Internal Integration Token" to `NOTION_TOKEN`
   - Share your target database with the integration
   - Copy the database ID from the URL to `NOTION_DB_ID`

### Usage

#### After Deepcast (aligned/diarized optional):

```bash
# assumes work/brief.md (+ optional brief.json) already exist
podx-notion \
  --markdown work/brief.md \
  --json work/brief.json \
  --meta work/latest.json \
  --db "$NOTION_DB_ID"
```

This will:

- **Upsert** a Notion page using title from `--title` or `--meta` and date
- Convert Markdown to rich Notion blocks (headings, lists, quotes, code, paragraphs)
- If `brief.json` is provided, map top 3 key points to a `Tags` multi-select property
- Use `--dry-run` to preview the payload without writing to Notion

#### Full pipeline in one line:

```bash
podx run --show "The Podcast" --date 2024-10-02 --align --diarize --workdir work/ \
&& podx-deepcast --input work/latest.json --output work/brief.json \
&& podx-notion --input work/brief.json --meta work/latest.json --db "$NOTION_DB_ID"
```

#### Justfile helpers:

```bash
just notion-dry    # Preview what would be uploaded
just notion        # Upload to Notion
just orchestrate   # Run full pipeline with deepcast (no Notion)
just publish       # Run complete pipeline including Notion upload
```

### Notion Configuration

- **Property names**: If your database uses different property names, set `NOTION_TITLE_PROP` and `NOTION_DATE_PROP` in `.env`, or pass `--title-prop` and `--date-prop`
- **Content management**: Use `--append-content` to append to existing page content instead of replacing (default: replace)
- **Cover images**: Use `--cover-image` to automatically set podcast artwork as the page cover (requires `image_url` in metadata)
- **More properties**: Map fields from `brief.json` to Notion properties (numeric "Episode #", status, relations) in the `props_extra` section
- **Inline formatting**: Block-level parsing for robustness. Can be extended to support bold/italic/links if needed

## Orchestrator Behavior

The `podx run` command provides a unified interface to the entire pipeline with intelligent defaults and selective execution:

### How it works

- **Selective execution**: Only runs steps when their flags are set or required downstream
- **Independent toggles**: `--align`, `--diarize`, `--deepcast`, `--notion` are independent
- **Verbose output**: `--verbose` streams interstitial JSON and prints progress banners
- **Intermediate saving**: Saves all intermediates to `--workdir` for inspection/reuse

### Output files (persisted in `--workdir`)

- **Core pipeline**: `episode-meta.json`, `audio-meta.json`, `transcript.json`, `aligned-transcript.json`, `diarized-transcript.json`, `latest.json`, `transcript.txt`, `transcript.srt`
- **Deepcast output**: `deepcast-brief.json` (when `--deepcast` is used)
- **Notion response**: `notion.out.json` (when `--notion` is used)

### Fallback behavior

- **Notion without Deepcast**: If `--notion` is used without `--deepcast`, it falls back to using `latest.txt` for upload
- **Smart file detection**: Automatically detects the best available input files for each step

### Advanced features

- **RSS URL support**: Use `--rss-url` instead of `--show` for private, unlisted, or custom podcast feeds
- **Smart workdir**: Automatically generates organized directories like `Radio_Lab/2024-02-02/` based on show name and date
- **Content replacement**: Use `--append-content` to append to existing Notion page content instead of replacing (default: replace)
- **Cleanup management**: Use `--clean` to remove intermediate files after successful completion (default: keep all files)
- **Audio preservation**: Use `--no-keep-audio` to delete audio files when cleaning (default: keep audio)
- **Smart file updates**: Use `--replace` with `podx-export` to only overwrite files when content has changed
- **Export formats**: Use `--formats txt,srt,vtt,md` with `podx-export` to specify output formats (default: txt,srt)
- **Standardized I/O**: All utilities support `-i`/`--input` and `-o`/`--output` flags for consistent file handling
- **Cover images**: Use `--cover-image` with `podx-notion` to automatically set podcast artwork as the page cover

### RSS URL Usage

For podcasts that aren't publicly listed or when you have a direct RSS feed URL:

```bash
# Direct RSS feed usage
podx-fetch --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-02

# With orchestrator
podx run --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-02 --workdir work/

# Full pipeline with RSS URL
podx run --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-02 \
  --align --diarize --deepcast --notion --workdir work/
```

**Benefits of RSS URL:**

- Works with private or unlisted podcasts
- No dependency on iTunes/Apple Podcasts search
- Direct access to custom or specialized feeds
- Automatic show name extraction from feed metadata
- Automatic artwork extraction for Notion cover images

### Smart Workdir Usage

Podx automatically generates organized work directories based on show name and episode date:

```bash
# Smart workdir: "The Podcast/2024-10-02/" (automatic)
podx-fetch --show "The Podcast" --date 2024-02-02

# With orchestrator (smart workdir automatic)
podx run --show "The Podcast" --date 2024-02-02

# Full pipeline with smart workdir (automatic)
podx run --show "The Podcast" --date 2024-02-02 \
  --align --diarize --deepcast --notion

# Override with custom directory
podx run --show "The Podcast" --date 2024-02-02 --workdir work/

# Unknown show: "Unknown Show/2024-10-02/"
podx run --rss-url "https://example.com/feed.xml"
```

**Benefits of Smart Workdir:**

- Organized file structure: `"The Podcast/2024-10-02/"` (with spaces)
- Automatic sanitization of show names for filesystem compatibility
- Consistent date formatting (YYYY-MM-DD)
- No need to manually specify work directories
- Perfect for batch processing multiple episodes
- Override capability with `--outdir`/`--workdir` when needed
- Intuitive piping: `podx-transcode` automatically uses the same directory as source audio

## Project Structure

```
podx/
├── podx/                    # Main package
│   ├── __init__.py
│   ├── cli_shared.py        # Shared CLI utilities
│   ├── io.py               # JSON I/O helpers
│   ├── schemas.py          # Data type definitions
│   ├── fetch.py            # Podcast fetching
│   ├── transcode.py        # Audio transcoding
│   ├── transcribe.py       # Speech-to-text
│   ├── align.py            # Word-level alignment
│   ├── diarize.py          # Speaker diarization
│   ├── export.py           # Format exporters
│   ├── deepcast.py         # AI-powered analysis
│   ├── notion.py           # Notion page uploader
│   └── orchestrate.py      # Convenience wrapper
├── tests/                  # Test suite
├── pyproject.toml          # Package configuration
├── .envrc                  # Direnv configuration
├── .env.example            # Environment template
└── README.md
```

## Requirements

- macOS (tested on Apple Silicon MBP, Python 3.9+)
- [ffmpeg](https://ffmpeg.org) (`brew install ffmpeg`)
- Python 3.9+
- direnv (optional, recommended)

## Output Formats

Each stage emits **JSON** to stdout:

- `fetch` → `{ show, episode_title, episode_published, audio_path }`
- `transcode` → `{ audio_path, format, sample_rate, channels }`
- `transcribe` → `{ text, segments: [...] }`
- `align` → transcript + word-level timestamps
- `diarize` → transcript + speaker labels
- `export` → SRT/VTT/TXT/MD files
- `deepcast` → AI-generated Markdown brief + structured JSON
