# PodX Service Layer

The service layer provides a programmatic API for integrating PodX into Python applications, notebooks, or automation scripts. It separates business logic from CLI concerns, enabling:

- **Library Usage**: Use PodX as a Python library instead of CLI
- **Custom Interfaces**: Build web apps, APIs, or GUIs on top of PodX
- **Testing**: Easy mocking and unit testing of pipeline logic
- **Automation**: Integrate into data pipelines and workflows

## Architecture

```
podx/services/
├── __init__.py                # Public API exports
├── command_builder.py         # Fluent command construction
├── step_executor.py           # Synchronous command execution
├── pipeline_service.py        # Synchronous orchestration
├── async_step_executor.py     # Async command execution
└── async_pipeline_service.py  # Async orchestration
```

### Component Responsibilities

**CommandBuilder** (`command_builder.py`)
- Fluent API for building CLI commands
- Type-safe option handling
- Automatic quoting and escaping
- Used by: StepExecutor, AsyncStepExecutor, orchestrate.py helpers

**StepExecutor** (`step_executor.py`)
- Executes individual pipeline steps via subprocess
- Handles JSON stdin/stdout communication
- Provides step-specific methods (fetch, transcribe, align, etc.)
- Used by: PipelineService

**PipelineService** (`pipeline_service.py`)
- High-level pipeline orchestration
- State management and artifact detection
- Resumption logic for crashed/interrupted pipelines
- Progress callbacks for UI integration
- Used by: External applications, notebooks

**AsyncStepExecutor** (`async_step_executor.py`)
- Async version of StepExecutor using asyncio
- Non-blocking subprocess execution
- Enables concurrent step execution
- Used by: AsyncPipelineService

**AsyncPipelineService** (`async_pipeline_service.py`)
- Async pipeline orchestration with concurrent execution
- Can run align + diarize steps in parallel
- Batch processing with concurrency control
- Perfect for web apps, APIs, and async applications
- Used by: FastAPI, aiohttp, async notebooks

## Quick Start

### Basic Pipeline

```python
from podx.services import PipelineService, PipelineConfig

# Configure pipeline
config = PipelineConfig(
    show="Lex Fridman Podcast",
    date="2024-10-01",
    model="large-v3-turbo",
    align=True,
    deepcast=True,
)

# Execute pipeline
service = PipelineService(config)
result = service.execute()

print(f"Completed in {result.duration:.2f}s")
print(f"Artifacts: {result.artifacts}")
```

### With Progress Tracking

```python
def on_progress(step: str, status: str):
    print(f"[{step}] {status}")

result = service.execute(progress_callback=on_progress)
```

### Custom Working Directory

```python
from pathlib import Path

config = PipelineConfig(
    show="All-In Podcast",
    workdir=Path("./output/all-in/2024-10-15"),
    model="large-v3-turbo",
)
```

## Configuration

### PipelineConfig

All pipeline parameters are specified via `PipelineConfig`:

```python
@dataclass
class PipelineConfig:
    # Source (choose one)
    show: Optional[str] = None              # Podcast name
    rss_url: Optional[str] = None           # Direct RSS URL
    youtube_url: Optional[str] = None       # YouTube video URL

    # Filtering
    date: Optional[str] = None              # Date filter (YYYY-MM-DD)
    title_contains: Optional[str] = None    # Title substring filter

    # Working Directory
    workdir: Optional[Path] = None          # Custom workdir (auto-generated if None)

    # Audio
    fmt: str = "wav16"                      # wav16, mp3, aac

    # Transcription
    model: str = "base"                     # ASR model (base, large-v3-turbo, etc.)
    compute: str = "int8"                   # int8, float16, float32
    asr_provider: Optional[str] = None      # auto, local, openai, hf
    preset: Optional[str] = None            # balanced, precision, recall

    # Enhancement
    align: bool = False                     # Word-level alignment
    diarize: bool = False                   # Speaker diarization
    preprocess: bool = False                # Preprocessing
    restore: bool = False                   # Semantic restore (LLM)

    # Analysis
    deepcast: bool = False                  # AI analysis
    dual: bool = False                      # Dual-mode (precision + recall)
    no_consensus: bool = False              # Skip consensus in dual mode
    deepcast_model: str = "gpt-4"           # LLM for analysis
    deepcast_temp: float = 0.7              # Temperature
    extract_markdown: bool = False          # Extract markdown
    deepcast_pdf: bool = False              # Generate PDF

    # Publishing
    notion: bool = False                    # Upload to Notion
    notion_db: Optional[str] = None         # Notion database ID

    # Execution
    verbose: bool = False                   # Verbose logging
    clean: bool = False                     # Clean intermediate files
    no_keep_audio: bool = False             # Don't keep audio files
```

