"""Enums for the podx domain layer."""

from enum import Enum


class PipelineStep(str, Enum):
    """Pipeline execution steps."""

    FETCH = "fetch"
    TRANSCODE = "transcode"
    TRANSCRIBE = "transcribe"
    ALIGN = "align"
    DIARIZE = "diarize"
    PREPROCESS = "preprocess"
    DEEPCAST = "deepcast"
    EXPORT = "export"
    NOTION = "notion"


class AnalysisType(str, Enum):
    """Deepcast analysis types."""

    INTERVIEW_GUEST_FOCUSED = "interview_guest_focused"
    PANEL_DISCUSSION = "panel_discussion"
    SOLO_COMMENTARY = "solo_commentary"
    GENERAL = "general"
    # Aliases
    HOST_MODERATED_PANEL = "host_moderated_panel"
    COHOST_COMMENTARY = "cohost_commentary"


class ASRProvider(str, Enum):
    """ASR provider backends."""

    AUTO = "auto"
    LOCAL = "local"
    OPENAI = "openai"
    HF = "hf"  # Hugging Face


class AudioFormat(str, Enum):
    """Audio format types."""

    WAV16 = "wav16"
    MP3 = "mp3"
    AAC = "aac"


class ASRPreset(str, Enum):
    """ASR transcription presets."""

    BALANCED = "balanced"
    PRECISION = "precision"
    RECALL = "recall"
