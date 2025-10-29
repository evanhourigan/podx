# PodX Architecture Refactoring Plan

## Current State Analysis

### Problems
1. **Mixed Concerns**: CLI parsing, business logic, and UI code intermingled
2. **Hard to Test**: Can't unit test core logic without mocking UI components
3. **Hard to Extend**: Adding new interfaces requires duplicating logic
4. **Inconsistent UX**: Some commands use TUI, some don't, some partially
5. **Code Duplication**: Similar patterns repeated across commands

### What Works
- Core processing logic is solid
- Textual TUI components show great promise
- Pipeline orchestration architecture
- Rich styling and formatting

## Proposed Architecture

```
podx/
├── core/                     # Pure business logic (no UI, no CLI)
│   ├── __init__.py
│   ├── transcribe.py        # Transcription engine
│   ├── diarize.py           # Diarization and alignment
│   ├── preprocess.py        # Text preprocessing
│   ├── deepcast.py          # AI analysis
│   ├── orchestrate.py       # Pipeline orchestration
│   ├── fetch.py             # Episode fetching
│   ├── transcode.py         # Audio transcoding
│   └── models/              # Data models
│       ├── episode.py
│       ├── transcript.py
│       └── config.py
├── cli/                      # Traditional CLI (stdin/stdout only)
│   ├── __init__.py
│   ├── commands/
│   │   ├── transcribe.py    # Click command wrapper
│   │   ├── diarize.py
│   │   └── ...
│   └── main.py              # Entry point for `podx` command
├── studio/                   # Interactive TUI application
│   ├── __init__.py
│   ├── app.py               # Main PodX Studio app
│   ├── screens/             # Full-screen workflows
│   │   ├── home.py          # Dashboard/launcher
│   │   ├── transcribe.py    # Transcription workflow
│   │   ├── diarize.py       # Diarization workflow
│   │   ├── preprocess.py    # Preprocessing workflow
│   │   ├── pipeline.py      # Full pipeline workflow
│   │   └── browser.py       # Episode browser
│   ├── widgets/             # Reusable UI components
│   │   ├── episode_list.py
│   │   ├── model_selector.py
│   │   ├── progress_display.py
│   │   └── config_panel.py
│   ├── theme.py             # Unified styling/colors
│   └── main.py              # Entry point for `podx-studio` command
└── ui/                       # Legacy UI code (to be migrated/deprecated)
```

## Recommended Approach: "PodX Studio"

### Why a Unified Studio?
- **Single Entry Point**: One command for all interactive work
- **Consistent UX**: Uniform navigation, styling, keyboard shortcuts
- **Professional Feel**: Textual creates immersive experiences, not just "CLI with colors"
- **State Management**: Share context between workflows (e.g., select episode once, process multiple ways)
- **Discoverability**: Users explore features through navigation, not command-line flags

### Studio Concept

```
┌─ PodX Studio ─────────────────────────────────────────────┐
│  [Home] [Transcribe] [Diarize] [Pipeline] [Settings]      │
├────────────────────────────────────────────────────────────┤
│  HOME SCREEN                                               │
│  ┌─ Recent Episodes ────────┐  ┌─ Quick Actions ────────┐ │
│  │ • Lenny's Pod: AI enters │  │ ▶ New Project          │ │
│  │   2025-10-26             │  │ ▶ Import Episode       │ │
│  │ • Netflix Daily Joke     │  │ ▶ Run Pipeline         │ │
│  │   2025-10-25             │  │ ▶ Batch Process        │ │
│  └──────────────────────────┘  └────────────────────────┘ │
│                                                            │
│  ┌─ Processing Queue ─────────┐  ┌─ System Status ──────┐ │
│  │ ○ No active jobs           │  │ ✓ Models loaded      │ │
│  │                            │  │ ✓ GPU available       │ │
│  └────────────────────────────┘  └──────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### Navigation Flow

**Option 1: Tab-based (Recommended)**
- F1/Ctrl+1: Home dashboard
- F2/Ctrl+2: Transcribe workflow
- F3/Ctrl+3: Diarize workflow
- F4/Ctrl+4: Full Pipeline
- F5/Ctrl+5: Settings

**Option 2: Modal workflows**
- Home screen with workflow cards
- Click/Enter launches full-screen workflow
- Esc returns to home

## Migration Strategy

### Phase 1: Extract Core Logic (1-2 weeks)
**Goal**: Pure business logic with no UI dependencies

Tasks:
- [ ] Create `core/` module structure
- [ ] Extract `TranscriptionEngine` from `transcribe.py`
- [ ] Extract `DiarizationEngine` from `diarize.py`
- [ ] Extract `PipelineOrchestrator` from `orchestrate.py`
- [ ] Add progress callback interfaces
- [ ] Write unit tests for core modules
- [ ] Update existing CLI to use `core/`

**Success Criteria**:
```python
# Can test without any UI
from podx.core import TranscriptionEngine

