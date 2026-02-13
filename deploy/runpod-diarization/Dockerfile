# RunPod Diarization Handler
# Based on CUDA 12.4 with Python 3.11

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# WhisperX must be installed from GitHub
# pyannote.audio can pull in an incompatible torchvision, so we
# reinstall the version matching the base image's PyTorch 2.4.0 last.
RUN pip install --no-cache-dir \
    runpod \
    pyannote.audio \
    git+https://github.com/m-bain/whisperx.git \
    && pip install --no-cache-dir torchvision==0.19.0 \
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
