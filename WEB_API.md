# podx-web API Contract

Purpose: A thin HTTP/WS layer over the podx CLI to power the `podx-web` frontend. Stable JSON shapes mirror existing Pydantic models in `podx/schemas.py` and the unified Deepcast output.

Status: v0.2.0-alpha.1 (contract v0.1)

Base URL: http://localhost:8787 (example)
Content-Type: application/json

Auth: None for local. For deployment, add bearer token for all endpoints.

File paths: Always absolute on server responses.

---

## Models (summary)

- Transcript
  - audio_path: string | null
  - language: string | null
  - asr_model: string | null
  - asr_provider: "local" | "openai" | "hf" | null
  - preset: "balanced" | "precision" | "recall" | null
  - decoder_options: { [k: string]: string } | null
  - segments: [{ start: number, end: number, text: string }]
  - text: string

- Deepcast unified JSON
  - markdown: string
  - metadata: Transcript
  - deepcast_metadata: {
      model: string,
      temperature: number,
      podcast_type: string,
      processed_at: string,  // ISO8601
      asr_model: string | null,
      transcript_variant: "base" | "aligned" | "diarized",
      deepcast_type: string
    }
  - (optional) summary, key_points[], gold_nuggets[], quotes[], actions[], outline[]

- Agreement result
  - agreement_score: number (0-100)
  - unique_to_a: string[]
  - unique_to_b: string[]
  - contradictions: string[]
  - summary: string

---

## Endpoints

### GET /api/episodes
Discover episodes and available artifacts.

Query:
- dir: string (optional; scan root)

Response 200:
```json
{
  "episodes": [
    {
      "show": "The Podcast",
      "date": "2025-05-02",
      "title": "Episode Title",
      "directory": "/abs/path/The Podcast/2025-05-02",
      "artifacts": {
        "episode_meta": "/abs/.../episode-meta.json",
        "audio_meta": "/abs/.../audio-meta.json",
        "transcripts": [
          {"model": "large-v3", "variant": "base", "path": "/abs/.../transcript-large-v3.json"},
          {"model": "large-v3", "variant": "aligned", "path": "/abs/.../transcript-aligned-large-v3.json"}
        ],
        "deepcasts": [
          {"ai_model": "gpt-4.1", "type": "interview_guest_focused", "path": "/abs/.../deepcast-large_v3-gpt_4_1-interview_guest_focused.json"}
        ]
      }
    }
  ]
}
```

### POST /api/transcribe
Run ASR. Mirrors `podx-transcribe`.

Request:
```json
{
  "audio_path": "/abs/path/audio.wav",
  "model": "large-v3",
  "asr_provider": "local",
  "preset": "balanced",
  "compute": "int8"
}
```

Response 200: Transcript

### POST /api/preprocess
Merge/normalize/restore transcript. Mirrors `podx-preprocess`.

Request:
```json
{
  "transcript": {},
  "merge": true,
  "normalize": true,
  "restore": false,
  "restore_model": "gpt-4.1-mini",
  "restore_batch_size": 20
}
```

Response 200: Transcript

### POST /api/align
Word-level alignment. Mirrors `podx-align`.

Request:
```json
{
  "transcript": {}
}
```

Response 200: Transcript

### POST /api/deepcast
Generate analysis. Mirrors `podx-deepcast` unified JSON.

Request:
```json
{
  "transcript": {},
  "model": "gpt-4.1",
  "temperature": 0.2,
  "type": "interview_guest_focused",
  "extract_markdown": true
}
```

Response 200: Deepcast unified JSON

### POST /api/agreement
Compare two analyses.

Request:
```json
{
  "a": { "markdown": "..." },
  "b": { "markdown": "..." },
  "model": "gpt-4.1"
}
```

Response 200:
```json
{
  "agreement_score": 84,
  "unique_to_a": ["..."],
  "unique_to_b": ["..."],
  "contradictions": ["..."],
  "summary": "..."
}
```

---

## Jobs & Progress (optional)

Async POST with `?async=true` returns:
```json
{ "job_id": "uuid", "status": "queued" }
```

- GET /api/jobs/{job_id} → { status, progress, result?, error? }
- WS /ws/progress → { job_id, status, progress }

---

## Errors

Non-2xx responses:
```json
{ "error": { "code": "BadRequest|NotFound|Internal", "message": "..." } }
```

---

## Minimal server mapping (reference)

- transcribe → spawn `podx-transcribe` (stdin AudioMeta)
- preprocess → spawn `podx-preprocess`
- align → spawn `podx-align`
- deepcast → spawn `podx-deepcast`
- agreement → spawn `podx-agreement`

---

## Examples

- Transcribe (local):
```bash
curl -sS -X POST http://localhost:8787/api/transcribe \
  -H 'Content-Type: application/json' \
  -d '{"audio_path":"/abs/.../audio.wav","model":"large-v3","preset":"balanced"}'
```

- Preprocess + restore:
```bash
curl -sS -X POST http://localhost:8787/api/preprocess \
  -H 'Content-Type: application/json' \
  -d @payload.json
```

- Deepcast:
```bash
curl -sS -X POST http://localhost:8787/api/deepcast \
  -H 'Content-Type: application/json' \
  -d @deepcast_request.json
```

- Agreement:
```bash
curl -sS -X POST http://localhost:8787/api/agreement \
  -H 'Content-Type: application/json' \
  -d '{"a":{"markdown":"..."},"b":{"markdown":"..."}}'
```

---

## Contract changes

- Additive only until 1.0. Fields may be added; existing fields remain.
- Breaking changes bump the contract version.