## Result Structure

### PipelineResult

The `execute()` method returns a `PipelineResult`:

```python
@dataclass
class PipelineResult:
    workdir: Path                           # Working directory
    steps_completed: List[str]              # List of completed steps
    artifacts: Dict[str, str]               # Generated files {key: path}
    duration: float                         # Execution time (seconds)
    errors: List[str]                       # Errors encountered

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
```

Example:
```python
result = service.execute()

# Access results
print(f"Duration: {result.duration:.2f}s")
print(f"Steps: {', '.join(result.steps_completed)}")

# Access artifacts
transcript_path = result.artifacts.get("transcript")
if transcript_path and Path(transcript_path).exists():
    with open(transcript_path) as f:
        transcript = json.load(f)
```

## Use Cases

### 1. Jupyter Notebook Integration

```python
# In a Jupyter notebook
from podx.services import PipelineService, PipelineConfig
from IPython.display import Markdown, display

config = PipelineConfig(
    show="Lex Fridman Podcast",
    date="2024-10-01",
    deepcast=True,
    extract_markdown=True,
)

service = PipelineService(config)
result = service.execute()

# Display results
md_path = result.artifacts.get("exported_md")
if md_path:
    display(Markdown(Path(md_path).read_text()))
```

### 2. Web API Integration

```python
# Flask/FastAPI endpoint
from fastapi import FastAPI, BackgroundTasks
from podx.services import PipelineService, PipelineConfig

app = FastAPI()

@app.post("/process")
async def process_podcast(
    show: str,
    background_tasks: BackgroundTasks
):
    config = PipelineConfig(show=show, deepcast=True)

    def run_pipeline():
        service = PipelineService(config)
        result = service.execute()
        # Save result to database

    background_tasks.add_task(run_pipeline)
    return {"status": "processing"}
```

### 3. Batch Processing

```python
# Process multiple episodes
from podx.services import PipelineService, PipelineConfig

episodes = [
    ("Lex Fridman Podcast", "2024-10-01"),
    ("Lex Fridman Podcast", "2024-10-08"),
    ("Lex Fridman Podcast", "2024-10-15"),
]

for show, date in episodes:
    config = PipelineConfig(
        show=show,
        date=date,
        model="large-v3-turbo",
        deepcast=True,
    )

    service = PipelineService(config)
    result = service.execute()

    print(f"✓ Processed {show} ({date}) in {result.duration:.2f}s")
```

### 4. Custom Progress UI

```python
# Rich progress bar integration
from rich.progress import Progress, SpinnerColumn, TextColumn
from podx.services import PipelineService, PipelineConfig

config = PipelineConfig(show="My Podcast", deepcast=True)
service = PipelineService(config)

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
) as progress:
    task = progress.add_task("Processing podcast...", total=None)

    def update_progress(step: str, status: str):
        progress.update(task, description=f"{step}: {status}")

    result = service.execute(progress_callback=update_progress)
```

## Testing

The service layer is designed for easy testing:

```python
# tests/test_pipeline_service.py
from unittest.mock import Mock, patch
from podx.services import PipelineService, PipelineConfig

def test_pipeline_execution():
    config = PipelineConfig(show="Test Show")
    service = PipelineService(config)

    # Mock the executor
    with patch.object(service, 'executor') as mock_executor:
        mock_executor.fetch.return_value = {"episode_title": "Test"}
        result = service.execute()

        assert result.workdir.exists()
        assert len(result.steps_completed) > 0
```

## Advanced Usage

### Custom StepExecutor

```python
from podx.services import PipelineService, PipelineConfig, StepExecutor

class CustomExecutor(StepExecutor):
    def _run(self, cmd, **kwargs):
        # Add custom logging, metrics, etc.
        logger.info(f"Running: {' '.join(cmd)}")
        return super()._run(cmd, **kwargs)

config = PipelineConfig(show="Test")
executor = CustomExecutor(verbose=True)
service = PipelineService(config, executor=executor)
result = service.execute()
```

