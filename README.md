# podx

Composable podcast tooling (Unix-style):

- `podx-fetch`: Find & download an episode by show/date/title
- `podx-transcode`: `ffmpeg` to `wav` (16k mono) / `mp3` / `aac`
- `podx-transcribe`: `faster-whisper` (fast pass)
- `podx-align`: `WhisperX` alignment (word-level timings)
- `podx-diarize`: `WhisperX` diarization (speaker labels)
- `podx-export`: Write `SRT`/`VTT`/`TXT`/`MD`
- `podx-deepcast`: AI-powered transcript analysis and summarization
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
```

## Quick start

### Unix-style pipeline (JSON on stdout/stdin):

```bash
podx-fetch --show "Radiolab" --date 2024-10-02 \
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
podx run --show "Radiolab" --date 2024-10-02 --align --diarize --workdir work/ \
--model small.en --compute int8
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
- **Your Notion uploader**: Keep as separate console script and chain after `podx-deepcast`.

### Deepcast Configuration

- **Models**: Default is `OPENAI_MODEL` env (e.g., `gpt-4o-mini`). Override with `--model`.
- **Big episodes**: Increase `--chunk-chars` if you have a high-context model; otherwise keep ~24k chars.
- **Determinism**: Keep temperature low (0.1-0.3) for consistent outlines.
- **Timestamps**: If you skip alignment/diarization, you still have coarse segment start/end; it will use them. If your base JSON lacks start/end, timecodes are omitted.

### How deepcast adapts automatically

- **Base transcript (no speakers)**: Quotes contain text only (timecodes omitted if no start/end).
- **Aligned (timecodes available)**: Quotes include `[HH:MM:SS]`.
- **Diarized (speakers present)**: Quotes include both `[HH:MM:SS] Speaker: "..."`.

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
