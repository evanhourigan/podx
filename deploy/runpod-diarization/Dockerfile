# RunPod Diarization Handler
# Based on CUDA 12.1 with Python 3.10 for WhisperX compatibility

FROM runpod/pytorch:2.1.0-py3.10-cuda12.1.0-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# WhisperX requires specific versions for compatibility
RUN pip install --no-cache-dir \
    runpod \
    torch==2.1.0 \
    torchaudio==2.1.0 \
    whisperx \
    pyannote.audio \
    && pip cache purge

# Copy handler
COPY handler.py /app/handler.py

# Set environment variables
ENV DEVICE=cuda
ENV PYTHONUNBUFFERED=1

# Pre-download models during build (optional, makes cold starts faster)
# Uncomment if you want models baked into the image (increases image size ~3GB)
# RUN python -c "import whisperx; whisperx.load_align_model('en', 'cpu')"

CMD ["python", "-u", "/app/handler.py"]
