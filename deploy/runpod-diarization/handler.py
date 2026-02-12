"""RunPod Serverless Handler for Speaker Diarization.

This handler receives audio and transcript segments, runs WhisperX alignment
and pyannote diarization, and returns speaker-labeled segments.

Deploy to RunPod as a custom serverless endpoint.
"""

import base64
import os
import tempfile
from pathlib import Path

import runpod

# GPU device selection
DEVICE = os.getenv("DEVICE", "cuda")

# Lazy-loaded models (persist across requests)
_align_model = None
_align_metadata = None
_diarize_pipeline = None


def get_align_model(language: str = "en"):
    """Load WhisperX alignment model (cached)."""
    global _align_model, _align_metadata

    import whisperx

    if _align_model is None:
        print(f"Loading alignment model for {language}...")
        _align_model, _align_metadata = whisperx.load_align_model(
            language_code=language,
            device=DEVICE
        )
        print("Alignment model loaded")

    return _align_model, _align_metadata


def get_diarize_pipeline():
    """Load pyannote diarization pipeline (cached)."""
    global _diarize_pipeline

    if _diarize_pipeline is None:
        from whisperx.diarize import DiarizationPipeline

        print("Loading diarization pipeline...")
        hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        _diarize_pipeline = DiarizationPipeline(
            use_auth_token=hf_token,
            device=DEVICE
        )
        print("Diarization pipeline loaded")

    return _diarize_pipeline


def sanitize_segments(segments: list) -> list:
    """Filter segments that could cause alignment to fail."""
    sanitized = []

    for seg in segments:
        text = seg.get("text", "").strip()
        start = seg.get("start")
        end = seg.get("end")

        # Skip invalid segments
        if not text or start is None or end is None:
            continue
        if end <= start:
            continue
        if (end - start) < 0.1:  # Too short for alignment
            continue

        # Only keep fields WhisperX expects
        sanitized.append({
            "start": start,
            "end": end,
            "text": text,
        })

    return sanitized


def handler(job: dict) -> dict:
    """RunPod handler for diarization jobs.

    Input:
        audio_base64: Base64-encoded audio file
        transcript_segments: List of {start, end, text} segments
        num_speakers: Optional exact number of speakers
        min_speakers: Optional minimum speakers
        max_speakers: Optional maximum speakers
        language: Language code (default: "en")

    Output:
        segments: List of segments with speaker labels and word timing
    """
    import whisperx
    from whisperx.diarize import assign_word_speakers

    job_input = job.get("input", {})

    # Extract inputs
    audio_base64 = job_input.get("audio_base64")
    transcript_segments = job_input.get("transcript_segments", [])
    num_speakers = job_input.get("num_speakers")
    min_speakers = job_input.get("min_speakers")
    max_speakers = job_input.get("max_speakers")
    language = job_input.get("language", "en")

    if not audio_base64:
        return {"error": "Missing audio_base64"}

    if not transcript_segments:
        return {"error": "Missing transcript_segments"}

    # Decode audio to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        audio_path = Path(f.name)
        f.write(base64.b64decode(audio_base64))

    try:
        # Sanitize segments
        clean_segments = sanitize_segments(transcript_segments)
        if not clean_segments:
            return {"error": "No valid segments after sanitization"}

        print(f"Processing {len(clean_segments)} segments...")

        # Step 1: Load audio
        print("Loading audio...")
        audio_data = whisperx.load_audio(str(audio_path))

        # Step 2: Alignment
        print("Running alignment...")
        model_a, metadata = get_align_model(language)
        aligned_result = whisperx.align(
            clean_segments,
            model_a,
            metadata,
            audio_data,
            device=DEVICE,
            return_char_alignments=False,
        )

        # Step 3: Diarization
        print("Running diarization...")
        diarize_pipeline = get_diarize_pipeline()
        diarized = diarize_pipeline(
            str(audio_path),
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        # Step 4: Assign speakers to words
        print("Assigning speakers...")
        result = assign_word_speakers(diarized, aligned_result)

        # Count speakers
        speakers = set()
        for seg in result.get("segments", []):
            if seg.get("speaker"):
                speakers.add(seg["speaker"])
            for word in seg.get("words", []):
                if word.get("speaker"):
                    speakers.add(word["speaker"])

        print(f"Done! Found {len(speakers)} speakers in {len(result.get('segments', []))} segments")

        return {
            "segments": result.get("segments", []),
            "speakers_count": len(speakers),
        }

    finally:
        # Cleanup temp file
        if audio_path.exists():
            audio_path.unlink()


# Start the serverless worker
runpod.serverless.start({"handler": handler})
