#!/usr/bin/env python3
"""Setup wizard for new PodX users.

Simple interactive setup that checks requirements and configures API keys.
"""

import os
import subprocess
import sys
from pathlib import Path

import click


def _check_command(cmd: str) -> tuple[bool, str]:
    """Check if a command is available and get its version."""
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip().split("\n")[0] if result.stdout else "unknown"
        return True, version
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def _check_requirements() -> bool:
    """Check system requirements. Returns True if all required deps are present."""
    click.echo()
    click.echo("Checking requirements...")
    click.echo()

    all_good = True

    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 9):
        click.echo(f"  [ok] Python {py_version}")
    else:
        click.echo(f"  [MISSING] Python {py_version} (requires 3.9+)")
        all_good = False

    # FFmpeg (required)
    ffmpeg_ok, ffmpeg_ver = _check_command("ffmpeg")
    if ffmpeg_ok:
        click.echo(f"  [ok] FFmpeg {ffmpeg_ver[:30]}")
    else:
        click.echo("  [MISSING] FFmpeg (required)")
        click.echo("      Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
        all_good = False

    # yt-dlp (optional)
    ytdlp_ok, ytdlp_ver = _check_command("yt-dlp")
    if ytdlp_ok:
        click.echo(f"  [ok] yt-dlp {ytdlp_ver[:30]}")
    else:
        click.echo("  [optional] yt-dlp not found (for YouTube downloads)")
        click.echo("      Install: pip install yt-dlp")

    click.echo()

    if not all_good:
        click.echo("Missing required dependencies. Install them and run 'podx init' again.")
        click.echo()

    return all_good


def _configure_output_dir() -> str:
    """Configure output directory."""
    click.echo("Where should PodX save files?")
    click.echo()
    click.echo("  1) Current working directory")
    click.echo("     Files saved relative to wherever you run podx.")
    click.echo()
    click.echo("  2) Fixed directory")
    click.echo("     Files always saved to one location.")
    click.echo()

    while True:
        choice = input("Choice [1]: ").strip() or "1"
        if choice == "1":
            return "cwd"
        elif choice == "2":
            default_path = str(Path.home() / "Podcasts")
            path = input(f"Enter directory path [{default_path}]: ").strip() or default_path
            path = os.path.expanduser(path)
            # Create directory if needed
            Path(path).mkdir(parents=True, exist_ok=True)
            click.echo(f"  Created: {path}")
            return path
        else:
            click.echo("  Please enter 1 or 2")


def _configure_api_keys() -> dict[str, str]:
    """Configure API keys."""
    click.echo()
    click.echo("Configure API keys (all optional, can be added later)")
    click.echo()

    keys = {}

    # OpenAI
    click.echo("OpenAI - for cloud transcription and GPT analysis")
    click.echo("Get key: https://platform.openai.com/api-keys")
    key = input("Enter key (or Enter to skip): ").strip()
    if key:
        keys["OPENAI_API_KEY"] = key
        click.echo("  Saved")
    else:
        click.echo("  Skipped")
    click.echo()

    # Anthropic
    click.echo("Anthropic - for Claude analysis models")
    click.echo("Get key: https://console.anthropic.com/settings/keys")
    key = input("Enter key (or Enter to skip): ").strip()
    if key:
        keys["ANTHROPIC_API_KEY"] = key
        click.echo("  Saved")
    else:
        click.echo("  Skipped")
    click.echo()

    # HuggingFace
    click.echo("HuggingFace - for improved speaker diarization")
    click.echo("Get token: https://huggingface.co/settings/tokens")
    key = input("Enter token (or Enter to skip): ").strip()
    if key:
        keys["HUGGINGFACE_TOKEN"] = key
        click.echo("  Saved")
    else:
        click.echo("  Skipped")
    click.echo()

    # Notion (ask first)
    setup_notion = input("Set up Notion integration? (y/N): ").strip().lower()
    if setup_notion == "y":
        click.echo()
        click.echo("Notion - for publishing analyses")
        click.echo("Get token: https://www.notion.so/my-integrations")
        key = input("Enter token (or Enter to skip): ").strip()
        if key:
            keys["NOTION_TOKEN"] = key
            click.echo("  Saved")

        db_id = input("Enter database ID (or Enter to skip): ").strip()
        if db_id:
            keys["NOTION_DATABASE_ID"] = db_id
            click.echo("  Saved")
        else:
            click.echo("  Skipped")
        click.echo()

    return keys


def _save_config(output_dir: str, api_keys: dict[str, str]) -> Path:
    """Save configuration to config file."""
    config_dir = Path.home() / ".config" / "podx"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"

    # Build config content
    lines = [
        "# PodX Configuration",
        "# Generated by 'podx init'",
        "",
        f"output_dir: {output_dir}",
        "transcribe_model: large-v3",
        "analyze_model: gpt-4o-mini",
        "language: auto",
        "",
    ]

    # Add API keys as comments (actual keys should be in environment)
    if api_keys:
        lines.append("# API keys configured:")
        for key in api_keys:
            lines.append(f"#   {key}: [set]")
        lines.append("")

    config_file.write_text("\n".join(lines))

    # Also create shell profile additions
    env_file = config_dir / "env.sh"
    if api_keys:
        env_lines = [
            "# PodX API Keys",
            "# Source this file: source ~/.config/podx/env.sh",
            "",
        ]
        for key, value in api_keys.items():
            env_lines.append(f'export {key}="{value}"')
        env_lines.append("")
        env_file.write_text("\n".join(env_lines))
        os.chmod(env_file, 0o600)  # Secure permissions

    return config_file


@click.command()
def main() -> None:
    """Setup wizard for new PodX users.

    Interactive setup that:
      1. Checks system requirements
      2. Configures output directory
      3. Sets up API keys (optional)

    No options - purely interactive.

    \b
    Examples:
      podx init
    """
    # Welcome
    click.echo()
    click.echo("=" * 40)
    click.echo("  Welcome to PodX!")
    click.echo("=" * 40)

    # Step 1: Check requirements
    if not _check_requirements():
        sys.exit(1)

    # Step 2: Output directory
    output_dir = _configure_output_dir()

    # Step 3: API keys
    api_keys = _configure_api_keys()

    # Save configuration
    config_file = _save_config(output_dir, api_keys)

    # Show summary
    click.echo()
    click.echo("=" * 40)
    click.echo("  Setup complete!")
    click.echo("=" * 40)
    click.echo()

    click.echo(f"Configuration saved to: {config_file}")
    if output_dir == "cwd":
        click.echo("Output directory: current working directory")
    else:
        click.echo(f"Output directory: {output_dir}")

    # API key status
    configured = []
    not_configured = []
    for name, label in [
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("HUGGINGFACE_TOKEN", "HuggingFace"),
        ("NOTION_TOKEN", "Notion"),
    ]:
        if name in api_keys:
            configured.append(label)
        else:
            not_configured.append(label)

    if configured:
        click.echo(f"API keys: {', '.join(configured)} [set]")
    if not_configured:
        click.echo(f"Not configured: {', '.join(not_configured)} (optional)")

    # Load API keys instruction
    if api_keys:
        env_file = Path.home() / ".config" / "podx" / "env.sh"
        click.echo()
        click.echo("To load API keys, run:")
        click.echo(f"  source {env_file}")
        click.echo("Or add this line to your ~/.zshrc or ~/.bashrc")

    # Next steps
    click.echo()
    click.echo("Get started:")
    click.echo('  podx fetch --show "Lex Fridman"')
    click.echo("  podx transcribe ./episode/")
    click.echo("  podx analyze ./episode/")

    click.echo()
    click.echo("To change settings:")
    click.echo("  podx config")

    click.echo()


if __name__ == "__main__":
    main()
