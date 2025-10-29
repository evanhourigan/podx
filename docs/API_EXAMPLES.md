# PodX API Examples

Comprehensive examples of using the PodX Python SDK for various podcast processing tasks.

## Table of Contents

1. [Basic Transcription](#basic-transcription)
2. [Advanced Transcription](#advanced-transcription)
3. [Speaker Diarization](#speaker-diarization)
4. [AI Analysis (Deepcast)](#ai-analysis-deepcast)
5. [Export Formats](#export-formats)
6. [Fetching Episodes](#fetching-episodes)
7. [YouTube Processing](#youtube-processing)
8. [Complete Pipelines](#complete-pipelines)
9. [Batch Processing](#batch-processing)
10. [Custom Workflows](#custom-workflows)

## Basic Transcription

### Simple Whisper Transcription

```python
from podx import TranscriptionEngine
from pathlib import Path

# Initialize with default model
engine = TranscriptionEngine(model="base")

# Transcribe
transcript = engine.transcribe(Path("audio.wav"))

# Access results
print(f"Language: {transcript['language']}")
print(f"Segments: {len(transcript['segments'])}")

# Print first few segments
for segment in transcript['segments'][:3]:
    print(f"[{segment['start']:.2f}s] {segment['text']}")
```

### Using Different Models

```python
from podx import TranscriptionEngine

# Local models (faster-whisper)
models = ["tiny", "base", "small", "medium", "large-v3"]

for model in models:
    engine = TranscriptionEngine(model=model, compute_type="int8")
    transcript = engine.transcribe("audio.wav")
    print(f"{model}: {len(transcript['segments'])} segments")
```

### OpenAI Whisper API

```python
from podx import TranscriptionEngine
import os

# Set API key
os.environ["OPENAI_API_KEY"] = "sk-..."

# Use OpenAI's API
engine = TranscriptionEngine(
    model="openai:large-v3-turbo",
    provider="openai"
)

transcript = engine.transcribe("audio.wav")
```

## Advanced Transcription

### Custom Decoder Options

```python
from podx import TranscriptionEngine

engine = TranscriptionEngine(
    model="base",
    compute_type="int8",
    vad_filter=True,  # Voice activity detection
    condition_on_previous_text=True,
    extra_decode_options={
        "beam_size": 5,
        "best_of": 5,
        "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    }
)

transcript = engine.transcribe("audio.wav")
```

### Progress Callback

```python
from podx import TranscriptionEngine

def progress_callback(message: str):
    print(f"Progress: {message}")

engine = TranscriptionEngine(
    model="base",
    progress_callback=progress_callback
)

transcript = engine.transcribe("audio.wav")
```

### Save Transcript to File

```python
from podx import TranscriptionEngine
from pathlib import Path
import json

engine = TranscriptionEngine(model="base")
transcript = engine.transcribe("audio.wav")

# Save as JSON
output_path = Path("transcript.json")
output_path.write_text(
    json.dumps(transcript, indent=2, ensure_ascii=False)
)

print(f"Saved to {output_path}")
```

## Speaker Diarization

### Basic Diarization

```python
from podx import TranscriptionEngine, DiarizationEngine
from pathlib import Path

# Step 1: Transcribe
trans_engine = TranscriptionEngine(model="base")
transcript = trans_engine.transcribe(Path("audio.wav"))

# Step 2: Diarize
diar_engine = DiarizationEngine()
diarized = diar_engine.diarize(
    audio_path=Path("audio.wav"),
    transcript=transcript
)

# Print with speakers
for segment in diarized['segments'][:5]:
    speaker = segment.get('speaker', 'Unknown')
    print(f"[{speaker}] {segment['text']}")
```

### Speaker Statistics

```python
from podx import DiarizationEngine
from collections import Counter

diar_engine = DiarizationEngine()
diarized = diar_engine.diarize("audio.wav", transcript)

# Count segments per speaker
speakers = [seg.get('speaker') for seg in diarized['segments']]
speaker_counts = Counter(speakers)

print("Speaker Statistics:")
for speaker, count in speaker_counts.most_common():
    print(f"{speaker}: {count} segments")
```

## AI Analysis (Deepcast)

### Basic Analysis

```python
from podx import DeepcastEngine

engine = DeepcastEngine(
    model="gpt-4.1",
    temperature=0.2
)

analysis = engine.analyze(transcript)

print(f"Summary: {analysis['summary']}")
print(f"\nKey Points:")
for i, point in enumerate(analysis['key_points'], 1):
    print(f"{i}. {point}")

print(f"\nQuotes:")
for quote in analysis['quotes']:
    print(f"- \"{quote['text']}\" ({quote['speaker']})")
```

### Custom Podcast Type

```python
from podx import DeepcastEngine

# Specify podcast format
engine = DeepcastEngine(
    model="gpt-4.1",
    temperature=0.2,
    podcast_type="interview_guest_focused"  # or panel_discussion, solo_commentary
)

analysis = engine.analyze(transcript)
```

### Save Analysis as Markdown

```python
from podx import DeepcastEngine
from pathlib import Path

engine = DeepcastEngine(
    model="gpt-4.1",
    extract_markdown=True
)

analysis = engine.analyze(transcript)

# Analysis includes markdown
if 'markdown' in analysis:
    md_path = Path("analysis.md")
    md_path.write_text(analysis['markdown'])
    print(f"Saved markdown to {md_path}")
```

### Cost Estimation

```python
from podx import DeepcastEngine
import tiktoken

def estimate_cost(transcript: dict, model: str = "gpt-4.1"):
    """Estimate API cost before running."""
    enc = tiktoken.encoding_for_model(model.replace(".", "-"))

    # Estimate tokens
    text = " ".join(seg['text'] for seg in transcript['segments'])
    tokens = len(enc.encode(text))

    # Cost per 1K tokens (as of 2024)
    cost_per_1k = {
        "gpt-4.1": 0.03,
        "gpt-4.1-mini": 0.0015,
    }

    estimated_cost = (tokens / 1000) * cost_per_1k.get(model, 0.03)
    print(f"Estimated tokens: {tokens}")
    print(f"Estimated cost: ${estimated_cost:.4f}")

    return estimated_cost

# Check before running
estimate_cost(transcript, model="gpt-4.1")
```

## Export Formats

### Export to All Formats

```python
from podx import ExportEngine
from pathlib import Path

engine = ExportEngine()

result = engine.export_all(
    transcript=transcript,
    output_dir=Path("output"),
    formats=["txt", "srt", "vtt", "md"]
)

print(f"Exported files:")
for file_path in result['files']:
    print(f"- {file_path}")
```

### Custom Export

```python
from podx import ExportEngine
from pathlib import Path

engine = ExportEngine()

# Export TXT only
txt_content = engine.export_txt(transcript)
Path("transcript.txt").write_text(txt_content)

# Export SRT with custom settings
srt_content = engine.export_srt(transcript, max_chars_per_line=42)
Path("transcript.srt").write_text(srt_content)
```

## Fetching Episodes

### Fetch from RSS Feed

```python
from podx import fetch_episode, find_feed_url

# Find feed URL
feed_url = find_feed_url("Lenny's Podcast")
print(f"Feed: {feed_url}")

# Fetch specific episode
episode = fetch_episode(
    feed_url=feed_url,
    date="2024-03-15"
)

print(f"Title: {episode['title']}")
print(f"Audio: {episode['audio_path']}")
print(f"Duration: {episode.get('duration', 'unknown')}")
```

### Search Episodes

```python
from podx import search_podcasts

results = search_podcasts("Lenny's Podcast")

print(f"Found {len(results)} podcasts:")
for podcast in results[:5]:
    print(f"- {podcast['collectionName']}")
    print(f"  Feed: {podcast.get('feedUrl', 'N/A')}")
```

### Fetch Latest Episode

```python
from podx import fetch_episode, find_feed_url
import feedparser

feed_url = find_feed_url("Lenny's Podcast")
feed = feedparser.parse(feed_url)

# Get latest episode
latest = feed.entries[0]
print(f"Latest: {latest.title}")
print(f"Published: {latest.published}")

# Download it
episode = fetch_episode(
    feed_url=feed_url,
    title_contains=latest.title[:20]  # Match by title
)
```

## YouTube Processing

### Download and Process YouTube Video

```python
from podx import YouTubeEngine, TranscriptionEngine, DeepcastEngine
from pathlib import Path

# Download
youtube_engine = YouTubeEngine()
download_result = youtube_engine.download(
    "https://youtube.com/watch?v=xyz"
)

print(f"Downloaded: {download_result['title']}")
audio_path = Path(download_result['audio_path'])

# Transcribe
trans_engine = TranscriptionEngine(model="base")
transcript = trans_engine.transcribe(audio_path)

# Analyze
deep_engine = DeepcastEngine(model="gpt-4.1")
analysis = deep_engine.analyze(transcript)

print(f"Summary: {analysis['summary']}")
```

### Get YouTube Metadata

```python
from podx import get_youtube_metadata, is_youtube_url

url = "https://youtube.com/watch?v=xyz"

if is_youtube_url(url):
    metadata = get_youtube_metadata(url)

    print(f"Title: {metadata['title']}")
    print(f"Channel: {metadata['channel']}")
    print(f"Duration: {metadata['duration']}s")
    print(f"Upload Date: {metadata['upload_date']}")
```

## Complete Pipelines

### Full Pipeline with Error Handling

```python
from podx import (
    TranscriptionEngine,
    DiarizationEngine,
    DeepcastEngine,
    ExportEngine,
    TranscriptionError,
    DiarizationError,
    DeepcastError,
)
from pathlib import Path

def process_audio_complete(audio_path: Path, output_dir: Path):
    """Complete processing pipeline with error handling."""
    try:
        # Step 1: Transcribe
        print("Transcribing...")
        trans_engine = TranscriptionEngine(model="base")
        transcript = trans_engine.transcribe(audio_path)
        print(f"✓ Transcribed {len(transcript['segments'])} segments")

        # Step 2: Diarize
        print("Diarizing...")
        diar_engine = DiarizationEngine()
        diarized = diar_engine.diarize(audio_path, transcript)
        print("✓ Added speaker labels")

        # Step 3: AI Analysis
        print("Analyzing...")
        deep_engine = DeepcastEngine(model="gpt-4.1")
        analysis = deep_engine.analyze(diarized)
        print("✓ Generated analysis")

        # Step 4: Export
        print("Exporting...")
        export_engine = ExportEngine()
        result = export_engine.export_all(
            transcript=diarized,
            output_dir=output_dir,
            formats=["txt", "srt", "vtt", "md"]
        )
        print(f"✓ Exported to {len(result['files'])} files")

        return {
            "transcript": diarized,
            "analysis": analysis,
            "exports": result['files']
        }

    except TranscriptionError as e:
        print(f"✗ Transcription failed: {e}")
        return None
    except DiarizationError as e:
        print(f"✗ Diarization failed: {e}")
        return None
    except DeepcastError as e:
        print(f"✗ Analysis failed: {e}")
        return None

# Run pipeline
result = process_audio_complete(
    audio_path=Path("audio.wav"),
    output_dir=Path("output")
)
```

### Pipeline with Intermediate Saves

```python
from podx import TranscriptionEngine, DiarizationEngine, DeepcastEngine
from pathlib import Path
import json

def process_with_checkpoints(audio_path: Path, work_dir: Path):
    """Process with intermediate saves for resumability."""
    work_dir.mkdir(exist_ok=True)

    # Transcription
    transcript_path = work_dir / "transcript.json"
    if transcript_path.exists():
        print("Loading existing transcript...")
        transcript = json.loads(transcript_path.read_text())
    else:
        print("Transcribing...")
        engine = TranscriptionEngine(model="base")
        transcript = engine.transcribe(audio_path)
        transcript_path.write_text(json.dumps(transcript, indent=2))
        print(f"Saved: {transcript_path}")

    # Diarization
    diarized_path = work_dir / "diarized.json"
    if diarized_path.exists():
        print("Loading existing diarization...")
        diarized = json.loads(diarized_path.read_text())
    else:
        print("Diarizing...")
        engine = DiarizationEngine()
        diarized = engine.diarize(audio_path, transcript)
        diarized_path.write_text(json.dumps(diarized, indent=2))
        print(f"Saved: {diarized_path}")

    # Analysis
    analysis_path = work_dir / "analysis.json"
    if analysis_path.exists():
        print("Loading existing analysis...")
        analysis = json.loads(analysis_path.read_text())
    else:
        print("Analyzing...")
        engine = DeepcastEngine(model="gpt-4.1")
        analysis = engine.analyze(diarized)
        analysis_path.write_text(json.dumps(analysis, indent=2))
        print(f"Saved: {analysis_path}")

    return {
        "transcript": transcript,
        "diarized": diarized,
        "analysis": analysis
    }

result = process_with_checkpoints(
    audio_path=Path("audio.wav"),
    work_dir=Path("work")
)
```

## Batch Processing

### Process Multiple Files

```python
from podx import TranscriptionEngine
from pathlib import Path
import json

def batch_transcribe(audio_dir: Path, output_dir: Path):
    """Transcribe all audio files in a directory."""
    output_dir.mkdir(exist_ok=True)

    engine = TranscriptionEngine(model="base")

    audio_files = list(audio_dir.glob("*.wav")) + list(audio_dir.glob("*.mp3"))

    print(f"Found {len(audio_files)} audio files")

    for audio_file in audio_files:
        print(f"\nProcessing: {audio_file.name}")

        try:
            transcript = engine.transcribe(audio_file)

            # Save transcript
            output_file = output_dir / f"{audio_file.stem}_transcript.json"
            output_file.write_text(json.dumps(transcript, indent=2))

            print(f"✓ Saved: {output_file}")

        except Exception as e:
            print(f"✗ Failed: {e}")

# Run batch
batch_transcribe(
    audio_dir=Path("audio_files"),
    output_dir=Path("transcripts")
)
```

### Parallel Processing

```python
from podx import TranscriptionEngine
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import json

def transcribe_one(audio_path: Path, output_dir: Path):
    """Transcribe a single file."""
    engine = TranscriptionEngine(model="base")
    transcript = engine.transcribe(audio_path)

    output_file = output_dir / f"{audio_path.stem}_transcript.json"
    output_file.write_text(json.dumps(transcript, indent=2))

    return output_file

def batch_transcribe_parallel(audio_dir: Path, output_dir: Path, max_workers: int = 4):
    """Transcribe files in parallel."""
    output_dir.mkdir(exist_ok=True)

    audio_files = list(audio_dir.glob("*.wav"))

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(transcribe_one, audio_file, output_dir)
            for audio_file in audio_files
        ]

        for future in futures:
            try:
                result = future.result()
                print(f"✓ {result}")
            except Exception as e:
                print(f"✗ Error: {e}")

# Run parallel batch
batch_transcribe_parallel(
    audio_dir=Path("audio_files"),
    output_dir=Path("transcripts"),
    max_workers=4
)
```

## Custom Workflows

### Podcast Episode Monitoring

```python
from podx import find_feed_url, fetch_episode, TranscriptionEngine
import feedparser
from pathlib import Path
import json
import time

def monitor_podcast(show_name: str, check_interval: int = 3600):
    """Monitor podcast for new episodes and auto-transcribe."""
    feed_url = find_feed_url(show_name)
    seen_episodes = set()

    print(f"Monitoring: {show_name}")
    print(f"Feed: {feed_url}")

    while True:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:5]:  # Check latest 5
            episode_id = entry.get('id', entry.link)

            if episode_id not in seen_episodes:
                print(f"\n🆕 New episode: {entry.title}")

                try:
                    # Download
                    episode = fetch_episode(
                        feed_url=feed_url,
                        title_contains=entry.title[:20]
                    )

                    # Transcribe
                    engine = TranscriptionEngine(model="base")
                    transcript = engine.transcribe(Path(episode['audio_path']))

                    # Save
                    output = Path(f"transcripts/{episode_id}.json")
                    output.parent.mkdir(exist_ok=True)
                    output.write_text(json.dumps(transcript, indent=2))

                    print(f"✓ Transcribed and saved to {output}")

                except Exception as e:
                    print(f"✗ Failed: {e}")

                seen_episodes.add(episode_id)

        print(f"\nChecked at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Waiting {check_interval}s for next check...")
        time.sleep(check_interval)

# Start monitoring (runs forever)
monitor_podcast("Lenny's Podcast", check_interval=3600)
```

### Generate Episode Notes

```python
from podx import (
    TranscriptionEngine,
    DiarizationEngine,
    DeepcastEngine,
    ExportEngine,
)
from pathlib import Path

def generate_episode_notes(audio_path: Path, output_path: Path):
    """Generate comprehensive episode notes."""
    # Process
    trans_engine = TranscriptionEngine(model="base")
    transcript = trans_engine.transcribe(audio_path)

    diar_engine = DiarizationEngine()
    diarized = diar_engine.diarize(audio_path, transcript)

    deep_engine = DeepcastEngine(model="gpt-4.1", extract_markdown=True)
    analysis = deep_engine.analyze(diarized)

    # Create notes
    notes = f"""# Episode Notes

## Summary

{analysis['summary']}

## Key Points

"""

    for i, point in enumerate(analysis['key_points'], 1):
        notes += f"{i}. {point}\n"

    notes += "\n## Notable Quotes\n\n"

    for quote in analysis.get('quotes', []):
        speaker = quote.get('speaker', 'Unknown')
        notes += f"> \"{quote['text']}\" - {speaker}\n\n"

    if 'markdown' in analysis:
        notes += "\n## Full Analysis\n\n"
        notes += analysis['markdown']

    # Save
    output_path.write_text(notes)
    print(f"✓ Saved episode notes to {output_path}")

# Generate notes
generate_episode_notes(
    audio_path=Path("audio.wav"),
    output_path=Path("episode_notes.md")
)
```

## Integration Examples

### Flask Web API

```python
from flask import Flask, request, jsonify
from podx import TranscriptionEngine
from pathlib import Path
import tempfile

app = Flask(__name__)
engine = TranscriptionEngine(model="base")

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """API endpoint for transcription."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']

    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        audio_file.save(tmp.name)
        transcript = engine.transcribe(Path(tmp.name))

    return jsonify(transcript)

if __name__ == '__main__':
    app.run(debug=True)
```

### Notion Integration

```python
from podx import (
    TranscriptionEngine,
    DeepcastEngine,
    NotionEngine,
)
from pathlib import Path
import os

def upload_to_notion(audio_path: Path, episode_title: str):
    """Process audio and upload to Notion."""
    # Set Notion credentials
    os.environ["NOTION_TOKEN"] = "secret_..."
    os.environ["NOTION_DB_ID"] = "..."

    # Process
    trans_engine = TranscriptionEngine(model="base")
    transcript = trans_engine.transcribe(audio_path)

    deep_engine = DeepcastEngine(model="gpt-4.1", extract_markdown=True)
    analysis = deep_engine.analyze(transcript)

    # Upload
    notion_engine = NotionEngine()
    result = notion_engine.upload(
        title=episode_title,
        content=analysis.get('markdown', ''),
        properties={
            "Status": "Processed",
            "AI Model": "gpt-4.1",
        }
    )

    print(f"✓ Uploaded to Notion: {result['url']}")

upload_to_notion(
    audio_path=Path("audio.wav"),
    episode_title="Episode 123: Great Discussion"
)
```

## Error Handling Best Practices

```python
from podx import (
    TranscriptionEngine,
    TranscriptionError,
    AudioError,
    ValidationError,
)
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_transcribe(audio_path: Path):
    """Transcribe with comprehensive error handling."""
    try:
        # Validate input
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if audio_path.stat().st_size == 0:
            raise ValueError("Audio file is empty")

        # Transcribe
        engine = TranscriptionEngine(model="base")
        transcript = engine.transcribe(audio_path)

        logger.info(f"Successfully transcribed {len(transcript['segments'])} segments")
        return transcript

    except TranscriptionError as e:
        logger.error(f"Transcription failed: {e}")
        return None
    except AudioError as e:
        logger.error(f"Audio processing error: {e}")
        return None
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None

# Use it
result = safe_transcribe(Path("audio.wav"))
if result:
    print("Success!")
```

---

## Next Steps

- **Quick Start**: [QUICK_START.md](./QUICK_START.md)
- **Architecture**: [ARCHITECTURE_V2.md](./ARCHITECTURE_V2.md)
- **API Reference**: [CORE_API.md](./CORE_API.md)
- **Migration**: [MIGRATION_V1_TO_V2.md](./MIGRATION_V1_TO_V2.md)

**Questions?** Open an issue on [GitHub](https://github.com/evanhourigan/podx/issues).
