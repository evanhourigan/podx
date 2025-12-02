#!/usr/bin/env python3
"""
Podcast-specific configuration management for customized deepcast analysis.
Allows users to predefine analysis settings for specific podcasts.
"""

import json
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .prompt_templates import PodcastType


class PodcastAnalysisConfig(BaseModel):
    """Configuration for podcast-specific analysis settings."""

    model_config = ConfigDict(extra="ignore")

    # Basic identification
    show_name: str = Field(..., description="Podcast show name (used for matching)")
    show_aliases: list[str] = Field(
        default_factory=list, description="Alternative names for matching"
    )

    # Analysis settings
    podcast_type: PodcastType = Field(
        default=PodcastType.GENERAL, description="Podcast type for analysis"
    )
    deepcast_model: Optional[str] = Field(
        default=None, description="Preferred OpenAI model"
    )
    temperature: Optional[float] = Field(
        default=None, description="Analysis temperature"
    )
    chunk_chars: Optional[int] = Field(
        default=None, description="Chunk size for analysis"
    )

    # Pipeline preferences
    default_flags: Dict[str, bool] = Field(
        default_factory=dict,
        description="Default pipeline flags (align, diarize, deepcast, etc.)",
    )

    # Output preferences
    extract_markdown: bool = Field(default=False, description="Always extract markdown")
    notion_upload: bool = Field(default=False, description="Auto-upload to Notion")

    # Custom settings
    custom_prompt_additions: Optional[str] = Field(
        default=None, description="Additional prompt instructions for this podcast"
    )

    # Metadata
    description: Optional[str] = Field(
        default=None, description="Notes about this configuration"
    )
    created_at: Optional[str] = Field(
        default=None, description="Configuration creation date"
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v


class PodcastConfigManager:
    """Manages podcast-specific configurations."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".podx" / "podcasts"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._configs: Optional[Dict[str, PodcastAnalysisConfig]] = None

    def _load_configs(self) -> Dict[str, PodcastAnalysisConfig]:
        """Load all podcast configurations."""
        if self._configs is not None:
            return self._configs

        configs = {}
        for config_file in self.config_dir.glob("*.json"):
            try:
                config_data = json.loads(config_file.read_text())
                config = PodcastAnalysisConfig(**config_data)
                configs[config.show_name] = config
            except Exception as e:
                print(f"Warning: Failed to load config {config_file}: {e}")

        self._configs = configs
        return configs

    def get_config(self, show_name: str) -> Optional[PodcastAnalysisConfig]:
        """Get configuration for a specific podcast."""
        configs = self._load_configs()

        # Direct match
        if show_name in configs:
            return configs[show_name]

        # Try case-insensitive match
        show_lower = show_name.lower()
        for config in configs.values():
            if config.show_name.lower() == show_lower:
                return config

            # Check aliases
            for alias in config.show_aliases:
                if alias.lower() == show_lower:
                    return config

        return None

    def save_config(self, config: PodcastAnalysisConfig) -> None:
        """Save a podcast configuration."""
        # Update creation date if not set
        if not config.created_at:
            from datetime import datetime

            config.created_at = datetime.now().isoformat()

        # Save to file
        config_file = self.config_dir / f"{self._safe_filename(config.show_name)}.json"
        config_file.write_text(config.model_dump_json(indent=2))

        # Invalidate cache
        self._configs = None

    def delete_config(self, show_name: str) -> bool:
        """Delete a podcast configuration."""
        config_file = self.config_dir / f"{self._safe_filename(show_name)}.json"
        if config_file.exists():
            config_file.unlink()
            self._configs = None
            return True
        return False

    def list_configs(self) -> Dict[str, PodcastAnalysisConfig]:
        """List all podcast configurations."""
        return self._load_configs()

    def _safe_filename(self, show_name: str) -> str:
        """Convert show name to safe filename."""
        import re

        # Replace unsafe characters with underscores
        safe = re.sub(r"[^\w\s-]", "", show_name)
        safe = re.sub(r"[-\s]+", "_", safe)
        return safe.lower()


# Global config manager instance
_config_manager: Optional[PodcastConfigManager] = None


def get_podcast_config_manager() -> PodcastConfigManager:
    """Get the global podcast configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = PodcastConfigManager()
    return _config_manager


def get_podcast_config(show_name: str) -> Optional[PodcastAnalysisConfig]:
    """Get configuration for a specific podcast."""
    return get_podcast_config_manager().get_config(show_name)


# Predefined configurations for popular podcasts
PREDEFINED_CONFIGS = {
    "Lenny's Podcast": PodcastAnalysisConfig(
        show_name="Lenny's Podcast",
        show_aliases=["Lenny's Newsletter", "Lenny Rachitsky"],
        podcast_type=PodcastType.INTERVIEW_GUEST_FOCUSED,
        default_flags={
            "align": True,
            "deepcast": True,
            "extract_markdown": True,
            "notion": True,
        },
        extract_markdown=True,
        notion_upload=True,
        custom_prompt_additions="""
        SPECIAL FOCUS for Lenny's Podcast:
        - This is a product management/growth interview show
        - Prioritize guest insights about product strategy, growth tactics, and career advice
        - Extract specific frameworks, metrics, and methodologies mentioned by guests
        - Include concrete examples and case studies shared by guests
        - Note any tools, books, or resources specifically recommended
        """,
        description="Product management interview podcast focusing on guest expertise",
    ),
    "Lex Fridman Podcast": PodcastAnalysisConfig(
        show_name="Lex Fridman Podcast",
        show_aliases=["Lex Fridman", "Artificial Intelligence Podcast"],
        podcast_type=PodcastType.INTERVIEW_HOST_FOCUSED,
        default_flags={"align": True, "deepcast": True, "extract_markdown": True},
        custom_prompt_additions="""
        SPECIAL FOCUS for Lex Fridman Podcast:
        - Academic/intellectual interview format
        - Capture Lex's thoughtful questions that reveal philosophical frameworks
        - Balance deep technical discussions with human elements
        - Note both technical insights and personal/philosophical reflections
        """,
        description="Long-form intellectual interviews with focus on both host questions and guest insights",
    ),
    "The Tim Ferriss Show": PodcastAnalysisConfig(
        show_name="The Tim Ferriss Show",
        show_aliases=["Tim Ferriss", "Tim Ferris"],
        podcast_type=PodcastType.INTERVIEW_GUEST_FOCUSED,
        default_flags={"align": True, "deepcast": True, "extract_markdown": True},
        custom_prompt_additions="""
        SPECIAL FOCUS for Tim Ferriss Show:
        - Focus heavily on guest's tactics, routines, and specific strategies
        - Extract morning routines, productivity systems, and optimization techniques
        - Prioritize actionable advice and concrete recommendations
        - Note books, tools, and resources that guests swear by
        """,
        description="Performance optimization interviews focusing on guest tactics and strategies",
    ),
    "Y Combinator Podcast": PodcastAnalysisConfig(
        show_name="Y Combinator Podcast",
        show_aliases=["YC Podcast", "Y Combinator"],
        podcast_type=PodcastType.BUSINESS,
        default_flags={"align": True, "deepcast": True, "extract_markdown": True},
        custom_prompt_additions="""
        SPECIAL FOCUS for Y Combinator Podcast:
        - Startup and entrepreneurship focus
        - Extract specific business advice, funding insights, and growth strategies
        - Note market analysis, competitive insights, and operational details
        - Prioritize actionable business intelligence
        """,
        description="Startup and entrepreneurship content with business focus",
    ),
}


def create_predefined_configs() -> None:
    """Create predefined configurations for popular podcasts."""
    manager = get_podcast_config_manager()

    for config in PREDEFINED_CONFIGS.values():
        # Only create if doesn't exist
        if not manager.get_config(config.show_name):
            manager.save_config(config)
