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
    asr_provider: Union[str, ASRProvider, None] = (
        None  # ASR provider: auto, local, openai, hf
    )
    preset: Union[str, ASRPreset, None] = (
        None  # ASR preset: balanced, precision, recall
    )

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
    def from_fidelity(cls, level: int, **kwargs: Any) -> "PipelineConfig":
        """Create configuration from fidelity level (1-5).

        Fidelity levels represent quality/speed tradeoffs:
        - Level 1: Deepcast only (fastest, lowest quality)
        - Level 2: Recall preset + enhancements
        - Level 3: Precision preset + enhancements
        - Level 4: Balanced preset + enhancements (recommended)
        - Level 5: Dual QA mode (slowest, highest quality)

        Fidelity-specific settings override kwargs presets.

        Args:
            level: Fidelity level 1-5
            **kwargs: Additional configuration overrides

        Returns:
            PipelineConfig instance with fidelity settings applied
        """
        # Start with kwargs, then override with fidelity settings
        config_dict = dict(kwargs)

        if level == 1:
            # Level 1: Deepcast only (fastest)
            config_dict.update(
                {
                    "align": False,
                    "diarize": False,
                    "preprocess": False,
                    "restore": False,
                    "deepcast": True,
                    "dual": False,
                }
            )
        elif level == 2:
            # Level 2: Recall preset + enhancements
            config_dict.update(
                {
                    "preset": ASRPreset.RECALL,
                    "preprocess": True,
                    "restore": True,
                    "deepcast": True,
                    "dual": False,
                }
            )
        elif level == 3:
            # Level 3: Precision preset + enhancements
            config_dict.update(
                {
                    "preset": ASRPreset.PRECISION,
                    "preprocess": True,
                    "restore": True,
                    "deepcast": True,
                    "dual": False,
                }
            )
        elif level == 4:
            # Level 4: Balanced preset + enhancements (recommended)
            config_dict.update(
                {
                    "preset": ASRPreset.BALANCED,
                    "preprocess": True,
                    "restore": True,
                    "deepcast": True,
                    "dual": False,
                }
            )
        elif level == 5:
            # Level 5: Dual QA mode (best quality)
            config_dict.update(
                {
                    "preset": ASRPreset.BALANCED,
                    "dual": True,
                    "preprocess": True,
                    "restore": True,
                    "deepcast": True,
                }
            )
        else:
            raise ValueError(f"Invalid fidelity level: {level}. Must be 1-5.")

        return cls(**config_dict)

    @classmethod
    def from_workflow(cls, workflow: str, **kwargs: Any) -> "PipelineConfig":
        """Create configuration from workflow preset.

        Workflows represent common use cases:
        - "quick": Minimal processing for quick review
        - "analyze": Analysis with alignment for detailed review
        - "publish": Full pipeline with Notion publishing

        Workflow settings override kwargs flags.

        Args:
            workflow: Workflow name ("quick", "analyze", "publish")
            **kwargs: Additional configuration overrides

        Returns:
            PipelineConfig instance with workflow settings applied
        """
        # Start with kwargs, then override with workflow settings
        config_dict = dict(kwargs)

        if workflow == "quick":
            # Quick workflow: Minimal processing
            config_dict.update(
                {
                    "align": False,
                    "diarize": False,
                    "deepcast": False,
                    "extract_markdown": False,
                    "notion": False,
                }
            )
        elif workflow == "analyze":
            # Analyze workflow: Analysis with alignment
            config_dict.update(
                {
                    "align": True,
                    "diarize": False,
                    "deepcast": True,
                    "extract_markdown": True,
                }
            )
        elif workflow == "publish":
            # Publish workflow: Full pipeline with Notion
            config_dict.update(
                {
                    "align": True,
                    "diarize": False,
                    "deepcast": True,
                    "extract_markdown": True,
                    "notion": True,
                }
            )
        else:
            raise ValueError(
                f"Invalid workflow: {workflow}. Must be 'quick', 'analyze', or 'publish'."
            )

        return cls(**config_dict)


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    workdir: Path  # Match services API naming
    steps_completed: list[str] = field(default_factory=list)  # Match services API
    artifacts: Dict[str, str] = field(
        default_factory=dict
    )  # Match services API (str paths)
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
