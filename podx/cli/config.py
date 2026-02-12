"""CLI command for configuration management.

Simple `defaults`-style interface:
  podx config              List all settings
  podx config get KEY      Get a setting's value
  podx config set KEY VAL  Set a setting's value
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.table import Table

from podx.domain.exit_codes import ExitCode

console = Console()

# Configuration keys with metadata
CONFIG_KEYS: Dict[str, Dict[str, Any]] = {
    # Non-secret settings
    "output-dir": {
        "description": "Where files are saved ('cwd' for current directory)",
        "secret": False,
        "default": "cwd",
        "validator": None,  # No validation needed
    },
    "transcribe-model": {
        "description": "Default transcription model",
        "secret": False,
        "default": "local:large-v3-turbo",
        "validator": "asr_model",
    },
    "analyze-model": {
        "description": "Default analysis model",
        "secret": False,
        "default": "openai:gpt-5.2",
        "validator": "llm_model",
    },
    "language": {
        "description": "Default language for transcription",
        "secret": False,
        "default": "auto",
        "validator": "language",
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
        "env_var": "NOTION_DATABASE_ID",
        "validator": None,  # No validation needed
    },
    # RunPod cloud settings
    "runpod-api-key": {
        "description": "RunPod API key for cloud processing",
        "secret": True,
        "env_var": "RUNPOD_API_KEY",
    },
    "runpod-endpoint-id": {
        "description": "RunPod endpoint ID for transcription",
        "secret": True,
        "env_var": "RUNPOD_ENDPOINT_ID",
    },
    "runpod-diarize-endpoint-id": {
        "description": "RunPod endpoint ID for diarization",
        "secret": True,
        "env_var": "RUNPOD_DIARIZE_ENDPOINT_ID",
    },
    # Cloudflare R2 storage settings
    "r2-account-id": {
        "description": "Cloudflare account ID for R2",
        "secret": False,
        "default": "",
        "env_var": "R2_ACCOUNT_ID",
    },
    "r2-bucket-name": {
        "description": "R2 bucket name for audio uploads",
        "secret": False,
        "default": "",
        "env_var": "R2_BUCKET_NAME",
    },
    "r2-access-key-id": {
        "description": "R2 API token access key ID",
        "secret": True,
        "env_var": "R2_ACCESS_KEY_ID",
    },
    "r2-secret-access-key": {
        "description": "R2 API token secret access key",
        "secret": True,
        "env_var": "R2_SECRET_ACCESS_KEY",
    },
}


def _validate_value(key: str, value: str) -> tuple[bool, str]:
    """Validate a config value. Returns (is_valid, error_message)."""
    key_info = CONFIG_KEYS.get(key)
    if not key_info:
        return False, f"Unknown config key '{key}'"

    validator = key_info.get("validator")
    if not validator:
        return True, ""

    if validator == "asr_model":
        from podx.ui.prompts import validate_asr_model

        if not validate_asr_model(value):
            return False, (
                f"Invalid ASR model '{value}'. " "Run 'podx models' to see available models."
            )
    elif validator == "llm_model":
        from podx.ui.prompts import validate_llm_model

        if not validate_llm_model(value):
            return False, (
                f"Invalid LLM model '{value}'. " "Run 'podx models' to see available models."
            )
    elif validator == "language":
        from podx.ui.prompts import validate_language

        if not validate_language(value):
            return False, (
                f"Invalid language code '{value}'. "
                "Use 'auto' or ISO 639-1 codes (e.g., en, es, fr)."
            )

    return True, ""


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
def main(ctx: click.Context) -> None:
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
      podx config set analyze-model openai:gpt-4o
      podx config set openai-api-key sk-...
    """
    if ctx.invoked_subcommand is None:
        # No subcommand - list all settings
        _list_all()


def _list_all() -> None:
    """List all configuration settings."""
    config = _load_config()
    secrets = _load_secrets()

    config_file = _get_config_file()
    console.print(f"\n[bold]PodX Configuration[/bold] ({config_file})\n")

    table = Table(show_header=True, header_style="bold cyan", expand=False)
    table.add_column("Setting", width=20)
    table.add_column("Value", width=25)
    table.add_column("Description")

    for key, info in CONFIG_KEYS.items():
        if info.get("secret"):
            env_var = info.get("env_var", "")
            # Check env first, then file
            if os.environ.get(env_var):
                value = "[green]\\[set][/green]"
            elif secrets.get(env_var):
                value = "[green]\\[set][/green]"
            else:
                value = "[dim]\\[not set][/dim]"
        else:
            value = config.get(key, info.get("default", ""))
            if not value:
                value = "[dim]\\[undefined][/dim]"

        table.add_row(key, value, info["description"])

    console.print(table)
    console.print()


@main.command()
@click.argument("key")
def get(key: str) -> None:
    """Get a configuration value.

    \b
    Examples:
      podx config get analyze-model
      podx config get openai-api-key
    """
    if key not in CONFIG_KEYS:
        console.print(f"[red]Error:[/red] Unknown config key '{key}'")
        console.print("[dim]Run 'podx config' to see all keys[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    key_info = CONFIG_KEYS[key]
    value = _get_value(key)

    if key_info.get("secret"):
        # Don't show actual secret value
        if value:
            console.print("[set]")
        else:
            console.print("[not set]")
    else:
        if value:
            console.print(value)
        else:
            console.print("[not set]")


@main.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str) -> None:
    """Set a configuration value.

    \b
    Examples:
      podx config set analyze-model openai:gpt-4o
      podx config set output-dir ~/Podcasts
      podx config set openai-api-key sk-abc123...
    """
    if key not in CONFIG_KEYS:
        console.print(f"[red]Error:[/red] Unknown config key '{key}'")
        console.print("[dim]Run 'podx config' to see all keys[/dim]")
        sys.exit(ExitCode.USER_ERROR)

    # Validate the value
    is_valid, error_msg = _validate_value(key, value)
    if not is_valid:
        console.print(f"[red]Error:[/red] {error_msg}")
        sys.exit(ExitCode.USER_ERROR)

    if _set_value(key, value):
        key_info = CONFIG_KEYS[key]
        if key_info.get("secret"):
            console.print(f"Set {key} = [hidden]")
            env_file = _get_env_file()
            console.print(f"[dim]To load: source {env_file}[/dim]")
        else:
            console.print(f"Set {key} = {value}")
    else:
        console.print(f"[red]Error:[/red] Failed to set {key}")
        sys.exit(ExitCode.PROCESSING_ERROR)


if __name__ == "__main__":
    main()
