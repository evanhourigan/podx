# Migrating to PodX v3.0

This guide helps you migrate from PodX v2.x to v3.0.

## Breaking Changes

### CLI Command Structure

**All `podx-verb` commands are now `podx verb` subcommands.**

This change improves discoverability, reduces namespace pollution, and aligns with modern CLI design patterns (like `git`, `docker`, `kubectl`).

## Migration Mapping

### Core Commands

| v2.x Command | v3.0 Command |
|---|---|
| `podx-run` | `podx run` |
| `podx-transcribe` | `podx transcribe` |
| `podx-diarize` | `podx diarize` |
| `podx-deepcast` | `podx deepcast` |
| `podx-export` | `podx export` |
| `podx-config` | `podx config` |
| `podx-fetch` | `podx fetch` |
| `podx-transcode` | `podx transcode` |
| `podx-preprocess` | `podx preprocess` |
| `podx-align` | `podx align` |
| `podx-notion` | `podx notion` |

### Batch Commands

| v2.x Command | v3.0 Command |
|---|---|
| `podx-batch-transcribe` | `podx batch transcribe` |
| `podx-batch-pipeline` | `podx batch pipeline` |
| `podx-batch-status` | `podx batch status` |

### Utility Commands

| v2.x Command | v3.0 Command |
|---|---|
| `podx-models` | `podx models` |
| `podx-estimate` | `podx estimate` |
| `podx-init` | `podx init` |
| `podx-search` | `podx search` |
| `podx-analyze` | `podx analyze` |

### Quick Aliases (REMOVED)

The quick workflow aliases have been replaced with the `--profile` flag:

| v2.x Alias | v3.0 Equivalent |
|---|---|
| `podx-quick` | `podx run --profile quick` |
| `podx-full` | `podx run --profile standard` |
| `podx-hq` | `podx run --profile high-quality` |

## Automated Migration

### Shell Scripts

Update your scripts with find & replace:

```bash
# Backup first!
cp script.sh script.sh.backup

# Update commands (macOS)
sed -i '' 's/podx-run/podx run/g' script.sh
sed -i '' 's/podx-transcribe/podx transcribe/g' script.sh
sed -i '' 's/podx-diarize/podx diarize/g' script.sh
sed -i '' 's/podx-deepcast/podx deepcast/g' script.sh
sed -i '' 's/podx-export/podx export/g' script.sh
sed -i '' 's/podx-batch-transcribe/podx batch transcribe/g' script.sh
sed -i '' 's/podx-batch-pipeline/podx batch pipeline/g' script.sh
sed -i '' 's/podx-batch-status/podx batch status/g' script.sh
sed -i '' 's/podx-search/podx search/g' script.sh
sed -i '' 's/podx-analyze/podx analyze/g' script.sh

# Update quick aliases
sed -i '' 's/podx-quick/podx run --profile quick/g' script.sh
sed -i '' 's/podx-full/podx run --profile standard/g' script.sh
sed -i '' 's/podx-hq/podx run --profile high-quality/g' script.sh
```

On Linux, remove the `''` after `-i`:

```bash
sed -i 's/podx-run/podx run/g' script.sh
```

### Multiple Files

```bash
# Update all shell scripts in directory
find . -name "*.sh" -type f -exec sed -i '' 's/podx-run/podx run/g' {} +
find . -name "*.sh" -type f -exec sed -i '' 's/podx-transcribe/podx transcribe/g' {} +
```

### CI/CD Pipelines

**GitHub Actions:**
```yaml
# Before
- run: podx-transcribe episode.mp3

# After
- run: podx transcribe episode.mp3
```

**GitLab CI:**
```yaml
# Before
script:
  - podx-quick --show "My Podcast"

# After
script:
  - podx run --profile quick --show "My Podcast"
```

## What Hasn't Changed

### Configuration Files

All configuration files remain the same:
- `~/.config/podx/config.yaml`
- `~/.config/podx/profiles.yaml`
- Working directory structure
- Output file formats

### Python API

The Python API is unchanged:

```python
# Still works in v3.0
from podx.api import PodxClient

client = PodxClient()
result = client.transcribe("episode.mp3")
```

### Command Options

All command-line options and flags remain the same. Only the command names have changed.

```bash
# v2.x
podx-transcribe episode.mp3 --model large-v3-turbo --language en

# v3.0
podx transcribe episode.mp3 --model large-v3-turbo --language en
#       ^^^^^^^^^ only this changed
```

## New in v3.0

### Web API Server

v3.0 introduces a production-grade REST API server:

```bash
# Start server
podx server start

# Access API documentation
open http://localhost:8000/docs
```

See the [README](README.md#-web-api-server-v30) for full documentation.

### Server Commands

| Command | Description |
|---|---|
| `podx server start` | Start the API server |
| `podx server stop` | Stop the running server |
| `podx server status` | Check server status |
| `podx server logs` | View server logs |

## Testing Your Migration

```bash
# Test individual commands
podx run --help
podx transcribe --help
podx server --help

# Test workflows
podx run --show "Test Podcast" --date 2024-01-01 --dry-run

# Verify configuration
podx models --status
podx config show
```

## Getting Help

- [CHANGELOG](CHANGELOG.md) - Detailed changes
- [README](README.md) - Updated examples
- `podx --help` - Command reference
- [GitHub Issues](https://github.com/evanhourigan/podx/issues)

## Rollback

```bash
# Uninstall v3.0
pip uninstall podx

# Reinstall v2.x
pip install podx==2.1.0
```
