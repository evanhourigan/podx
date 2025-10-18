"""Pipeline configuration and result models."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set

from ..enums import (
    AnalysisType,
    ASRPreset,
    ASRProvider,
    AudioFormat,
    PipelineStep,
)


@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""

    # Source configuration
    show: Optional[str] = None
    rss_url: Optional[str] = None
    youtube_url: Optional[str] = None
    date: Optional[str] = None
    title_contains: Optional[str] = None

    # Working directory
    workdir: Optional[Path] = None

    # Audio configuration
    audio_format: AudioFormat = AudioFormat.WAV16

    # ASR configuration
    asr_provider: ASRProvider = ASRProvider.AUTO
    asr_model: str = "medium.en"
    asr_preset: Optional[ASRPreset] = None
    asr_compute: str = "int8"

    # Enhancement flags
    align: bool = False
    diarize: bool = False
    preprocess: bool = False
    restore: bool = False

    # Analysis configuration
    deepcast: bool = False
    deepcast_model: str = "gpt-4"
    deepcast_temp: float = 0.7
    deepcast_type: Optional[AnalysisType] = None

    # Dual mode (precision + recall)
    dual: bool = False
    no_consensus: bool = False

    # Export configuration
    extract_markdown: bool = False
    deepcast_pdf: bool = False

    # Publishing configuration
    notion: bool = False
    notion_db: Optional[str] = None
    podcast_prop: str = "Podcast"
    date_prop: str = "Date"
    episode_prop: str = "Episode"
    model_prop: str = "Model"
    asr_prop: str = "ASR"
    append_content: bool = False

    # Workflow configuration
    workflow: Optional[str] = None
    fidelity: Optional[str] = None

    # Other options
    verbose: bool = False
    clean: bool = False
    no_keep_audio: bool = False

    @classmethod
    def from_fidelity(cls, level: int, **kwargs) -> "PipelineConfig":
        """Create config from fidelity preset (1-5).

        Args:
            level: Fidelity level 1-5
                1: Deepcast only (fastest)
                2: Recall preset + preprocess + restore + deepcast
                3: Precision preset + preprocess + restore + deepcast
                4: Balanced preset + preprocess + restore + deepcast (recommended)
                5: Dual QA (precision + recall) + preprocess + restore (best quality)
            **kwargs: Additional configuration overrides

        Returns:
            PipelineConfig instance with fidelity settings applied
        """
        config = cls(**kwargs)

        if level == 1:
            config.align = False
            config.diarize = False
            config.preprocess = False
            config.dual = False
            config.deepcast = True
        elif level == 2:
            config.asr_preset = ASRPreset.RECALL
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.dual = False
        elif level == 3:
            config.asr_preset = ASRPreset.PRECISION
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.dual = False
        elif level == 4:
            config.asr_preset = ASRPreset.BALANCED
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.dual = False
        elif level == 5:
            config.dual = True
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.asr_preset = config.asr_preset or ASRPreset.BALANCED

        return config

    @classmethod
    def from_workflow(cls, workflow_name: str, **kwargs) -> "PipelineConfig":
        """Create config from workflow preset.

        Args:
            workflow_name: Workflow name (quick, analyze, publish)
            **kwargs: Additional configuration overrides

        Returns:
            PipelineConfig instance with workflow settings applied
        """
        config = cls(**kwargs)

        if workflow_name == "quick":
            config.align = False
            config.diarize = False
            config.deepcast = False
            config.extract_markdown = False
            config.notion = False
        elif workflow_name == "analyze":
            config.align = True
            config.diarize = False
            config.deepcast = True
            config.extract_markdown = True
        elif workflow_name == "publish":
            config.align = True
            config.diarize = False
            config.deepcast = True
            config.extract_markdown = True
            config.notion = True

        return config


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    working_dir: Path
    completed_steps: Set[PipelineStep] = field(default_factory=set)
    artifacts: Dict[str, Path] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "working_dir": str(self.working_dir),
            "completed_steps": [step.value for step in self.completed_steps],
            "artifacts": {k: str(v) for k, v in self.artifacts.items()},
            "metadata": self.metadata,
            "success": self.success,
            "error": self.error,
        }
