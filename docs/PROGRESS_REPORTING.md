# Progress Reporting API

PodX provides a unified progress reporting abstraction that works seamlessly across CLI, web API, TUI, and testing contexts.

## Table of Contents

1. [Overview](#overview)
2. [ProgressReporter Interface](#progressreporter-interface)
3. [Built-in Reporters](#built-in-reporters)
4. [Web API Integration](#web-api-integration)
5. [Usage Examples](#usage-examples)
6. [Best Practices](#best-practices)

---

## Overview

The progress reporting system provides a clean abstraction for status updates during long-running operations (transcription, AI analysis, etc.) without coupling business logic to UI frameworks.

### Architecture

```
┌─────────────────────┐
│  Core Engines       │
│  - TranscribeEngine │
│  - DeepcastEngine   │
│  - PreprocessEngine │
└──────────┬──────────┘
           │ Uses ProgressReporter interface
           │
     ┌─────▼──────────────────────────┐
     │  ProgressReporter (Abstract)   │
     └─────┬──────────────────────────┘
           │
     ┌─────┴───────────────────────────────┐
     │                                     │
┌────▼────────────┐              ┌────────▼────────┐
│ ConsoleProgress │              │ APIProgressReporter │
│ Reporter        │              │                     │
│ (CLI/Terminal)  │              │ (Web API/SSE)       │
└─────────────────┘              └─────────────────────┘
     │                                     │
┌────▼────────────┐              ┌────────▼────────┐
│ SilentProgress  │              │ TUIProgressReporter │
│ Reporter        │              │                     │
│ (Testing)       │              │ (Textual TUI)       │
└─────────────────┘              └─────────────────────┘
```

### Key Benefits

- ✅ **Unified Interface** - Same API across all contexts
- ✅ **Testable** - SilentProgressReporter for tests
- ✅ **Flexible** - Easy to add new reporters (TUI, GUI, etc.)
- ✅ **Backward Compatible** - Supports legacy callback functions
- ✅ **Type-Safe** - Full type hints for autocomplete and validation

---

## ProgressReporter Interface

All progress reporters implement this abstract interface:

```python
from abc import ABC, abstractmethod
from typing import Optional

class ProgressReporter(ABC):
    """Abstract interface for progress reporting."""

    @abstractmethod
    def start_task(self, task_name: str, total_steps: Optional[int] = None) -> None:
        """Signal the start of a new task.

        Args:
            task_name: Name of the task being started
            total_steps: Optional total number of steps (for progress bar)
        """
        pass

    @abstractmethod
    def update_step(
        self,
        message: str,
        step: Optional[int] = None,
        progress: Optional[float] = None
    ) -> None:
        """Update progress with a status message.

        Args:
            message: Status message describing current step
            step: Optional step number (1-indexed)
            progress: Optional progress fraction (0.0 to 1.0)
        """
        pass

    @abstractmethod
    def complete_step(self, message: str, duration: Optional[float] = None) -> None:
        """Mark a step as complete.

        Args:
            message: Completion message
            duration: Optional duration in seconds
        """
        pass

    @abstractmethod
    def complete_task(self, message: str, duration: Optional[float] = None) -> None:
        """Mark the entire task as complete.

        Args:
            message: Completion message
            duration: Optional total duration in seconds
        """
        pass

    @abstractmethod
    def error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Report an error.

        Args:
            message: Error message
            exception: Optional exception that caused the error
        """
        pass
```

### ProgressStep Data Model

Reporters can optionally track structured progress steps:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ProgressStep:
    """Structured progress step data."""
    message: str
    step: Optional[int] = None
    progress: Optional[float] = None  # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)
```

---

## Built-in Reporters

### ConsoleProgressReporter

Rich-based console output for CLI applications.

```python
from podx.progress import ConsoleProgressReporter

# Basic usage
progress = ConsoleProgressReporter()

# With custom console
from rich.console import Console
console = Console(file=sys.stderr, force_terminal=True)
progress = ConsoleProgressReporter(console=console, verbose=True)

# Example output
# [12:34:56] Starting transcription
# [12:35:01] ⠋ Processing chunk 1/5
# [12:35:05] ✓ Chunk 1 complete (4.2s)
```

**Features:**
- Colored output using Rich library
- Timestamps on each message
- Optional verbose mode for detailed logging
- Spinners and progress indicators

**Use when:**
- Building CLI tools
- Running scripts in terminal
- Debugging with rich output

### APIProgressReporter

Event queue-based reporter for web APIs with SSE/WebSocket support.

```python
from podx.progress import APIProgressReporter

# Create reporter
progress = APIProgressReporter(maxlen=1000)

# Use with engine
engine = TranscribeEngine(progress=progress)
result = engine.transcribe(audio_path)

# Get all events
events = progress.get_events()

# Get events since timestamp
events = progress.get_events(since=last_timestamp)

# Clear old events
progress.clear()
```

**Event Structure:**

```python
from dataclasses import dataclass

@dataclass
class ProgressEvent:
    """Progress event for API streaming."""
    type: str           # "start", "update", "complete", "error"
    message: str        # Status message
    step: Optional[int] = None
    progress: Optional[float] = None  # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)
    data: Optional[dict] = None  # Additional context
```

**Use when:**
- Building web APIs (FastAPI, Flask, Django)
- Streaming progress via SSE or WebSocket
- Need to poll for progress updates

**See:** [Web API Integration](#web-api-integration) for detailed examples.

### SilentProgressReporter

No-op reporter for testing, with optional call tracking.

```python
from podx.progress import SilentProgressReporter

# Basic usage (no tracking)
progress = SilentProgressReporter()

# With call tracking for testing
progress = SilentProgressReporter(track_calls=True)
engine = TranscribeEngine(progress=progress)
engine.transcribe(audio_path)

# Verify progress updates in tests
assert len(progress.calls) > 0
assert progress.calls[0] == ("start_task", "Transcribing audio", {...})
```

**Use when:**
- Writing unit tests
- Benchmarking without I/O overhead
- Silent background processing

---

## Web API Integration

### FastAPI with Server-Sent Events (SSE)

Stream progress updates to web clients in real-time:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from podx.core.transcribe import TranscribeEngine
from podx.progress import APIProgressReporter
import asyncio
import json

app = FastAPI()

@app.post("/transcribe")
async def transcribe_audio(audio_path: str):
    """Transcribe audio with real-time progress via SSE."""
    progress = APIProgressReporter()

    # Start transcription in background
    async def run_transcription():
        engine = TranscribeEngine(progress=progress)
        return engine.transcribe(audio_path)

    # Start task
    task = asyncio.create_task(run_transcription())
    last_timestamp = 0.0

    # Stream events as SSE
    async def event_stream():
        nonlocal last_timestamp

        while not task.done():
            # Get new events since last poll
            events = progress.get_events(since=last_timestamp)

            for event in events:
                # Format as SSE
                data = {
                    "type": event.type,
                    "message": event.message,
                    "step": event.step,
                    "progress": event.progress,
                    "timestamp": event.timestamp
                }
                yield f"data: {json.dumps(data)}\n\n"
                last_timestamp = event.timestamp

            await asyncio.sleep(0.1)  # Poll interval

        # Wait for result
        result = await task

        # Send completion event
        yield f"data: {json.dumps({'type': 'complete', 'result': str(result)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )
```

**Client-side JavaScript:**

```javascript
const eventSource = new EventSource('/transcribe?audio_path=podcast.mp3');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'start') {
        console.log(`Starting: ${data.message}`);
    } else if (data.type === 'update') {
        console.log(`Progress: ${data.progress * 100}% - ${data.message}`);
        updateProgressBar(data.progress);
    } else if (data.type === 'complete') {
        console.log('Complete!');
        eventSource.close();
    } else if (data.type === 'error') {
        console.error(`Error: ${data.message}`);
        eventSource.close();
    }
};
```

### FastAPI with WebSocket

For bidirectional communication:

```python
from fastapi import WebSocket
from podx.core.deepcast import DeepcastEngine
from podx.progress import APIProgressReporter

@app.websocket("/ws/deepcast")
async def deepcast_websocket(websocket: WebSocket):
    await websocket.accept()

    # Receive request
    data = await websocket.receive_json()
    transcript_path = data["transcript_path"]

    # Setup progress reporter
    progress = APIProgressReporter()

    # Run analysis
    async def run_analysis():
        engine = DeepcastEngine(progress=progress)
        return engine.deepcast(transcript)

    task = asyncio.create_task(run_analysis())
    last_timestamp = 0.0

    # Stream progress updates
    while not task.done():
        events = progress.get_events(since=last_timestamp)

        for event in events:
            await websocket.send_json({
                "type": event.type,
                "message": event.message,
                "progress": event.progress
            })
            last_timestamp = event.timestamp

        await asyncio.sleep(0.1)

    # Send result
    result = await task
    await websocket.send_json({
        "type": "complete",
        "result": result
    })

    await websocket.close()
```

### Flask with SSE

For non-async frameworks:

```python
from flask import Flask, Response, request
from podx.core.transcribe import TranscribeEngine
from podx.progress import APIProgressReporter
import json
import time

app = Flask(__name__)

@app.route('/transcribe')
def transcribe():
    audio_path = request.args.get('audio_path')
    progress = APIProgressReporter()

    def generate():
        # Start transcription in thread
        from threading import Thread
        result = [None]

        def run():
            engine = TranscribeEngine(progress=progress)
            result[0] = engine.transcribe(audio_path)

        thread = Thread(target=run)
        thread.start()

        # Stream events
        last_timestamp = 0.0
        while thread.is_alive():
            events = progress.get_events(since=last_timestamp)
            for event in events:
                yield f"data: {json.dumps({
                    'type': event.type,
                    'message': event.message,
                    'progress': event.progress
                })}\n\n"
                last_timestamp = event.timestamp
            time.sleep(0.1)

        thread.join()

        # Send completion
        yield f"data: {json.dumps({
            'type': 'complete',
            'result': str(result[0])
        })}\n\n"

    return Response(generate(), mimetype='text/event-stream')
```

### Polling Endpoint

For simpler polling-based progress:

```python
from fastapi import FastAPI, BackgroundTasks
from podx.progress import APIProgressReporter
import uuid

app = FastAPI()
tasks = {}  # In-memory task storage

@app.post("/transcribe/start")
async def start_transcription(audio_path: str, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    progress = APIProgressReporter()

    async def run():
        engine = TranscribeEngine(progress=progress)
        result = engine.transcribe(audio_path)
        tasks[task_id]["result"] = result
        tasks[task_id]["status"] = "complete"

    tasks[task_id] = {
        "status": "running",
        "progress": progress,
        "result": None
    }

    background_tasks.add_task(run)
    return {"task_id": task_id}

@app.get("/transcribe/status/{task_id}")
async def get_status(task_id: str, since: float = 0.0):
    if task_id not in tasks:
        return {"error": "Task not found"}

    task = tasks[task_id]
    events = task["progress"].get_events(since=since)

    return {
        "status": task["status"],
        "events": [
            {
                "type": e.type,
                "message": e.message,
                "progress": e.progress,
                "timestamp": e.timestamp
            }
            for e in events
        ],
        "result": task["result"] if task["status"] == "complete" else None
    }
```

**Client usage:**

```javascript
// Start task
const response = await fetch('/transcribe/start', {
    method: 'POST',
    body: JSON.stringify({audio_path: 'podcast.mp3'})
});
const {task_id} = await response.json();

// Poll for progress
let lastTimestamp = 0;
const interval = setInterval(async () => {
    const status = await fetch(`/transcribe/status/${task_id}?since=${lastTimestamp}`);
    const data = await status.json();

    data.events.forEach(event => {
        console.log(`[${event.type}] ${event.message}`);
        updateUI(event);
        lastTimestamp = event.timestamp;
    });

    if (data.status === 'complete') {
        clearInterval(interval);
        console.log('Result:', data.result);
    }
}, 500);  // Poll every 500ms
```

---

## Usage Examples

### Basic Engine Usage

```python
from podx.core.transcribe import TranscribeEngine
from podx.progress import ConsoleProgressReporter

# Create reporter
progress = ConsoleProgressReporter(verbose=True)

# Use with engine
engine = TranscribeEngine(
    model="large-v3",
    progress=progress
)

result = engine.transcribe("podcast.mp3")
```

### Multiple Engines with Same Reporter

```python
from podx.progress import ConsoleProgressReporter
from podx.core.transcribe import TranscribeEngine
from podx.core.preprocess import TranscriptPreprocessor
from podx.core.deepcast import DeepcastEngine

# Shared reporter for pipeline
progress = ConsoleProgressReporter()

# Step 1: Transcribe
progress.start_task("Processing podcast")
transcribe = TranscribeEngine(progress=progress)
transcript = transcribe.transcribe("podcast.mp3")

# Step 2: Preprocess
preprocess = TranscriptPreprocessor(
    merge=True,
    restore=True,
    progress=progress
)
cleaned = preprocess.preprocess(transcript)

# Step 3: Analyze
deepcast = DeepcastEngine(
    model="gpt-4o",
    progress=progress
)
analysis, insights = deepcast.deepcast(cleaned)

progress.complete_task("Pipeline complete!")
```

### Custom Reporter

Create your own reporter for custom UI frameworks:

```python
from podx.progress import ProgressReporter
from typing import Optional

class CustomUIProgressReporter(ProgressReporter):
    """Custom reporter for your UI framework."""

    def __init__(self, ui_widget):
        self.widget = ui_widget

    def start_task(self, task_name: str, total_steps: Optional[int] = None):
        self.widget.set_title(task_name)
        if total_steps:
            self.widget.set_max(total_steps)

    def update_step(self, message: str, step: Optional[int] = None,
                    progress: Optional[float] = None):
        self.widget.set_status(message)
        if progress is not None:
            self.widget.set_progress(int(progress * 100))
        elif step is not None:
            self.widget.set_step(step)

    def complete_step(self, message: str, duration: Optional[float] = None):
        self.widget.add_log(f"✓ {message}")

    def complete_task(self, message: str, duration: Optional[float] = None):
        self.widget.set_complete(message)

    def error(self, message: str, exception: Optional[Exception] = None):
        self.widget.show_error(message)

# Use with engine
progress = CustomUIProgressReporter(my_ui_widget)
engine = TranscribeEngine(progress=progress)
```

### Testing with Call Tracking

```python
from podx.progress import SilentProgressReporter
from podx.core.preprocess import TranscriptPreprocessor

def test_preprocessing_progress():
    # Create tracking reporter
    progress = SilentProgressReporter(track_calls=True)

    # Run operation
    preprocessor = TranscriptPreprocessor(
        restore=True,
        restore_batch_size=2,
        progress=progress
    )
    result = preprocessor.preprocess(transcript)

    # Verify progress updates
    assert len(progress.calls) >= 2

    # Check batch progress reporting
    update_calls = [c for c in progress.calls if c[0] == "update_step"]
    assert any("batch" in c[1].lower() for c in update_calls)

    # Check progress values
    for method, message, kwargs in progress.calls:
        if "progress" in kwargs:
            assert 0.0 <= kwargs["progress"] <= 1.0
```

### Backward Compatibility

Engines still support legacy callback functions:

```python
from podx.core.deepcast import DeepcastEngine

# Old style: callback function
def my_callback(message: str):
    print(f"Status: {message}")

# Works with legacy callback
engine = DeepcastEngine(progress_callback=my_callback)

# Also works with new ProgressReporter
from podx.progress import ConsoleProgressReporter
engine = DeepcastEngine(progress=ConsoleProgressReporter())

# Both can be passed via 'progress' parameter with type checking
engine = DeepcastEngine(progress=my_callback)  # Auto-detected as callback
```

---

## Best Practices

### 1. Use ConsoleProgressReporter for CLI

```python
from podx.progress import ConsoleProgressReporter

# Good: Rich console output for CLI
progress = ConsoleProgressReporter()
```

### 2. Use APIProgressReporter for Web APIs

```python
from podx.progress import APIProgressReporter

# Good: Event queue for SSE/WebSocket
progress = APIProgressReporter(maxlen=1000)
```

### 3. Use SilentProgressReporter for Tests

```python
from podx.progress import SilentProgressReporter

# Good: No I/O overhead in tests
progress = SilentProgressReporter()

# Or with tracking for assertions
progress = SilentProgressReporter(track_calls=True)
```

### 4. Clear Event Queue Periodically

```python
# For long-running processes, prevent memory growth
if len(progress.events) > 10000:
    progress.clear()
```

### 5. Provide Progress Fractions

```python
# Good: Provides UI percentage
progress.update_step(
    f"Processing batch {i}/{total}",
    step=i,
    progress=i / total  # 0.0 to 1.0
)

# Works but less useful for progress bars
progress.update_step("Processing...")
```

### 6. Report Task Boundaries

```python
# Good: Clear task lifecycle
progress.start_task("Transcribing audio", total_steps=3)
progress.update_step("Loading model", step=1, progress=0.33)
progress.update_step("Processing audio", step=2, progress=0.66)
progress.update_step("Saving transcript", step=3, progress=1.0)
progress.complete_task("Transcription complete", duration=45.2)

# Bad: No clear start/end
progress.update_step("Transcribing...")
```

### 7. Include Duration Metrics

```python
import time

start = time.time()
# ... do work ...
duration = time.time() - start

progress.complete_task("Task complete", duration=duration)
```

### 8. Handle Errors Gracefully

```python
try:
    result = engine.process(data)
    progress.complete_task("Success!")
except Exception as e:
    progress.error(f"Processing failed: {e}", exception=e)
    raise
```

---

## API Reference

### ProgressReporter

Base abstract class for all reporters.

**Methods:**
- `start_task(task_name, total_steps=None)` - Start new task
- `update_step(message, step=None, progress=None)` - Update progress
- `complete_step(message, duration=None)` - Mark step complete
- `complete_task(message, duration=None)` - Mark task complete
- `error(message, exception=None)` - Report error

### ConsoleProgressReporter

Rich-based console output.

**Constructor:**
```python
ConsoleProgressReporter(
    console: Optional[Console] = None,
    verbose: bool = False
)
```

**Parameters:**
- `console` - Rich Console instance (creates default if None)
- `verbose` - Enable verbose logging

### APIProgressReporter

Event queue for web API integration.

**Constructor:**
```python
APIProgressReporter(maxlen: int = 1000)
```

**Parameters:**
- `maxlen` - Maximum events to keep in queue (FIFO)

**Methods:**
- `get_events(since: Optional[float] = None) -> list[ProgressEvent]` - Get events since timestamp
- `clear()` - Clear all events

**Properties:**
- `events: Deque[ProgressEvent]` - Event queue

### SilentProgressReporter

No-op reporter for testing.

**Constructor:**
```python
SilentProgressReporter(track_calls: bool = False)
```

**Parameters:**
- `track_calls` - Enable call tracking for test assertions

**Properties:**
- `calls: list[tuple[str, str, dict]]` - List of (method, message, kwargs) if tracking enabled

### ProgressEvent

Data model for API events.

**Fields:**
```python
@dataclass
class ProgressEvent:
    type: str                    # "start", "update", "complete", "error"
    message: str                 # Status message
    step: Optional[int] = None   # Step number (1-indexed)
    progress: Optional[float] = None  # Progress fraction (0.0-1.0)
    timestamp: float             # Unix timestamp
    data: Optional[dict] = None  # Additional context
```

---

## See Also

- [Python API Documentation](./api/python-api.md) - Client API with progress callbacks
- [Core API Documentation](./CORE_API.md) - Engine reference with progress examples
- [Testing Guide](./TESTING.md) - Testing with SilentProgressReporter
- [Architecture](./ARCHITECTURE_V2.md) - System design patterns

---

## Support

For questions and issues:
- GitHub Issues: https://github.com/evanhourigan/podx/issues
- Documentation: https://github.com/evanhourigan/podx/tree/main/docs