### Partial Pipeline Execution

```python
from podx.services import StepExecutor

# Execute individual steps
executor = StepExecutor(verbose=True)

# 1. Fetch episode
meta = executor.fetch(show="Lex Fridman Podcast", date="2024-10-01")

# 2. Transcode audio
audio = executor.transcode(meta=meta, fmt="wav16", outdir=Path("./output"))

# 3. Transcribe
transcript = executor.transcribe(
    audio=audio,
    model="large-v3-turbo",
    compute="int8"
)

# 4. Analyze
deepcast = executor.deepcast(
    transcript=transcript,
    model="gpt-4o",
    temperature=0.7
)
```

## Async Execution

PodX provides full async/await support for non-blocking pipeline execution and concurrent processing. This is ideal for:
- **Web Applications**: FastAPI, aiohttp servers
- **WebSocket Streaming**: Real-time progress updates
- **Batch Processing**: Process multiple episodes concurrently
- **Async Applications**: Any async Python application

### Basic Async Pipeline

```python
import asyncio
from podx.services import AsyncPipelineService, PipelineConfig

async def main():
    config = PipelineConfig(
        show="Lex Fridman Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        deepcast=True,
    )

    service = AsyncPipelineService(config)
    result = await service.execute()

    print(f"Completed in {result.duration:.2f}s")

asyncio.run(main())
```

### Concurrent Step Execution

When both `align` and `diarize` are enabled, AsyncPipelineService runs them **concurrently** for faster execution:

```python
config = PipelineConfig(
    show="All-In Podcast",
    date="2024-10-01",
    model="large-v3-turbo",
    align=True,      # Runs concurrently with diarize
    diarize=True,    # Runs concurrently with align
)

service = AsyncPipelineService(config)
result = await service.execute()

# Both align and diarize ran in parallel!
```

### Batch Processing with Concurrency Control

Process multiple episodes concurrently with a configurable concurrency limit:

```python
configs = [
    PipelineConfig(show="Lex Fridman Podcast", date="2024-10-01", deepcast=True),
    PipelineConfig(show="All-In Podcast", date="2024-10-01", deepcast=True),
    PipelineConfig(show="Acquired", date="2024-10-01", deepcast=True),
]

# Process max 2 episodes at a time
results = await AsyncPipelineService.process_batch(
    configs,
    max_concurrent=2,
    progress_callback=lambda idx, step, status: print(f"[{idx}] {step}: {status}")
)

for i, result in enumerate(results):
    print(f"{i+1}. Completed in {result.duration:.2f}s")
```

### FastAPI Integration

Perfect integration with async web frameworks:

```python
from fastapi import FastAPI, WebSocket
from podx.services import AsyncPipelineService, PipelineConfig

app = FastAPI()

@app.post("/process")
async def process_podcast(show: str, deepcast: bool = False):
    """Non-blocking API endpoint."""
    config = PipelineConfig(show=show, deepcast=deepcast)
    service = AsyncPipelineService(config)
    result = await service.execute()

    return {
        "workdir": str(result.workdir),
        "duration": result.duration,
        "artifacts": result.artifacts,
    }

@app.websocket("/process-stream")
async def process_with_progress(websocket: WebSocket):
    """Stream progress updates via WebSocket."""
    await websocket.accept()
    show = await websocket.receive_text()

    async def send_progress(step: str, status: str):
        await websocket.send_json({"step": step, "status": status})

    config = PipelineConfig(show=show, deepcast=True)
    service = AsyncPipelineService(config)

    try:
        result = await service.execute(progress_callback=send_progress)
        await websocket.send_json({"type": "complete", "result": result.to_dict()})
    except Exception as e:
        await websocket.send_json({"type": "error", "error": str(e)})
    finally:
        await websocket.close()
```

### Progress Tracking

Async progress callbacks for real-time updates:

```python
async def on_progress(step: str, status: str):
    """Called for each pipeline step update."""
    print(f"[{step}] {status}")
    # Send to websocket, update database, etc.

result = await service.execute(progress_callback=on_progress)
```

### Graceful Cancellation

AsyncPipelineService supports graceful cancellation:

