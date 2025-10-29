# Manifest System

The PodX manifest system provides comprehensive episode and pipeline tracking stored in `.podx/manifest.json`. It enables progress tracking during long operations, resumable pipeline sessions, and maintains a history of processing stages.

## Overview

The manifest tracks:
- **Episodes**: Each processed podcast episode with stage completion status
- **Stages**: Individual pipeline steps (fetch, transcribe, diarize, etc.) with progress, timestamps, models used, and output files
- **Sessions**: Multi-stage pipeline runs with current progress and resumability

## Structure

```json
{
  "version": "2.0.0",
  "episodes": [
    {
      "show": "Lenny's Podcast",
      "date": "2024-03-15",
      "title": "Building products people love",
      "path": "Lenny's Podcast/2024-03-15",
      "stages": {
        "transcribe": {
          "completed": true,
          "started_at": "2024-03-15T10:00:00",
          "completed_at": "2024-03-15T10:05:30",
          "progress": 1.0,
          "status": "Completed",
          "model": "base",
          "files": ["transcript-base.json"],
          "metadata": {}
        },
        "diarize": {
          "completed": false,
          "started_at": "2024-03-15T10:06:00",
          "progress": 0.45,
          "status": "Processing segment 450/1000",
          "model": "pyannote/speaker-diarization",
          "files": [],
          "metadata": {}
        }
      },
      "created_at": "2024-03-15T09:00:00",
      "updated_at": "2024-03-15T10:06:15"
    }
  ],
  "sessions": [
    {
      "id": "session-a1b2c3d4",
      "episode_show": "Lenny's Podcast",
      "episode_date": "2024-03-15",
      "pipeline": ["transcribe", "diarize", "deepcast"],
      "current_stage": "diarize",
      "current_stage_index": 1,
      "status": "running",
      "started_at": "2024-03-15T10:00:00",
      "completed_at": null,
      "error": null
    }
  ]
}
```

## Using the Manifest in Code

### Basic Episode Tracking

```python
from podx import ManifestManager

# Initialize manager (uses current directory by default)
manager = ManifestManager()

# Add or update an episode
episode = manager.add_or_update_episode(
    show="Lenny's Podcast",
    date="2024-03-15",
    title="Building products people love",
    path="Lenny's Podcast/2024-03-15"
)

# Start a stage
manager.start_stage(
    show="Lenny's Podcast",
    date="2024-03-15",
    stage="transcribe",
    model="base",
    metadata={"language": "en"}
)

# Update progress (0.0 to 1.0)
manager.update_stage_progress(
    show="Lenny's Podcast",
    date="2024-03-15",
    stage="transcribe",
    progress=0.5,
    status="Processing segment 500/1000"
)

# Complete a stage
manager.complete_stage(
    show="Lenny's Podcast",
    date="2024-03-15",
    stage="transcribe",
    files=["transcript-base.json"],
    metadata={"duration": 3600, "segments": 1000}
)

# Mark stage as failed
manager.fail_stage(
    show="Lenny's Podcast",
    date="2024-03-15",
    stage="transcribe",
    error="Out of memory"
)
```

### Pipeline Sessions

Sessions track multi-stage pipeline runs and enable resumability:

```python
from podx import ManifestManager

manager = ManifestManager()

# Create a pipeline session
session = manager.create_session(
    show="Lenny's Podcast",
    date="2024-03-15",
    pipeline=["transcribe", "diarize", "deepcast", "export"]
)
print(f"Created session: {session.id}")

# Update current stage
manager.update_session_stage(
    session_id=session.id,
    stage_index=1,  # Now on "diarize"
    status="running"
)

# Complete session
manager.complete_session(session.id)

# Or mark as failed
manager.fail_session(session.id, error="Diarization failed")

# Get incomplete sessions (for resuming)
incomplete = manager.get_incomplete_sessions()
for session in incomplete:
    print(f"Resume session {session.id}: {session.current_stage}")
```

### Querying Episodes

```python
from podx import ManifestManager

manager = ManifestManager()

# Get all episodes
all_episodes = manager.get_all_episodes()

# Get specific episode
episode = manager.get_episode(
    manifest=manager.load(),
    show="Lenny's Podcast",
    date="2024-03-15"
)

# Get episodes with completed diarization
diarized = manager.get_episodes_by_stage("diarize", completed=True)

# Get episodes with incomplete transcription
pending_transcribe = manager.get_episodes_by_stage("transcribe", completed=False)
```

### Filesystem Sync

The manifest can auto-detect completed stages by scanning the filesystem:

