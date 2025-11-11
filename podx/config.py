#!/usr/bin/env python3
"""
Centralized configuration management for podx.
"""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PodxConfig(BaseSettings):
    """Main configuration for podx pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # ASR Configuration
    default_asr_model: str = Field(default="large-v3-turbo", validation_alias="PODX_DEFAULT_MODEL")
    default_compute: str = Field(default="auto", validation_alias="PODX_DEFAULT_COMPUTE")

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1", validation_alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.2, validation_alias="OPENAI_TEMPERATURE")
    openai_base_url: Optional[str] = Field(default=None, validation_alias="OPENAI_BASE_URL")

    # Notion Configuration
    notion_token: Optional[str] = Field(default=None, validation_alias="NOTION_TOKEN")
    notion_db_id: Optional[str] = Field(default=None, validation_alias="NOTION_DB_ID")
    notion_podcast_prop: str = Field(default="Podcast", validation_alias="NOTION_PODCAST_PROP")
    notion_date_prop: str = Field(default="Date", validation_alias="NOTION_DATE_PROP")
    notion_episode_prop: str = Field(default="Episode", validation_alias="NOTION_EPISODE_PROP")

    # Pipeline Configuration
    max_retries: int = Field(default=3, validation_alias="PODX_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, validation_alias="PODX_RETRY_DELAY")
    chunk_chars: int = Field(default=24000, validation_alias="PODX_CHUNK_CHARS")

    # Pipeline Defaults (can be overridden by podcast-specific configs)
    default_align: bool = Field(default=False, validation_alias="PODX_DEFAULT_ALIGN")
    default_diarize: bool = Field(default=False, validation_alias="PODX_DEFAULT_DIARIZE")
    default_deepcast: bool = Field(default=False, validation_alias="PODX_DEFAULT_DEEPCAST")
    default_extract_markdown: bool = Field(
        default=False, validation_alias="PODX_DEFAULT_EXTRACT_MARKDOWN"
    )
    default_notion: bool = Field(default=False, validation_alias="PODX_DEFAULT_NOTION")
    default_podcast_type: Optional[str] = Field(
        default=None, validation_alias="PODX_DEFAULT_PODCAST_TYPE"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", validation_alias="PODX_LOG_LEVEL")
    log_format: str = Field(default="console", validation_alias="PODX_LOG_FORMAT")

    @field_validator("openai_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("OpenAI temperature must be between 0.0 and 2.0")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        valid_formats = {"console", "json"}
        if v.lower() not in valid_formats:
            raise ValueError(f"Log format must be one of: {valid_formats}")
        return v.lower()


# Global config instance
_config: Optional[PodxConfig] = None


def get_config() -> PodxConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = PodxConfig()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
