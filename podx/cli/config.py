"""CLI command for configuration management.

Simple `defaults`-style interface:
  podx config              List all settings
  podx config get KEY      Get a setting's value
  podx config set KEY VAL  Set a setting's value
"""

import os
import sys
from pathlib import Path
from typing import Optional

import click

from podx.domain.exit_codes import ExitCode

# Configuration keys with metadata
CONFIG_KEYS = {
    # Non-secret settings
    "output-dir": {
        "description": "Where files are saved ('cwd' for current directory)",
        "secret": False,
        "default": "cwd",
    },
    "transcribe-model": {
        "description": "Default transcription model",
        "secret": False,
        "default": "large-v3",
    },
    "analyze-model": {
        "description": "Default analysis model",
        "secret": False,
        "default": "gpt-4o-mini",
    },
    "language": {
        "description": "Default language for transcription",
        "secret": False,
        "default": "auto",
    },
    # Secret settings (API keys)
    "openai-api-key": {
        "description": "OpenAI API key",
        "secret": True,
        "env_var": "OPENAI_API_KEY",
    },
    "anthropic-api-key": {
        "description": "Anthropic API key",
        "secret": True,
        "env_var": "ANTHROPIC_API_KEY",
    },
    "huggingface-token": {
        "description": "HuggingFace token for diarization",
        "secret": True,
        "env_var": "HUGGINGFACE_TOKEN",
    },
    "notion-token": {
        "description": "Notion API token",
        "secret": True,
        "env_var": "NOTION_TOKEN",
    },
    "notion-database-id": {
        "description": "Notion database ID",
        "secret": False,
        "default": "",
    },
}


def _get_config_dir() -> Path:
    """Get config directory path."""
    return Path.home() / ".config" / "podx"


def _get_config_file() -> Path:
    """Get config file path."""
    return _get_config_dir() / "config.yaml"


def _get_env_file() -> Path:
    """Get env file path for secrets."""
    return _get_config_dir() / "env.sh"


def _load_config() -> dict[str, str]:
    """Load config from YAML file."""
    config_file = _get_config_file()
    if not config_file.exists():
        return {}

    config = {}
    for line in config_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            config[key.strip()] = value.strip()
    return config


def _save_config(config: dict[str, str]) -> None:
    """Save config to YAML file."""
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# PodX Configuration", ""]
    for key, value in config.items():
        lines.append(f"{key}: {value}")
    lines.append("")

    _get_config_file().write_text("\n".join(lines))


def _load_secrets() -> dict[str, str]:
    """Load secrets from env file."""
    env_file = _get_env_file()
    if not env_file.exists():
        return {}

    secrets = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            # Parse: export KEY="value" or KEY="value"
            if line.startswith("export "):
                line = line[7:]
            key, value = line.split("=", 1)
            # Remove quotes
            value = value.strip().strip('"').strip("'")
            secrets[key.strip()] = value
    return secrets


def _save_secrets(secrets: dict[str, str]) -> None:
    """Save secrets to env file."""
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# PodX API Keys",
        "# Source this file: source ~/.config/podx/env.sh",
        "",
    ]
    for key, value in secrets.items():
        lines.append(f'export {key}="{value}"')
    lines.append("")

    env_file = _get_env_file()
    env_file.write_text("\n".join(lines))
    os.chmod(env_file, 0o600)


def _get_value(key: str) -> Optional[str]:
    """Get a config value by key."""
    key_info = CONFIG_KEYS.get(key)
    if not key_info:
        return None

    if key_info.get("secret"):
        # Check environment first, then env file
        env_var = key_info.get("env_var", "")
        value = os.environ.get(env_var)
        if value:
            return value
        secrets = _load_secrets()
        return secrets.get(env_var)
    else:
        config = _load_config()
        return config.get(key, key_info.get("default", ""))


def _set_value(key: str, value: str) -> bool:
    """Set a config value. Returns True on success."""
    key_info = CONFIG_KEYS.get(key)
    if not key_info:
        return False

    if key_info.get("secret"):
        env_var = key_info.get("env_var", "")
        secrets = _load_secrets()
        secrets[env_var] = value
        _save_secrets(secrets)
    else:
        config = _load_config()
        config[key] = value
        _save_config(config)

    return True


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """View and manage PodX configuration.

    \b
    Usage:
      podx config                 List all settings
      podx config get KEY         Get a setting's value
      podx config set KEY VALUE   Set a setting's value

    \b
    Settings:
      output-dir          Where files are saved ('cwd' for current directory)
      transcribe-model    Default transcription model
      analyze-model       Default analysis model
      language            Default language for transcription

    \b
    API Keys:
      openai-api-key      OpenAI API key
      anthropic-api-key   Anthropic API key
      huggingface-token   HuggingFace token
      notion-token        Notion API token
      notion-database-id  Notion database ID

    \b
    Examples:
      podx config
      podx config get analyze-model
      podx config set analyze-model gpt-4o
      podx config set openai-api-key sk-...
    """
    if ctx.invoked_subcommand is None:
        # No subcommand - list all settings
        _list_all()


def _list_all():
    """List all configuration settings."""
    config = _load_config()
    secrets = _load_secrets()

    # Simple tabular output without Rich
    click.echo()
    click.echo(f"{'Setting':<22}{'Value':<20}{'Description'}")
    click.echo("-" * 70)

    for key, info in CONFIG_KEYS.items():
        if info.get("secret"):
            env_var = info.get("env_var", "")
            # Check env first, then file - only show [set] or [not set]
            if os.environ.get(env_var) or secrets.get(env_var):
                value = "[set]"
            else:
                value = "[not set]"
        else:
            # Non-secret: show actual value or [undefined]
            value = config.get(key, info.get("default", ""))
            if not value:
                value = "[undefined]"

        click.echo(f"{key:<22}{value:<20}{info['description']}")

    click.echo()


@main.command()
@click.argument("key")
def get(key: str):
    """Get a configuration value.

    \b
    Examples:
      podx config get analyze-model
      podx config get openai-api-key
    """
    if key not in CONFIG_KEYS:
        click.echo(f"podx config: unknown key '{key}'", err=True)
        sys.exit(ExitCode.USER_ERROR)

    key_info = CONFIG_KEYS[key]
    value = _get_value(key)

    if key_info.get("secret"):
        # Don't show actual secret value
        if value:
            click.echo("[set]")
        else:
            click.echo("[not set]")
    else:
        if value:
            click.echo(value)
        else:
            click.echo("[undefined]")


@main.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str):
    """Set a configuration value.

    \b
    Examples:
      podx config set analyze-model gpt-4o
      podx config set output-dir ~/Podcasts
      podx config set openai-api-key sk-abc123...
    """
    if key not in CONFIG_KEYS:
        click.echo(f"podx config: unknown key '{key}'", err=True)
        sys.exit(ExitCode.USER_ERROR)

    if _set_value(key, value):
        key_info = CONFIG_KEYS[key]
        if key_info.get("secret"):
            click.echo(f"{key} = [set]")
            env_file = _get_env_file()
            click.echo(f"To load: source {env_file}")
        else:
            click.echo(f"{key} = {value}")
    else:
        click.echo(f"podx config: failed to set {key}", err=True)
        sys.exit(ExitCode.PROCESSING_ERROR)


if __name__ == "__main__":
    main()
