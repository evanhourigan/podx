# Migration Guide: v2.x → v3.0.0

This guide helps you migrate from PodX v2.x to v3.0.0.

## 🚨 Breaking Changes

### CLI Restructure: `podx-verb` → `podx verb`

**v3.0.0 unifies all commands under a single `podx` entry point.**

All standalone `podx-verb` commands have been removed. Use `podx <verb>` instead.

#### Command Mapping

| v2.x Command | v3.0 Command | Notes |
|--------------|--------------|-------|
| `podx-run` | `podx run` | Main pipeline orchestrator |
| `podx-transcribe` | `podx transcribe` | Transcription only |
| `podx-fetch` | `podx fetch` | Fetch episode metadata |
| `podx-transcode` | `podx transcode` | Audio format conversion |
| `podx-diarize` | `podx diarize` | Speaker diarization |
| `podx-preprocess` | `podx preprocess` | Transcript preprocessing |
| `podx-deepcast` | `podx deepcast` | AI analysis |
| `podx-export` | `podx export` | Export to formats |
| `podx-notion` | `podx notion` | Notion upload |
| `podx-models` | `podx models` | Model management |
| `podx-config` | `podx config` | Configuration |
| `podx-estimate` | `podx estimate` | Cost estimation |
| `podx-init` | `podx init` | Interactive setup |
| `podx-completion` | `podx completion` | Shell completion |
| `podx-analyze-audio` | `podx analyze-audio` | Audio quality analysis |
| `podx-quick` | `podx run --profile quick` | Fast transcription |
| `podx-full` | `podx run --profile standard` | Standard pipeline |
| `podx-hq` | `podx run --profile high-quality` | High-quality pipeline |

#### Batch Commands

| v2.x Command | v3.0 Command |
|--------------|--------------|
| `podx-batch-transcribe` | `podx batch transcribe` |
| `podx-batch-pipeline` | `podx batch pipeline` |
| `podx-batch-status` | `podx batch status` |

#### Search & Analysis

| v2.x Command | v3.0 Command |
|--------------|--------------|
| `podx-search` | `podx search <subcommand>` |
| - | `podx search index` |
| - | `podx search query` |
| - | `podx search list` |
| - | `podx search quotes` |
| - | `podx search stats` |
| `podx-analyze` | `podx analyze <subcommand>` |
| - | `podx analyze highlights` |
| - | `podx analyze quotes` |
| - | `podx analyze speakers` |
| - | `podx analyze topics` |

### Workflow Aliases Removed

The `podx-quick`, `podx-full`, and `podx-hq` commands have been replaced with **profiles**.

#### Before (v2.x):
```bash
podx-quick podcast.mp3
podx-full podcast.mp3
podx-hq podcast.mp3
```

#### After (v3.0):
```bash
podx run --profile quick --show "My Podcast"
podx run --profile standard --show "My Podcast"
podx run --profile high-quality --show "My Podcast"
```

#### Profile Settings

- **quick**: Fast processing (base model, no diarize/preprocess/deepcast)
- **standard**: Balanced quality (medium model, all features, gpt-4o-mini)
- **high-quality**: Best quality (large-v3, all features, gpt-4o)

## 📦 Installation

### Upgrade

```bash
pip install --upgrade podx
```

### Reinstall (Clean)

If you encounter issues, try a clean reinstall:

```bash
pip uninstall podx
pip install podx
```

## 🔧 Shell Scripts & Aliases

If you have shell scripts or aliases using the old commands, update them:

### Example: Update Shell Script

**Before:**
```bash
#!/bin/bash
podx-run --show "$1" --date "$2"
```

**After:**
```bash
#!/bin/bash
podx run --show "$1" --date "$2"
```

### Example: Update Bash Alias

**Before:**
```bash
alias pq='podx-quick'
alias pf='podx-full'
```

**After:**
```bash
alias pq='podx run --profile quick'
alias pf='podx run --profile standard'
alias phq='podx run --profile high-quality'
```

## 🧪 Testing Your Migration

After upgrading, verify everything works:

```bash
# Check version
podx --version

# Test help for main commands
podx --help
podx run --help
podx batch --help
podx search --help

# Test a simple command
podx models --status
podx estimate --help
```

## ✨ New Features in v3.0

While migrating, take advantage of these new features:

### 1. Configuration Profiles

Create and use custom profiles:

```bash
# Use built-in profiles
podx run --profile quick --show "My Podcast"

# Or configure defaults in ~/.podx/config.yaml
```

### 2. Unified CLI

All commands are now organized under a single entry point:

```bash
podx <command> [options]
```

### 3. Improved Help

Get help for any command or subcommand:

```bash
podx run --help
podx batch transcribe --help
podx search query --help
```

## 🆘 Troubleshooting

### Command Not Found

**Error:** `bash: podx-run: command not found`

**Solution:** Update to use `podx run` instead of `podx-run`.

### Old Commands Still Work

If old `podx-verb` commands still work, you may have an old version installed:

```bash
pip uninstall podx
pip install podx
which podx
```

### Shell Completion Broke

Reinstall shell completion after upgrading:

```bash
podx completion bash  # or zsh/fish
```

## 📚 Need Help?

- **Documentation:** See README.md and QUICKSTART.md
- **Issues:** https://github.com/evanhourigan/podx/issues
- **Changelog:** See CHANGELOG.md for full release notes

## 🎯 Quick Reference

### Most Common Commands

```bash
# Process an episode (interactive mode)
podx run --interactive

# Process with YouTube URL
podx run --youtube-url "https://youtube.com/watch?v=..."

# Process with RSS feed
podx run --show "Podcast Name" --date 2025-01-15

# Use a profile
podx run --profile quick --show "Podcast Name"

# Batch processing
podx batch transcribe --auto-detect
podx batch pipeline --show "Podcast Name" --since 2025-01-01

# Search transcripts
podx search index transcript.json
podx search query "machine learning"
podx search quotes

# Cost estimation
podx estimate audio.mp3
podx estimate --duration 3600 --model large-v3
```

---

**Happy migrating! 🚀**

If you encounter any issues not covered here, please open an issue on GitHub.