engine = TranscriptionEngine("large-v3")
result = engine.transcribe("audio.mp3")
assert len(result.segments) > 0
```

### Phase 2: Build Studio Foundation (2-3 weeks)
**Goal**: Unified TUI application framework

Tasks:
- [ ] Create studio app structure
- [ ] Design home dashboard screen
- [ ] Implement unified theme/styling
- [ ] Create reusable widgets (episode list, progress bars, etc.)
- [ ] Set up screen navigation system
- [ ] Add keyboard shortcut system
- [ ] Implement settings/preferences

**Deliverable**: Empty studio shell with navigation

### Phase 3: Implement Workflows (2-3 weeks)
**Goal**: Feature-complete studio workflows

Tasks:
- [ ] Transcribe screen (episode select → model select → progress)
- [ ] Diarize screen (transcript select → progress)
- [ ] Preprocess screen (transcript select → config → progress)
- [ ] Full pipeline screen (config → execution)
- [ ] Progress tracking system
- [ ] Error handling and user feedback

**Deliverable**: Functional studio replacing `--interactive` flags

### Phase 4: CLI Refactoring (1 week)
**Goal**: Clean CLI using core modules

Tasks:
- [ ] Create thin wrappers in `cli/`
- [ ] Remove `--interactive` flags from CLI
- [ ] Update all commands to use `core/`
- [ ] Ensure backward compatibility
- [ ] Update documentation

**Deliverable**: `podx` for scripting, `podx studio` for interactive

### Phase 5: Polish & Release (1-2 weeks)
**Goal**: Production-ready 2.0 release

Tasks:
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Documentation and tutorials
- [ ] Migration guide for users
- [ ] Example workflows and recipes

## Command Structure

### Recommended: Subcommand Approach

```bash
# Traditional CLI (scriptable, stdin/stdout)
podx transcribe --audio audio.mp3 --model large-v3

podx diarize --input transcript.json --audio audio.mp3

echo '{"audio_path": "..."}' | podx transcribe | podx diarize

# Interactive Studio (immersive TUI)
podx studio                    # Launch dashboard
podx studio transcribe         # Jump directly to transcribe workflow
podx studio pipeline           # Jump to full pipeline workflow
```

**Benefits**:
- Clear separation of use cases
- `podx` remains familiar for CLI users
- `studio` is discoverable and explicit
- Can install studio separately if needed

**Alternative**: Separate executable `podx-studio`
- More explicit separation
- Could be packaged independently
- Slightly more typing

## Version & Tagging Strategy

### Current Situation
- `v2.0` tag exists but marks partially broken/experimental features
- Need clean versioning strategy for refactoring work

### Recommendation

**Remove `v2.0` tag**, use this strategy:

```
v1.9.x    - Current stable (CLI with partial TUI)
  ├─ v1.9.0  - Current state
  └─ v1.9.1  - Bug fixes during refactoring

v2.0-alpha - Core extraction phase
  ├─ v2.0.0-alpha.1 - Core module structure
  ├─ v2.0.0-alpha.2 - Transcription engine extracted
  └─ v2.0.0-alpha.3 - All core modules extracted

