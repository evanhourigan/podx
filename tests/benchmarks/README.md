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
- More benchmark files will be added for:
  - Transcription (various models/backends)
  - Diarization (WhisperX performance)
  - Deepcast (LLM analysis)
  - Full pipeline end-to-end

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

Baseline performance metrics will be tracked here as we establish them.

### Preprocessing (Medium transcript - 100 segments)
- TBD after initial run

### Export (100 segments)
- TBD after initial run

## Performance Goals

Target performance metrics for future optimization:

- Preprocessing: < 50ms for 100 segments
- Export: < 100ms for 100 segments
- Full pipeline: TBD based on actual workload

## Notes

- Benchmarks use synthetic test data for consistency
- Real-world performance may vary based on:
  - Audio file size and quality
  - Model selection (Whisper variants)
  - Hardware capabilities (CPU/GPU)
  - Network conditions (for API-based operations)
