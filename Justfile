# Justfile for podx project automation
# Install with: brew install just

set shell := ["bash", "-cu"]

# Bootstrap & Env
init:
    #!/usr/bin/env bash
    brew install direnv ffmpeg jq || true
    if ! command -v direnv &> /dev/null; then
        echo "Please install direnv: brew install direnv"
        echo "Then add to ~/.zshrc: eval \"\$(direnv hook zsh)\""
        exit 1
    fi
    cp -n .env.example .env || true
    direnv allow
    pip install -U pip

# Recreate venv if needed
venv:
    #!/usr/bin/env bash
    rm -rf .venv
    python3 -m venv .venv
    direnv allow

# Install project (editable)
install:
    #!/usr/bin/env bash
    pip install -e ".[asr]"
    echo "Tip: add WhisperX support with: pip install -e \".[whisperx]\""

# Install with dev dependencies
dev-install:
    #!/usr/bin/env bash
    pip install -e ".[asr,dev]"

# Quality checks
lint:
    ruff check podx tests

fmt:
    ruff check --fix podx tests

typecheck:
    mypy podx

test:
    pytest -q

cov:
    pytest --cov=podx --cov-report=term-missing

# Pipeline examples
fetch show="Radiolab" date="2024-10-02":
    podx-fetch --show "{{show}}" --date {{date}} > work/meta.json

fast:
    #!/usr/bin/env bash
    mkdir -p work
    podx-fetch --show "Radiolab" --date 2024-10-02 \
    | podx-transcode --to wav16 --outdir work \
    | podx-transcribe \
    | tee work/base.json \
    | podx-export --txt work/base.txt --srt work/base.srt

full:
    podx run --show "Radiolab" --date 2024-10-02 --align --diarize --workdir work/ --model small.en --compute int8

# Hooks
pre-commit-install:
    pre-commit install

# Notion helpers
notion-dry:
    podx-notion --markdown work/brief.md --json work/brief.json --meta work/latest.json --db "$NOTION_DB_ID" --dry-run

notion:
    podx-notion --markdown work/brief.md --json work/brief.json --meta work/latest.json --db "$NOTION_DB_ID"

# Orchestration helpers
orchestrate:
    podx run --show "Radiolab" --date 2024-10-02 --align --deepcast --workdir work/ -v

publish:
    podx run --show "Radiolab" --date 2024-10-02 --align --deepcast --notion --workdir work/ -v

# Cleanup
clean:
    #!/usr/bin/env bash
    rm -rf .venv .direnv dist build *.egg-info work episodes **/__pycache__
