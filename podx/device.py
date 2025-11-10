"""Device detection and optimization for ML workloads.

Auto-detects the best available compute device for transcription and diarization:
- Apple Silicon: MPS (Metal Performance Shaders) for M1/M2/M3 - PyTorch only
- NVIDIA: CUDA for GPU acceleration
- Fallback: CPU

Note: Different libraries have different device support:
- CTranslate2 (faster-whisper): Only supports CUDA and CPU (no MPS)
- PyTorch (WhisperX): Supports MPS, CUDA, and CPU
"""

import platform
from typing import Literal, Tuple

from .logging import get_logger

logger = get_logger(__name__)

DeviceType = Literal["mps", "cuda", "cpu"]


def detect_device_for_ctranslate2() -> Literal["cuda", "cpu"]:
    """Detect the best available device for CTranslate2 (faster-whisper).

    CTranslate2 only supports CUDA and CPU (no MPS support).

    Returns:
        Device type: "cuda" (NVIDIA) or "cpu"
    """
    # Check for NVIDIA CUDA
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(
                "Detected NVIDIA CUDA GPU for transcription",
                device="cuda",
                gpu_name=device_name,
                backend="CTranslate2",
            )
            return "cuda"
    except (ImportError, AttributeError):
        pass

    # Fallback to CPU
    logger.info(
        "Using CPU for transcription (CTranslate2 doesn't support MPS)",
        device="cpu",
        backend="CTranslate2",
    )
    return "cpu"


def detect_device_for_pytorch() -> DeviceType:
    """Detect the best available device for PyTorch (WhisperX).

    PyTorch supports MPS, CUDA, and CPU.

    Returns:
        Device type: "mps" (Apple Silicon), "cuda" (NVIDIA), or "cpu"
    """
    # Check for Apple Silicon MPS
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            import torch
            if torch.backends.mps.is_available():
                logger.info(
                    "Detected Apple Silicon with MPS support for diarization",
                    device="mps",
                    platform=platform.machine(),
                    backend="PyTorch",
                )
                return "mps"
        except (ImportError, AttributeError):
            # torch not available or MPS not supported
            pass

    # Check for NVIDIA CUDA
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(
                "Detected NVIDIA CUDA GPU for diarization",
                device="cuda",
                gpu_name=device_name,
                backend="PyTorch",
            )
            return "cuda"
    except (ImportError, AttributeError):
        pass

    # Fallback to CPU
    logger.info(
        "Using CPU for diarization (no GPU acceleration detected)",
        device="cpu",
        backend="PyTorch",
    )
    return "cpu"


def detect_device() -> DeviceType:
    """Detect the best available compute device (general purpose).

    DEPRECATED: Use detect_device_for_ctranslate2() or detect_device_for_pytorch()
    for library-specific detection.

    Returns:
        Device type: "mps" (Apple Silicon), "cuda" (NVIDIA), or "cpu"
    """
    return detect_device_for_pytorch()


def get_optimal_compute_type(device: Literal["cuda", "cpu"]) -> str:
    """Get optimal compute type for faster-whisper (CTranslate2) based on device.

    Args:
        device: Device type ("cuda" or "cpu" - MPS not supported by CTranslate2)

    Returns:
        Optimal compute_type string for faster-whisper
    """
    if device == "cuda":
        # NVIDIA: int8_float16 works well for most GPUs
        return "int8_float16"
    else:
        # CPU: int8 for performance
        return "int8"


def get_device_info_for_ctranslate2() -> Tuple[Literal["cuda", "cpu"], str]:
    """Get device and optimal compute type for CTranslate2 (faster-whisper).

    Returns:
        Tuple of (device_type, compute_type)
    """
    device = detect_device_for_ctranslate2()
    compute_type = get_optimal_compute_type(device)
    return device, compute_type


def get_device_info() -> Tuple[DeviceType, str]:
    """Get device and optimal compute type in one call (general purpose).

    DEPRECATED: Use get_device_info_for_ctranslate2() for transcription.

    Returns:
        Tuple of (device_type, compute_type)
    """
    device = detect_device_for_ctranslate2()
    compute_type = get_optimal_compute_type(device)
    return device, compute_type


def log_device_usage(device: DeviceType, compute_type: str, operation: str = "processing"):
    """Log device usage information for transparency.

    Args:
        device: Device being used
        compute_type: Compute type being used
        operation: What operation is being performed (e.g., "transcription")
    """
    device_names = {
        "mps": "Apple Silicon GPU (Metal)",
        "cuda": "NVIDIA GPU (CUDA)",
        "cpu": "CPU",
    }

    logger.info(
        f"Starting {operation}",
        device=device_names.get(device, device),
        compute_type=compute_type,
    )