v2.0-beta  - Studio development phase
  ├─ v2.0.0-beta.1  - Studio foundation
  ├─ v2.0.0-beta.2  - Transcribe workflow complete
  └─ v2.0.0-beta.3  - All workflows complete

v2.0.0    - Official unified release
```

**What was valuable in the "2.0" work?**
- Textual TUI integration (keep)
- Episode browser improvements (keep)
- Progress tracking concepts (keep)
- Unified styling approach (keep)

**What was broken?**
- Incomplete modal flows
- Missing Esc behavior
- Inconsistent command integration

**New approach**: Mark as `2.0-alpha` work, iterate properly

## Core API Design

### Key Principles
1. **No UI imports** in core modules
2. **Callback-based** progress reporting
3. **Type-safe** with proper models
4. **Testable** without mocking

### Example: Transcription Engine

```python
# podx/core/transcribe.py
from pathlib import Path
from typing import Callable, Optional
from .models import Transcript, TranscriptionProgress

class TranscriptionEngine:
    """Pure transcription logic, no UI dependencies."""

    def __init__(
        self,
        model: str,
        provider: str = "faster-whisper",
        device: str = "cpu"
    ):
        self.model = model
        self.provider = provider
        self.device = device

    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[TranscriptionProgress], None]] = None
    ) -> Transcript:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Optional language code
            progress_callback: Optional progress updates

        Returns:
            Transcript with segments and metadata
        """
        # Pure processing logic
        # Call progress_callback() periodically if provided
        ...

        return Transcript(segments=segments, metadata=metadata)
```

### Example: Studio Usage

```python
# podx/studio/screens/transcribe.py
from textual.screen import Screen
from podx.core import TranscriptionEngine

class TranscribeScreen(Screen):
    async def run_transcription(self, episode, model):
        engine = TranscriptionEngine(model)

        # Run in worker thread
        result = await self.run_worker(
            engine.transcribe,
            audio_path=episode.audio_path,
            progress_callback=self.update_progress
        )

        self.show_completion(result)

    def update_progress(self, progress):
        # Update TUI progress display
        self.progress_bar.update(progress.percent)
```

### Example: CLI Usage

```python
# podx/cli/commands/transcribe.py
import click
from podx.core import TranscriptionEngine

@click.command()
@click.option("--audio", type=Path, required=True)
@click.option("--model", default="large-v3")
def transcribe(audio, model):
    """Transcribe audio file (CLI)."""
    engine = TranscriptionEngine(model)

    # No progress callback for CLI
    result = engine.transcribe(audio)

    # Output JSON to stdout
    print(result.to_json())
```

## Open Questions for Discussion

1. **Command naming**: `podx studio` vs `podx-studio`?
2. **Project concept**: Should studio support multi-episode "projects"?
3. **State persistence**: Save studio state between sessions?
4. **Configuration**: Studio-specific config file? Or reuse podx config?
5. **Model management**: Unified model download UI in studio?
6. **Batch processing**: Studio support for batch operations?
7. **Extensions**: Plugin system for custom workflows?

## Success Metrics

- [ ] All core logic has >80% test coverage
- [ ] New interface (web API) can be added in <1 day
- [ ] Studio workflows are consistent (same colors, shortcuts, patterns)
- [ ] CLI remains fully functional for scripting
- [ ] Users can choose CLI or Studio based on use case
- [ ] Documentation clearly explains when to use each

## Timeline Estimate

- **Phase 1** (Core extraction): 1-2 weeks
- **Phase 2** (Studio foundation): 2-3 weeks
- **Phase 3** (Workflows): 2-3 weeks
- **Phase 4** (CLI refactoring): 1 week
- **Phase 5** (Polish): 1-2 weeks

**Total**: 7-11 weeks for comprehensive refactoring

**Faster approach** (MVP): 4-6 weeks focusing on core + studio essentials
