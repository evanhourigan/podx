#!/usr/bin/env python3
"""
Centralized configuration management for podx.

Includes profile management for saving/loading named configuration presets.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
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
    default_asr_model: str = Field(
        default="large-v3-turbo", validation_alias="PODX_DEFAULT_MODEL"
    )
    default_compute: str = Field(
        default="auto", validation_alias="PODX_DEFAULT_COMPUTE"
    )

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(
        default=None, validation_alias="OPENAI_API_KEY"
    )
    openai_model: str = Field(default="gpt-4.1", validation_alias="OPENAI_MODEL")
    openai_temperature: float = Field(
        default=0.2, validation_alias="OPENAI_TEMPERATURE"
    )
    openai_base_url: Optional[str] = Field(
        default=None, validation_alias="OPENAI_BASE_URL"
    )

    # Notion Configuration
    notion_token: Optional[str] = Field(default=None, validation_alias="NOTION_TOKEN")
    notion_db_id: Optional[str] = Field(default=None, validation_alias="NOTION_DB_ID")
    notion_podcast_prop: str = Field(
        default="Podcast", validation_alias="NOTION_PODCAST_PROP"
    )
    notion_date_prop: str = Field(default="Date", validation_alias="NOTION_DATE_PROP")
    notion_episode_prop: str = Field(
        default="Episode", validation_alias="NOTION_EPISODE_PROP"
    )

    # Pipeline Configuration
    max_retries: int = Field(default=3, validation_alias="PODX_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, validation_alias="PODX_RETRY_DELAY")
    chunk_chars: int = Field(default=24000, validation_alias="PODX_CHUNK_CHARS")

    # Pipeline Defaults (can be overridden by podcast-specific configs)
    default_align: bool = Field(default=False, validation_alias="PODX_DEFAULT_ALIGN")
    default_diarize: bool = Field(
        default=False, validation_alias="PODX_DEFAULT_DIARIZE"
    )
    default_deepcast: bool = Field(
        default=False, validation_alias="PODX_DEFAULT_DEEPCAST"
    )
    default_extract_markdown: bool = Field(
        default=False, validation_alias="PODX_DEFAULT_EXTRACT_MARKDOWN"
    )
    default_notion: bool = Field(default=False, validation_alias="PODX_DEFAULT_NOTION")
    default_podcast_type: Optional[str] = Field(
        default=None, validation_alias="PODX_DEFAULT_PODCAST_TYPE"
    )

    # Logging Configuration
    log_level: str = Field(default="WARNING", validation_alias="PODX_LOG_LEVEL")
    log_format: str = Field(default="console", validation_alias="PODX_LOG_FORMAT")

    # Webhook Configuration
    webhook_url: Optional[str] = Field(default=None, validation_alias="PODX_WEBHOOK_URL")
    webhook_secret: Optional[str] = Field(
        default=None, validation_alias="PODX_WEBHOOK_SECRET"
    )

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


# ============================================================================
# Configuration Profiles
# ============================================================================


class ConfigProfile:
    """Named configuration profile for reusable settings.

    Profiles allow users to save common configuration combinations
    and reuse them across commands.
    """

    def __init__(self, name: str, settings: Dict[str, Any], description: str = ""):
        """Initialize configuration profile.

        Args:
            name: Profile name (must be filesystem-safe)
            settings: Dictionary of configuration settings
            description: Optional profile description
        """
        self.name = name
        self.settings = settings
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigProfile":
        """Create profile from dictionary.

        Args:
            data: Profile data dictionary

        Returns:
            ConfigProfile instance
        """
        return cls(
            name=data["name"],
            settings=data.get("settings", {}),
            description=data.get("description", ""),
        )


class ProfileManager:
    """Manage configuration profiles.

    Handles saving, loading, listing, and deleting configuration profiles.
    Profiles are stored as YAML files in ~/.podx/profiles/
    """

    def __init__(self, profile_dir: Optional[Path] = None):
        """Initialize profile manager.

        Args:
            profile_dir: Directory to store profiles (defaults to ~/.podx/profiles)
        """
        self.profile_dir = profile_dir or (Path.home() / ".podx" / "profiles")
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def save(self, profile: ConfigProfile) -> None:
        """Save profile to disk.

        Args:
            profile: Profile to save

        Raises:
            ValueError: If profile name contains invalid characters
        """
        # Validate profile name (filesystem-safe)
        if not profile.name or "/" in profile.name or "\\" in profile.name:
            raise ValueError(
                f"Invalid profile name: {profile.name}. "
                "Name must not contain / or \\ characters."
            )

        profile_file = self.profile_dir / f"{profile.name}.yaml"
        with profile_file.open("w") as f:
            yaml.dump(profile.to_dict(), f, default_flow_style=False, sort_keys=False)

    def load(self, name: str) -> Optional[ConfigProfile]:
        """Load profile from disk.

        Args:
            name: Profile name

        Returns:
            ConfigProfile if found, None otherwise
        """
        profile_file = self.profile_dir / f"{name}.yaml"
        if not profile_file.exists():
            return None

        with profile_file.open("r") as f:
            data = yaml.safe_load(f)

        return ConfigProfile.from_dict(data)

    def list_profiles(self) -> List[str]:
        """List all available profile names.

        Returns:
            List of profile names (sorted alphabetically)
        """
        profiles = [p.stem for p in self.profile_dir.glob("*.yaml")]
        return sorted(profiles)

    def delete(self, name: str) -> bool:
        """Delete profile.

        Args:
            name: Profile name to delete

        Returns:
            True if profile was deleted, False if not found
        """
        profile_file = self.profile_dir / f"{name}.yaml"
        if profile_file.exists():
            profile_file.unlink()
            return True
        return False

    def export_profile(self, name: str) -> Optional[str]:
        """Export profile as YAML string.

        Args:
            name: Profile name to export

        Returns:
            YAML string if profile exists, None otherwise
        """
        profile = self.load(name)
        if profile is None:
            return None

        return yaml.dump(profile.to_dict(), default_flow_style=False, sort_keys=False)

    def import_profile(self, yaml_content: str) -> ConfigProfile:
        """Import profile from YAML string.

        Args:
            yaml_content: YAML string containing profile data

        Returns:
            Imported ConfigProfile

        Raises:
            ValueError: If YAML is invalid or profile data is malformed
        """
        try:
            data = yaml.safe_load(yaml_content)
            profile = ConfigProfile.from_dict(data)
            self.save(profile)
            return profile
        except Exception as e:
            raise ValueError(f"Failed to import profile: {e}") from e

    def install_builtin_profiles(self) -> int:
        """Install built-in profiles to disk.

        Returns:
            Number of profiles installed
        """
        profiles = get_builtin_profiles()
        for profile in profiles:
            self.save(profile)
        return len(profiles)


def get_builtin_profiles() -> List[ConfigProfile]:
    """Get built-in configuration profiles.

    Returns:
        List of built-in profiles (quick, standard, high-quality)
    """
    return [
        ConfigProfile(
            name="quick",
            description="Fast processing with minimal features",
            settings={
                "asr_model": "base",
                "asr_provider": "local",
                "diarize": False,
                "preprocess": False,
                "deepcast": False,
                "export_formats": ["txt"],
            },
        ),
        ConfigProfile(
            name="standard",
            description="Balanced quality and speed",
            settings={
                "asr_model": "medium",
                "asr_provider": "local",
                "diarize": True,
                "preprocess": True,
                "restore_punctuation": True,
                "restore_model": "gpt-4o-mini",
                "deepcast": True,
                "llm_model": "gpt-4o-mini",
                "llm_provider": "openai",
                "export_formats": ["txt", "srt", "md"],
            },
        ),
        ConfigProfile(
            name="high-quality",
            description="Best quality processing with all features",
            settings={
                "asr_model": "large-v3",
                "asr_provider": "local",
                "diarize": True,
                "num_speakers": None,  # Auto-detect
                "preprocess": True,
                "restore_punctuation": True,
                "restore_model": "gpt-4o",
                "deepcast": True,
                "llm_model": "gpt-4o",
                "llm_provider": "openai",
                "export_formats": ["txt", "srt", "vtt", "md", "pdf", "html"],
            },
        ),
    ]


def install_builtin_profiles(profile_dir: Optional[Path] = None) -> int:
    """Install built-in profiles to disk.

    Args:
        profile_dir: Directory to install profiles (defaults to ~/.podx/profiles)

    Returns:
        Number of profiles installed
    """
    manager = ProfileManager(profile_dir)
    profiles = get_builtin_profiles()

    for profile in profiles:
        manager.save(profile)

    return len(profiles)
