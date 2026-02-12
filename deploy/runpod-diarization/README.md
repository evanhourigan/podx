# RunPod Diarization Endpoint

Speaker diarization handler for RunPod serverless. Runs WhisperX alignment + pyannote diarization.

## Quick Deploy (Docker Hub)

If you've pushed this to Docker Hub:

1. Go to [RunPod Serverless Console](https://runpod.io/console/serverless)
2. Click **New Endpoint**
3. Select **Custom** template
4. Enter your Docker image: `yourusername/podx-diarization:latest`
5. Configure:
   - GPU: **RTX A4000** or **RTX 4090** (24GB VRAM recommended)
   - Min Workers: **0** (scale to zero)
   - Max Workers: **1-3**
6. Add environment variable: `HUGGINGFACE_TOKEN` = your HF token
7. Deploy

## Build & Push

```bash
# Build the image
docker build -t podx-diarization .

# Tag for Docker Hub
docker tag podx-diarization yourusername/podx-diarization:latest

# Push to Docker Hub
docker push yourusername/podx-diarization:latest
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HUGGINGFACE_TOKEN` | Yes | HuggingFace token for pyannote models |
| `DEVICE` | No | Device to use (default: `cuda`) |

## API Format

### Request

```json
{
  "input": {
    "audio_base64": "<base64-encoded-audio>",
    "transcript_segments": [
      {"start": 0.0, "end": 2.5, "text": "Hello world"},
      {"start": 2.5, "end": 5.0, "text": "How are you"}
    ],
    "num_speakers": null,
    "min_speakers": null,
    "max_speakers": null,
    "language": "en"
  }
}
```

### Response

```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello world",
      "speaker": "SPEAKER_00",
      "words": [
        {"word": "Hello", "start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"},
        {"word": "world", "start": 0.6, "end": 1.0, "speaker": "SPEAKER_00"}
      ]
    }
  ],
  "speakers_count": 2
}
```

## GPU Requirements

- **VRAM**: 10-16GB minimum, 24GB recommended
- **Recommended GPUs**: RTX A4000, RTX 4090, A100
- Processing time: ~30-60s per hour of audio

## Cold Start

First request after scale-to-zero takes ~30-60s to:
1. Start the container
2. Load alignment model (~1GB)
3. Load diarization pipeline (~1GB)

Subsequent requests are fast (models stay in memory).

## Usage with PodX

After deploying, configure PodX:

```bash
podx cloud setup
# Or manually:
podx config set runpod-diarize-endpoint-id YOUR_ENDPOINT_ID
```

Then use cloud diarization:

```bash
podx diarize --provider runpod ./episode/
```
