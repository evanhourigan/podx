#!/usr/bin/env python3
"""Setup wizard for new PodX users.

Simple interactive setup that checks requirements and configures API keys.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

console = Console()

# Shell completion commands for each shell
COMPLETION_COMMANDS = {
    "bash": 'eval "$(_PODX_COMPLETE=bash_source podx)"',
    "zsh": 'eval "$(_PODX_COMPLETE=zsh_source podx)"',
    "fish": "_PODX_COMPLETE=fish_source podx | source",
}

SHELL_RC_FILES = {
    "bash": "~/.bashrc",
    "zsh": "~/.zshrc",
    "fish": "~/.config/fish/config.fish",
}


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
    console.print("\n[bold]Checking requirements...[/bold]\n")

    all_good = True

    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 9):
        console.print(f"  [green]✓[/green] Python {py_version}")
    else:
        console.print(f"  [red]✗[/red] Python {py_version} (requires 3.9+)")
        all_good = False

    # FFmpeg (required)
    ffmpeg_ok, ffmpeg_ver = _check_command("ffmpeg")
    if ffmpeg_ok:
        console.print(f"  [green]✓[/green] FFmpeg {ffmpeg_ver[:30]}")
    else:
        console.print("  [red]✗[/red] FFmpeg not found (required)")
        console.print("      Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
        all_good = False

    # yt-dlp (optional)
    ytdlp_ok, ytdlp_ver = _check_command("yt-dlp")
    if ytdlp_ok:
        console.print(f"  [green]✓[/green] yt-dlp {ytdlp_ver[:30]}")
    else:
        console.print("  [dim]○[/dim] yt-dlp not found (optional, for YouTube downloads)")
        console.print("      Install: pip install yt-dlp")

    console.print()

    if not all_good:
        console.print(
            "[red]Missing required dependencies. Install them and run 'podx init' again.[/red]\n"
        )

    return all_good


def _configure_output_dir() -> str:
    """Configure output directory."""
    console.print("[bold]Where should PodX save files?[/bold]\n")
    console.print("  [cyan]1[/cyan]) Current working directory")
    console.print("      Files saved relative to wherever you run podx.")
    console.print()
    console.print("  [cyan]2[/cyan]) Fixed directory")
    console.print("      Files always saved to one location.")
    console.print()

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
            console.print(f"  [green]✓[/green] Created: {path}")
            return path
        else:
            console.print("  Please enter 1 or 2")


def _configure_api_keys() -> dict[str, str]:
    """Configure API keys."""
    console.print("\n[bold]Configure API keys[/bold] (all optional, can be added later)\n")

    keys = {}

    # OpenAI
    console.print("[bold]OpenAI[/bold] - for cloud transcription and GPT analysis")
    console.print("[dim]Get key: https://platform.openai.com/api-keys[/dim]")
    key = input("Enter key (or Enter to skip): ").strip()
    if key:
        keys["OPENAI_API_KEY"] = key
        console.print("  [green]✓[/green] Saved\n")
    else:
        console.print("  [dim]Skipped[/dim]\n")

    # Anthropic
    console.print("[bold]Anthropic[/bold] - for Claude analysis models")
    console.print("[dim]Get key: https://console.anthropic.com/settings/keys[/dim]")
    key = input("Enter key (or Enter to skip): ").strip()
    if key:
        keys["ANTHROPIC_API_KEY"] = key
        console.print("  [green]✓[/green] Saved\n")
    else:
        console.print("  [dim]Skipped[/dim]\n")

    # HuggingFace
    console.print("[bold]HuggingFace[/bold] - for improved speaker diarization")
    console.print("[dim]Get token: https://huggingface.co/settings/tokens[/dim]")
    key = input("Enter token (or Enter to skip): ").strip()
    if key:
        keys["HUGGINGFACE_TOKEN"] = key
        console.print("  [green]✓[/green] Saved\n")
    else:
        console.print("  [dim]Skipped[/dim]\n")

    # Notion (ask first)
    setup_notion = input("Set up Notion integration? (y/N): ").strip().lower()
    if setup_notion == "y":
        console.print("\n[bold]Notion[/bold] - for publishing analyses")
        console.print("[dim]Get token: https://www.notion.so/my-integrations[/dim]")
        key = input("Enter token (or Enter to skip): ").strip()
        if key:
            keys["NOTION_TOKEN"] = key
            console.print("  [green]✓[/green] Saved")

        db_id = input("Enter database ID (or Enter to skip): ").strip()
        if db_id:
            keys["NOTION_DATABASE_ID"] = db_id
            console.print("  [green]✓[/green] Saved\n")
        else:
            console.print("  [dim]Skipped[/dim]\n")

    return keys


def _detect_shell() -> Optional[str]:
    """Detect the current shell."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    elif "bash" in shell:
        return "bash"
    elif "fish" in shell:
        return "fish"
    return None