```python
# Create cancellable task
task = asyncio.create_task(service.execute())

# Cancel if needed (e.g., user cancellation, timeout)
task.cancel()

try:
    result = await task
except asyncio.CancelledError:
    print("Pipeline was cancelled gracefully")
```

### Concurrent Metadata Fetching

Use AsyncStepExecutor for concurrent individual operations:

```python
from podx.services import AsyncStepExecutor

executor = AsyncStepExecutor(verbose=False)

# Fetch 3 different podcasts concurrently
results = await executor.run_concurrent(
    executor.fetch(show="Lex Fridman Podcast", date="2024-10-01"),
    executor.fetch(show="All-In Podcast", date="2024-10-01"),
    executor.fetch(show="Acquired", date="2024-10-01"),
)

for meta in results:
    print(f"✓ {meta['show']}: {meta['episode_title']}")
```

### Mixing Sync and Async

You can mix sync and async APIs as needed:

```python
# Use async for I/O-bound operations
executor = AsyncStepExecutor()
meta = await executor.fetch(show="Lex Fridman Podcast", date="2024-10-01")

# Continue with sync code if needed
from podx.services import PipelineService
config = PipelineConfig(show="...", model="...")
service = PipelineService(config)  # Sync version
```

### Async Examples

See `/examples/using_async_service_layer.py` for complete working examples:

1. Basic Async Pipeline
2. Concurrent Steps (align + diarize in parallel)
3. Batch Processing (multiple episodes with concurrency control)
4. FastAPI Integration Pattern
5. Concurrent Metadata Fetching
6. Custom Progress Tracking
7. Graceful Cancellation
8. Mixed Sync/Async Usage

### Async Benefits

✅ **Non-blocking Execution** - Doesn't block the event loop
✅ **Concurrent Processing** - Run align + diarize in parallel
✅ **Batch Operations** - Process 100s of episodes efficiently
✅ **Real-time Progress** - Stream updates via WebSockets
✅ **Web Framework Ready** - Perfect for FastAPI, aiohttp
✅ **Graceful Cancellation** - Clean shutdown on cancel
✅ **Scalable** - Handle many concurrent operations

## Migration from CLI

### Before (CLI)
```bash
podx run \
  --show "Lex Fridman Podcast" \
  --date 2024-10-01 \
  --model large-v3-turbo \
  --align \
  --deepcast
```

### After (Service Layer)
```python
from podx.services import PipelineService, PipelineConfig

config = PipelineConfig(
    show="Lex Fridman Podcast",
    date="2024-10-01",
    model="large-v3-turbo",
    align=True,
    deepcast=True,
)

service = PipelineService(config)
result = service.execute()
```

## Examples

### Synchronous API Examples

See `/examples/using_service_layer.py` for complete working examples:

1. Basic Pipeline (Fetch + Transcribe)
2. Full Pipeline (Align + Diarize + Deepcast)
3. Dual-Mode (Precision + Recall + Consensus)
4. YouTube Video Processing
5. Custom Working Directory

### Async API Examples

See `/examples/using_async_service_layer.py` for complete async examples:

1. Basic Async Pipeline
2. Concurrent Steps (align + diarize in parallel)
3. Batch Processing (multiple episodes with concurrency control)
4. FastAPI Integration Pattern
5. Concurrent Metadata Fetching
6. Custom Progress Tracking
7. Graceful Cancellation
8. Mixed Sync/Async Usage

## Benefits

✅ **Programmatic Control** - Full control over pipeline execution from Python
✅ **Type Safety** - Pydantic-based configuration with validation
✅ **Progress Tracking** - Callbacks for custom UI integration
✅ **State Management** - Automatic artifact detection and resumption
✅ **Testability** - Easy mocking and unit testing
✅ **Flexibility** - Use full pipeline or individual steps
✅ **Integration** - Perfect for notebooks, web apps, and automation

## Future Enhancements

Planned improvements:
- [x] Async execution with `asyncio` ✅ (Completed)
- [x] WebSocket streaming for real-time progress ✅ (Completed)
- [ ] Plugin system for custom steps
- [ ] REST API server mode (standalone FastAPI app)
- [ ] Distributed execution with Celery/RQ
- [ ] Streaming transcription with incremental updates
- [ ] GPU pool management for batch processing
