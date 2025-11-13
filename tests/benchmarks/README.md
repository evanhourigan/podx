# PodX Performance Benchmarks

This directory contains performance benchmarks for PodX's core operations.

## Running Benchmarks

### Run all benchmarks
```bash
pytest tests/benchmarks/ --benchmark-only
```

### Run specific benchmark file
```bash
pytest tests/benchmarks/test_preprocessing_benchmarks.py --benchmark-only
```

### Run benchmarks with comparison
```bash
# First run (saves baseline)
pytest tests/benchmarks/ --benchmark-only --benchmark-autosave

# After changes (compares against baseline)
pytest tests/benchmarks/ --benchmark-only --benchmark-compare
```

### Save benchmark results
```bash
pytest tests/benchmarks/ --benchmark-only --benchmark-save=baseline
```

### Compare against specific baseline
```bash
pytest tests/benchmarks/ --benchmark-only --benchmark-compare=baseline
```

## Benchmark Organization

- `test_preprocessing_benchmarks.py` - Transcript preprocessing operations (merge, normalize, etc.)
- `test_export_benchmarks.py` - Export to different formats (TXT, MD, SRT, VTT)
- `test_transcription_benchmarks.py` - Transcription utility functions (model parsing, etc.)
- `test_deepcast_benchmarks.py` - Deepcast utility functions (timestamp formatting, text processing, chunking)
- `test_notion_benchmarks.py` - Notion utility functions (rich text chunking, markdown parsing)

Note: Full transcription and diarization with actual models are not benchmarked yet, as they require audio files and model loading which are expensive operations. Current benchmarks focus on utility functions and data processing.

## Interpreting Results

pytest-benchmark provides several metrics:

- **min/max**: Fastest and slowest execution times
- **mean**: Average execution time
- **stddev**: Standard deviation (consistency)
- **median**: Middle value (less affected by outliers)
- **iqr**: Interquartile range (spread of middle 50%)
- **outliers**: Number of statistical outliers
- **rounds**: Number of measurement rounds
- **iterations**: Total number of function calls

## Baseline Results

Baseline performance metrics on Darwin (macOS) with CPython 3.12, Apple Silicon (M-series).

### Fast Operations (< 1 microsecond)
- **Model parsing**: 62-338 ns (parse_model_and_provider)
- **Timestamp formatting**: 750-960 ns (hhmmss)

### Quick Operations (1-100 microseconds)
- **Text chunking (small)**: 333 ns - 10.9 µs
- **Rich text chunking**: 485 ns - 2.2 µs
- **Markdown parsing (inline)**: 666 ns - 5.6 µs
- **Segment merging (small, 10 segs)**: 2.5 µs
- **Export to TXT/MD**: 4.0-4.2 µs
- **Normalize text (small)**: 15.2 µs
- **Normalize segments (small)**: 21.8 µs
- **Merge segments (medium, 100 segs)**: 24.8 µs

### Medium Operations (100-1000 microseconds)
- **Segments to plain text (small)**: 10.5 µs
- **Markdown to Notion blocks (simple)**: 27.7 µs
- **Split into chunks (various sizes)**: 40.6 µs
- **Rich text chunking (various)**: 49.3 µs
- **Markdown to Notion blocks (complex)**: 51.9 µs
- **Segments to plain text (medium, 100 segs)**: 110.5 µs
- **Normalize text (medium)**: 143.9 µs
- **Normalize segments (medium)**: 220.1 µs
- **Export to SRT/VTT**: 242.7-260.0 µs
- **Merge segments (large, 1000 segs)**: 258.8 µs

### Slower Operations (> 1000 microseconds)
- **Segments to plain text (large, 1000 segs)**: 1.04 ms
- **Normalize text (large)**: 1.38 ms
- **Normalize segments (large)**: 2.23 ms

## Performance Goals

Current performance meets or exceeds our initial targets:

- ✅ **Preprocessing**: 24.8 µs for 100 segments (target: < 50 ms) - **2,000x faster than target**
- ✅ **Export**: 4.0-260 µs for 100 segments (target: < 100 ms) - **400-25,000x faster than target**
- ✅ **Text processing utilities**: Sub-millisecond for most operations

These utility functions are extremely fast and unlikely to be bottlenecks. Performance optimization efforts should focus on:
- Audio transcription (model loading, inference)
- Diarization (WhisperX processing)
- LLM API calls (deepcast)
- Network I/O (fetching, Notion uploads)

## Notes

- Benchmarks use synthetic test data for consistency
- Real-world performance may vary based on:
  - Audio file size and quality
  - Model selection (Whisper variants)
  - Hardware capabilities (CPU/GPU)
  - Network conditions (for API-based operations)
