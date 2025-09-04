# podx

Composable podcast tooling (Unix-style):

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

- `podx-fetch`: Find & download an episode by show/date/title or RSS URL
- `podx-transcode`: `ffmpeg` to `wav` (16k mono) / `mp3` / `aac`
- `podx-transcribe`: `faster-whisper` (fast pass)
- `podx-align`: `WhisperX` alignment (word-level timings)
- `podx-diarize`: `WhisperX` diarization (speaker labels)
- `podx-export`: Write `SRT`/`VTT`/`TXT`/`MD`
- `podx-deepcast`: AI-powered transcript analysis and summarization
- `podx-notion`: Upload Deepcast output to Notion as formatted pages
- `podx run`: Convenience orchestrator that chains steps

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

# install editable
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

### Unix-style pipeline (JSON on stdout/stdin):

```bash
# Using show name (iTunes search)
podx-fetch --show "Radiolab" --date 2024-10-02 \
| podx-transcode --to wav16 --outdir work \
| podx-transcribe \
| tee work/base.json \
| podx-export --txt work/base.txt --srt work/base.srt

# Using RSS URL (for private/unlisted podcasts)
podx-fetch --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-02 \
| podx-transcode --to wav16 --outdir work \
| podx-transcribe \
| tee work/base.json \
| podx-export --txt work/base.txt --srt work/base.srt
```

### Add alignment/diarization only when needed:

```bash
cat work/base.json \
| podx-align --audio "$(jq -r .audio_path work/base.json)" \
| tee work/aligned.json \
| podx-diarize --audio "$(jq -r .audio_path work/base.json)" \
| tee work/diar.json \
| podx-export --srt work/episode.srt --vtt work/episode.vtt --txt work/episode.txt
```

### One-shot convenience:

```bash
# Using show name (iTunes search)
# Minimal happy-path (fast pass; fetch → transcode → transcribe → export)
podx run --show "Radiolab" --date 2024-10-02 --workdir work/

# Add alignment & diarization
podx run --show "Radiolab" --date 2024-10-02 --align --diarize --workdir work/

# Add Deepcast (AI analysis)
export OPENAI_API_KEY=sk-...
podx run --show "Radiolab" --date 2024-10-02 --align --diarize --deepcast --workdir work/

# Add Notion upload (complete pipeline)
export NOTION_TOKEN=secret_xxx
export NOTION_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
podx run --show "Radiolab" --date 2024-10-02 --align --diarize --deepcast --notion --workdir work/

# Using RSS URL (for private/unlisted podcasts)
podx run --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-02 --workdir work/

# Using auto-workdir for organized output
podx run --show "Radio Lab" --date 2024-02-02 --auto-workdir

# Advanced usage with content replacement and cleanup
podx run --show "Radiolab" --date 2024-10-02 --align --diarize --deepcast --notion \
  --replace-content --clean --keep-audio --workdir work/

# Minimal upload with aggressive cleanup
podx run --show "Radiolab" --date 2024-10-02 --notion --clean --no-keep-audio --workdir work/

# Export with smart file updates (only overwrite if changed)
podx-export --srt work/episode.srt --txt work/episode.txt --replace

# Notion upload with cover image and content replacement
podx-notion --markdown work/brief.md --json work/brief.json --meta work/latest.json \
  --db "$NOTION_DB_ID" --replace-content --cover-image
```

### AI-powered analysis with deepcast:

```bash
# Fast pass → deepcast (no alignment/diarization)
podx-fetch --show "Radiolab" --date 2024-10-02 \
| podx-transcode --to wav16 --outdir work \
| podx-transcribe \
| tee work/base.json \
| podx-deepcast --md-out work/brief.md --json-out work/brief.json

# With alignment & diarization → deepcast
cat work/base.json \
| podx-align --audio "$(jq -r .audio_path work/base.json)" \
| tee work/aligned.json \
| podx-diarize --audio "$(jq -r .audio_path work/base.json)" \
| tee work/diar.json \
| podx-deepcast --md-out work/brief.md --json-out work/brief.json
```

### Complete workflow:

```bash
# Run everything and then deepcast
podx run --show "Radiolab" --date 2024-10-02 --align --diarize --workdir work/ \
--model small.en --compute int8

# Then deepcast the final artifact
podx-deepcast --in work/latest.json --md-out work/brief.md --json-out work/brief.json
```

## Notes & tweaks

- **`direnv`**: `.envrc` auto-creates `.venv` and loads `.env`. Run `direnv allow` after editing `.envrc`.
- **Editable install**: `pip install -e .` lets you run `podx-*` from any folder.
- **Optional deps**: Keep `WhisperX` and `llm` optional to keep base install light.
- **Testing**: `pip install -e .[dev] && pytest -q`
- **Notion integration**: Use `podx-notion` to upload Deepcast output to Notion as formatted pages.

### Deepcast Configuration

- **Models**: Default is `OPENAI_MODEL` env (e.g., `gpt-4o-mini`). Override with `--model`.
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
podx run --show "Radiolab" --date 2024-10-02 --align --diarize --workdir work/ \
&& podx-deepcast --in work/latest.json --md-out work/brief.md --json-out work/brief.json \
&& podx-notion --markdown work/brief.md --json work/brief.json --meta work/latest.json --db "$NOTION_DB_ID"
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
- **Content management**: Use `--replace-content` to replace existing page content instead of appending
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

- **Core pipeline**: `meta.json`, `audio.json`, `base.json`, `aligned.json`, `diar.json`, `latest.json`, `latest.txt`, `latest.srt`
- **Deepcast output**: `brief.md`, `brief.json` (when `--deepcast` is used)
- **Notion response**: `notion.out.json` (when `--notion` is used)

### Fallback behavior

- **Notion without Deepcast**: If `--notion` is used without `--deepcast`, it falls back to using `latest.txt` for upload
- **Smart file detection**: Automatically detects the best available input files for each step

### Advanced features

- **RSS URL support**: Use `--rss-url` instead of `--show` for private, unlisted, or custom podcast feeds
- **Auto-workdir**: Use `--auto-workdir` to automatically generate organized directories like `Radio_Lab/2024-02-02/`
- **Content replacement**: Use `--replace-content` to replace existing Notion page content instead of appending
- **Cleanup management**: Use `--clean` to remove intermediate files after successful completion
- **Audio preservation**: Use `--keep-audio` (default) to preserve downloaded/transcoded audio files when cleaning
- **Smart file updates**: Use `--replace` with `podx-export` to only overwrite files when content has changed
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

### Auto-Workdir Usage

Automatically generate organized work directories based on show name and episode date:

```bash
# Auto-generate workdir: Radio_Lab/2024-02-02/
podx-fetch --show "Radio Lab" --date 2024-02-02 --auto-workdir

# With orchestrator
podx run --show "Radio Lab" --date 2024-02-02 --auto-workdir

# Full pipeline with auto-workdir
podx run --show "Radio Lab" --date 2024-02-02 --auto-workdir \
  --align --diarize --deepcast --notion
```

**Benefits of Auto-Workdir:**

- Organized file structure: `Show_Name/YYYY-MM-DD/`
- Automatic sanitization of show names for filesystem compatibility
- Consistent date formatting (YYYY-MM-DD)
- No need to manually specify work directories
- Perfect for batch processing multiple episodes

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
