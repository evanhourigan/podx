"""Pipeline configuration and result models."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ..enums import AnalysisType, ASRPreset, ASRProvider, AudioFormat



@dataclass
class PipelineConfig:
    """Pipeline execution configuration.

    This configuration controls which steps run and with what parameters.
    Field names match the CLI/services API for consistency.
    """

    # Source configuration
    show: Optional[str] = None
    rss_url: Optional[str] = None
    youtube_url: Optional[str] = None
    date: Optional[str] = None
    title_contains: Optional[str] = None

    # Working directory
    workdir: Optional[Path] = None

    # Audio configuration (use simple name for API consistency)
    fmt: Union[str, AudioFormat] = "wav16"  # Audio format: wav16, mp3, aac

    # Transcription configuration (match CLI names)
    model: str = "base"  # ASR model name
    compute: str = "int8"  # Compute type: int8, float16, float32
    asr_provider: Union[str, ASRProvider, None] = None  # ASR provider: auto, local, openai, hf
    preset: Union[str, ASRPreset, None] = None  # ASR preset: balanced, precision, recall

    # Pipeline flags
    align: bool = False
    diarize: bool = False
    preprocess: bool = False
    restore: bool = False
    deepcast: bool = False
    dual: bool = False
    no_consensus: bool = False

    # Deepcast configuration
    deepcast_model: str = "gpt-4"
    deepcast_temp: float = 0.7
    analysis_type: Union[str, AnalysisType, None] = None  # Analysis type for deepcast
    extract_markdown: bool = False
    deepcast_pdf: bool = False

    # Notion configuration
    notion: bool = False
    notion_db: Optional[str] = None
    podcast_prop: str = "Podcast"
    date_prop: str = "Date"
    episode_prop: str = "Episode"
    model_prop: str = "Model"
    asr_prop: str = "ASR"
    append_content: bool = False

    # Execution flags
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
            config.preset = ASRPreset.RECALL
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.dual = False
        elif level == 3:
            config.preset = ASRPreset.PRECISION
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.dual = False
        elif level == 4:
            config.preset = ASRPreset.BALANCED
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.dual = False
        elif level == 5:
            config.dual = True
            config.preprocess = True
            config.restore = True
            config.deepcast = True
            config.preset = config.preset or ASRPreset.BALANCED

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

    workdir: Path  # Match services API naming
    steps_completed: list[str] = field(default_factory=list)  # Match services API
    artifacts: Dict[str, str] = field(default_factory=dict)  # Match services API (str paths)
    duration: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary.

        Returns:
            Dictionary representation of pipeline result
        """
        return {
            "workdir": str(self.workdir),
            "steps_completed": self.steps_completed,
            "artifacts": self.artifacts,
            "duration": self.duration,
            "errors": self.errors,
        }