def _configure_completions() -> Optional[str]:
    """Configure shell completions. Returns the shell configured, or None if skipped."""
    console.print("\n[bold]Shell Completions[/bold]\n")
    console.print("Enable tab-completion for podx commands and options.")
    console.print()

    detected = _detect_shell()
    if detected:
        console.print(f"  Detected shell: [cyan]{detected}[/cyan]")

    console.print("\n  [cyan]1[/cyan]) bash")
    console.print("  [cyan]2[/cyan]) zsh")
    console.print("  [cyan]3[/cyan]) fish")
    console.print("  [cyan]s[/cyan]) Skip")
    console.print()

    default = {"bash": "1", "zsh": "2", "fish": "3"}.get(detected or "", "s")
    choice = input(f"Choice [{default}]: ").strip().lower() or default

    shell_map = {"1": "bash", "2": "zsh", "3": "fish"}
    if choice == "s":
        console.print("  [dim]Skipped[/dim]")
        return None

    shell = shell_map.get(choice)
    if not shell:
        console.print("  [dim]Skipped[/dim]")
        return None

    # Get the RC file path
    rc_file = Path(os.path.expanduser(SHELL_RC_FILES[shell]))
    completion_cmd = COMPLETION_COMMANDS[shell]

    # Check if already configured
    if rc_file.exists():
        content = rc_file.read_text()
        if "_PODX_COMPLETE" in content:
            console.print(f"  [green]✓[/green] Already configured in {rc_file}")
            return shell

    # Add completion to shell rc file
    try:
        # Create parent directories if needed (for fish)
        rc_file.parent.mkdir(parents=True, exist_ok=True)

        # Append the completion command
        with open(rc_file, "a") as f:
            f.write(f"\n# PodX shell completion\n{completion_cmd}\n")

        console.print(f"  [green]✓[/green] Added to {rc_file}")
        console.print(f"  [dim]Run 'source {rc_file}' or restart your shell to activate[/dim]")
        return shell
    except OSError as e:
        console.print(f"  [red]✗[/red] Failed to write to {rc_file}: {e}")
        console.print(f"  [dim]Add manually: {completion_cmd}[/dim]")
        return None


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


@click.command(context_settings={"max_content_width": 120})
@click.option(
    "--completions",
    is_flag=True,
    help="Only configure shell completions (skip other setup steps).",
)
def main(completions: bool) -> None:
    """Setup wizard for new PodX users.

    Interactive setup that:
      1. Checks system requirements
      2. Configures output directory
      3. Sets up API keys (optional)
      4. Configures shell completions

    \b
    Options:
      --completions    Only configure shell completions

    \b
    Examples:
      podx init              # Full setup wizard
      podx init --completions  # Only set up shell completions
    """
    # Completions-only mode
    if completions:
        console.print(
            Panel.fit(
                "[bold cyan]PodX Shell Completions[/bold cyan]",
                border_style="cyan",
            )
        )
        shell = _configure_completions()
        if shell:
            console.print(f"\n[green]✓[/green] Shell completions configured for {shell}")
        else:
            console.print("\n[dim]Shell completions not configured[/dim]")
        return

    # Welcome
    console.print(
        Panel.fit(
            "[bold cyan]Welcome to PodX![/bold cyan]",
            border_style="cyan",
        )
    )

    # Step 1: Check requirements
    if not _check_requirements():
        sys.exit(1)

    # Step 2: Output directory
    output_dir = _configure_output_dir()

    # Step 3: API keys
    api_keys = _configure_api_keys()

    # Step 4: Shell completions
    shell_configured = _configure_completions()

    # Save configuration
    config_file = _save_config(output_dir, api_keys)

    # Show summary
    console.print("\n" + "=" * 50)
    console.print("[bold green]Setup complete![/bold green]")
    console.print("=" * 50 + "\n")

    console.print(f"Configuration saved to: {config_file}")
    if output_dir == "cwd":
        console.print("Output directory: current working directory")
    else:
        console.print(f"Output directory: {output_dir}")

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
        console.print(f"API keys: {', '.join(configured)} [green]✓[/green]")
    if not_configured:
        console.print(f"Not configured: {', '.join(not_configured)} [dim](optional)[/dim]")

    # Shell completions status
    if shell_configured:
        console.print(f"Shell completions: {shell_configured} [green]✓[/green]")

    # Load API keys instruction
    if api_keys:
        env_file = Path.home() / ".config" / "podx" / "env.sh"
        console.print("\n[bold]To load API keys, run:[/bold]")
        console.print(f"  [cyan]source {env_file}[/cyan]")
        console.print("[dim]Or add this line to your ~/.zshrc or ~/.bashrc[/dim]")

    # Next steps
    console.print("\n[bold]Get started:[/bold]")
    console.print('  [cyan]podx fetch --show "Lex Fridman"[/cyan]')
    console.print("  [cyan]podx transcribe ./episode/[/cyan]")
    console.print("  [cyan]podx analyze ./episode/[/cyan]")

    console.print("\n[bold]To change settings:[/bold]")
    console.print("  [cyan]podx config[/cyan]")

    console.print()


if __name__ == "__main__":
    main()
