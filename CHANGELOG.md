# Changelog

## v0.2.0-alpha.1
- ASR provider abstraction (local/openai/hf) with model aliasing
- Presets and expert flags for transcribe; provider-aware interactive
- Schema: asr_provider, preset, decoder_options
- Orchestrator passes provider/preset; preprocess stage with optional restore
- Agreement check CLI; canonical prompt templates; docs updated