```python
from podx import ManifestManager

manager = ManifestManager()

# Scan filesystem and update manifest
manifest = manager.scan_and_sync()

# This detects stages based on file presence:
# - fetch: episode-meta.json
# - transcribe: transcript*.json
# - diarize: diarized.json
# - deepcast: deepcast*.json
# - export: *.txt, *.srt, *.vtt
# - notion: notion.out.json
```

## Stage Lifecycle

Each stage follows this lifecycle:

1. **Not Started**: Stage doesn't exist in episode's `stages` dict
2. **Started**: `start_stage()` creates entry with `progress=0.0`, `completed=False`
3. **In Progress**: `update_stage_progress()` updates `progress` (0.0-1.0) and `status`
4. **Completed**: `complete_stage()` sets `completed=True`, `progress=1.0`, adds `files`
5. **Failed**: `fail_stage()` sets `error` and `status` to indicate failure

## Progress Tracking

Progress is tracked as a float from 0.0 to 1.0:

```python
# 0.0 = just started
manager.update_stage_progress(show, date, stage, 0.0, "Starting...")

# 0.5 = halfway
manager.update_stage_progress(show, date, stage, 0.5, "Processing segment 500/1000")

# 1.0 = complete
manager.update_stage_progress(show, date, stage, 1.0, "Finalizing...")
```

Status messages are human-readable and shown in Studio UI.

## Integration with CLI Commands

CLI commands can optionally write to the manifest:

```python
# In your CLI command
from podx import ManifestManager, TranscriptionEngine

manager = ManifestManager()

# Start stage
manager.start_stage(
    show=show,
    date=date,
    stage="transcribe",
    model=model,
)

try:
    # Run transcription
    engine = TranscriptionEngine(model=model)
    result = engine.transcribe(audio_file)

    # Complete stage
    manager.complete_stage(
        show=show,
        date=date,
        stage="transcribe",
        files=["transcript-base.json"],
        metadata={"duration": result["duration"]}
    )
except Exception as e:
    # Mark as failed
    manager.fail_stage(show, date, "transcribe", str(e))
    raise
```

## Integration with Studio

PodX Studio automatically:
- Loads manifest on startup
- Displays stage badges in episode browser:
  - `✓trans` = transcribe completed
  - `⏳diar(45%)` = diarize in progress at 45%
  - `○deep` = deepcast not started
- Shows incomplete sessions with resume hints
- Syncs filesystem on refresh

## Best Practices

1. **Always use ManifestManager**: Don't manually edit manifest.json
2. **Track long operations**: Use progress updates for operations over 10 seconds
3. **Include metadata**: Store useful info like model names, durations, settings
4. **Handle failures**: Always use try/except and `fail_stage()` on errors
5. **Create sessions for pipelines**: Use sessions when running multiple stages
6. **Sync regularly**: Call `scan_and_sync()` when browsing episodes

## Example: Full Pipeline with Tracking

```python
from podx import (
    ManifestManager,
    TranscriptionEngine,
    DiarizationEngine,
    ExportEngine,
)

# Setup
manager = ManifestManager()
show = "Lenny's Podcast"
date = "2024-03-15"

# Create pipeline session
session = manager.create_session(
    show=show,
    date=date,
    pipeline=["transcribe", "diarize", "export"]
)

try:
    # Stage 1: Transcribe
    manager.start_stage(show, date, "transcribe", model="base")
    engine = TranscriptionEngine(model="base")
    transcript = engine.transcribe("audio.wav")
    manager.complete_stage(
        show, date, "transcribe",
        files=["transcript.json"],
        metadata={"segments": len(transcript["segments"])}
    )
    manager.update_session_stage(session.id, 1, "running")

    # Stage 2: Diarize
    manager.start_stage(show, date, "diarize")
    diarize_engine = DiarizationEngine()
    diarized = diarize_engine.diarize(transcript, "audio.wav")
    manager.complete_stage(
        show, date, "diarize",
        files=["diarized.json"],
        metadata={"speakers": diarized["num_speakers"]}
    )
    manager.update_session_stage(session.id, 2, "running")

    # Stage 3: Export
    manager.start_stage(show, date, "export")
    export_engine = ExportEngine()
    export_engine.export_txt(diarized, "output.txt")
    export_engine.export_srt(diarized, "output.srt")
    manager.complete_stage(
        show, date, "export",
        files=["output.txt", "output.srt"]
    )

    # Complete session
    manager.complete_session(session.id)

except Exception as e:
    # Mark session as failed
    manager.fail_session(session.id, str(e))
    raise
```

## Related Documentation

- [Core API](CORE_API.md) - Engine classes and functions
- [Processing Pipeline](PROCESSING_PIPELINE.md) - Pipeline stages and flow
- [API Examples](API_EXAMPLES.md) - More code examples
