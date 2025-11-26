# Podx Pipeline Flow Diagram

```mermaid
graph TD
    A[podx fetch] -->|EpisodeMeta JSON| B[podx transcode]
    B -->|AudioMeta JSON| C[podx transcribe]
    C -->|Transcript JSON| D[podx align]
    D -->|AlignedTranscript JSON| E[podx diarize]
    C -->|Transcript JSON| F[podx export<br/>📁 writes files]
    D -->|AlignedTranscript JSON| F
    E -->|DiarizedTranscript JSON| F

    %% AI Analysis and Publishing
    C -->|Transcript JSON| G[podx deepcast<br/>📄 writes analysis]
    D -->|AlignedTranscript JSON| G
    E -->|DiarizedTranscript JSON| G
    G -->|DeepcastBrief JSON| H[podx notion<br/>☁️ uploads to Notion]

    %% Invalid flows (shown in red/dashed)
    C -.->|❌ Invalid| E

    %% End state indicators
    F -->|END| F1[📁 Files Created]
    G -->|END| G1[📄 Analysis Files]
    H -->|END| H1[☁️ Notion Page]

    %% Styling
    classDef valid fill:#e1f5fe
    classDef invalid fill:#ffebee,stroke:#f44336,stroke-dasharray: 5 5
    classDef endpoint fill:#f3e5f5
    classDef ai fill:#e8f5e8
    classDef publish fill:#fff3e0
    classDef endstate fill:#f0f0f0,stroke:#666,stroke-dasharray: 3 3

    class A,B,C,D,E valid
    class F,G,H endpoint
    class G ai
    class H publish
    class F1,G1,H1 endstate
```

## Valid Pipeline Flows

### Core Processing Flows

1. **Full pipeline**: fetch → transcode → transcribe → align → diarize → export
2. **Skip diarization**: fetch → transcode → transcribe → align → export
3. **Skip alignment/diarization**: fetch → transcode → transcribe → export

### AI Analysis Flows

4. **AI analysis**: transcribe → deepcast → notion
5. **AI analysis with alignment**: transcribe → align → deepcast → notion
6. **AI analysis with diarization**: transcribe → align → diarize → deepcast → notion

### Combined Flows

7. **Full pipeline with AI**: fetch → transcode → transcribe → align → diarize → export + deepcast → notion
8. **Export + AI**: transcribe → export + deepcast → notion

### Orchestrator Behavior

The `podx run` orchestrator shows steps as sequential (e.g., `export → deepcast`), but both `export` and `deepcast` actually run from the same transcript JSON source. The sequential display is for clarity, but they don't depend on each other's output.

## Invalid Flows

- ❌ transcribe → diarize (diarization requires aligned timestamps)
- ❌ export → anything (export writes files, no JSON output)
- ❌ deepcast → anything (deepcast writes files, no JSON output)
- ❌ notion → anything (notion uploads to database, no JSON output)
- ❌ Any backwards flow (wrong data types)

## Key Dependencies

- **podx diarize** requires **podx align** (needs word-level timestamps)
- **podx deepcast** can accept any transcript JSON (transcribe, align, or diarize output)
- **podx export** can accept any transcript JSON (transcribe, align, or diarize output)
- **podx notion** requires deepcast output (needs structured analysis)
- **podx fetch** starts the pipeline (no input required)
