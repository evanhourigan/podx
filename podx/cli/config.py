"""CLI command for configuration and profile management.

Handles:
- Configuration profiles (save, load, list, delete, export, import)
- API key management (set, list, remove)
- Built-in profile installation
"""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from podx.config import (
    ConfigProfile,
    ProfileManager,
    get_builtin_profiles,
    install_builtin_profiles,
)
from podx.domain.exit_codes import ExitCode

console = Console()


@click.group(help="Manage configuration profiles and API keys")
def main():
    """Configuration management commands."""
    pass


# ============================================================================
# Profile Management Commands
# ============================================================================


@main.command(name="save-profile", help="Save a new configuration profile")
@click.argument("profile_name")
@click.option("--description", help="Profile description")
@click.option("--asr-model", help="ASR model (e.g., large-v3, medium)")
@click.option(
    "--asr-provider", type=click.Choice(["local", "openai"]), help="ASR provider"
)
@click.option("--diarize/--no-diarize", default=None, help="Enable speaker diarization")
@click.option("--preprocess/--no-preprocess", default=None, help="Enable preprocessing")
@click.option("--deepcast/--no-deepcast", default=None, help="Enable deepcast")
@click.option(
    "--llm-model", help="LLM model for deepcast (e.g., gpt-4o, claude-3-sonnet)"
)
@click.option(
    "--llm-provider",
    type=click.Choice(["openai", "anthropic", "openrouter"]),
    help="LLM provider",
)
@click.option("--export-formats", help="Export formats (comma-separated)")
def save_profile(profile_name: str, description: Optional[str], **kwargs):
    """Save configuration profile with specified settings.

    Example:
        podx config save-profile "my-profile" \\
            --asr-model large-v3 \\
            --llm-model gpt-4o \\
            --diarize \\
            --export-formats txt,srt,md
    """
    # Build settings dict from provided options
    settings = {}
    for key, value in kwargs.items():
        if value is not None:
            # Convert export_formats string to list
            if key == "export_formats":
                settings[key] = [f.strip() for f in value.split(",")]
            else:
                settings[key] = value

    if not settings:
        console.print("[red]Error:[/red] No settings provided")
        sys.exit(ExitCode.USER_ERROR)

    # Create and save profile
    profile = ConfigProfile(
        name=profile_name, settings=settings, description=description or ""
    )

    manager = ProfileManager()
    manager.save(profile)

    console.print(f"[green]✓[/green] Saved profile '[cyan]{profile_name}[/cyan]'")
    console.print(f"  Settings: {len(settings)} options")


@main.command(name="list-profiles", help="List all configuration profiles")
@click.option("--verbose", "-v", is_flag=True, help="Show profile details")
def list_profiles(verbose: bool):
    """List all available profiles."""
    manager = ProfileManager()
    profiles = manager.list_profiles()

    if not profiles:
        console.print("[yellow]No profiles found.[/yellow]")
        console.print("\nCreate a profile with: podx config save-profile <name>")
        console.print("Or install built-in profiles with: podx config install-builtins")
        sys.exit(ExitCode.SUCCESS)

    if verbose:
        # Show detailed table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Profile", style="cyan")
        table.add_column("Description")
        table.add_column("Settings")

        for name in profiles:
            profile = manager.load(name)
            if profile:
                settings_summary = ", ".join(
                    f"{k}={v}" for k, v in list(profile.settings.items())[:3]
                )
                if len(profile.settings) > 3:
                    settings_summary += f", ... (+{len(profile.settings) - 3} more)"

                table.add_row(name, profile.description or "-", settings_summary)

        console.print(table)
    else:
        # Simple list
        console.print("[bold]Available Profiles:[/bold]")
        for name in profiles:
            profile = manager.load(name)
            if profile and profile.description:
                console.print(f"  • [cyan]{name}[/cyan] - {profile.description}")
            else:
                console.print(f"  • [cyan]{name}[/cyan]")

    sys.exit(ExitCode.SUCCESS)


@main.command(name="show-profile", help="Show profile details")
@click.argument("profile_name")
def show_profile(profile_name: str):
    """Show detailed profile configuration."""
    manager = ProfileManager()
    profile = manager.load(profile_name)

    if profile is None:
        console.print(f"[red]Error:[/red] Profile '{profile_name}' not found")
        sys.exit(ExitCode.USER_ERROR)

    console.print(f"\n[bold cyan]Profile: {profile.name}[/bold cyan]")
    if profile.description:
        console.print(f"[dim]{profile.description}[/dim]")

    console.print("\n[bold]Settings:[/bold]")
    for key, value in profile.settings.items():
        console.print(f"  {key}: [green]{value}[/green]")

    console.print("")
    sys.exit(ExitCode.SUCCESS)


@main.command(name="delete-profile", help="Delete a configuration profile")
@click.argument("profile_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete_profile(profile_name: str, yes: bool):
    """Delete configuration profile."""
    manager = ProfileManager()

    # Check if profile exists
    if not manager.load(profile_name):
        console.print(f"[red]Error:[/red] Profile '{profile_name}' not found")
        sys.exit(ExitCode.USER_ERROR)

    # Confirm deletion
    if not yes:
        confirm = click.confirm(f"Delete profile '{profile_name}'?", default=False)
        if not confirm:
            console.print("Cancelled")
            sys.exit(ExitCode.SUCCESS)

    # Delete
    if manager.delete(profile_name):
        console.print(f"[green]✓[/green] Deleted profile '[cyan]{profile_name}[/cyan]'")
    else:
        console.print("[red]Error:[/red] Failed to delete profile")
        sys.exit(ExitCode.PROCESSING_ERROR)

    sys.exit(ExitCode.SUCCESS)


@main.command(name="export-profile", help="Export profile as YAML")
@click.argument("profile_name")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file (prints to stdout if not specified)",
)
def export_profile(profile_name: str, output: Optional[str]):
    """Export profile configuration as YAML."""
    manager = ProfileManager()
    yaml_content = manager.export_profile(profile_name)

    if yaml_content is None:
        console.print(f"[red]Error:[/red] Profile '{profile_name}' not found")
        sys.exit(ExitCode.USER_ERROR)

    if output:
        Path(output).write_text(yaml_content)
        console.print(f"[green]✓[/green] Exported to {output}")
    else:
        print(yaml_content)

    sys.exit(ExitCode.SUCCESS)


@main.command(name="import-profile", help="Import profile from YAML file")
@click.argument("yaml_file", type=click.Path(exists=True))
def import_profile(yaml_file: str):
    """Import profile from YAML file."""
    manager = ProfileManager()

    try:
        yaml_content = Path(yaml_file).read_text()
        profile = manager.import_profile(yaml_content)
        console.print(
            f"[green]✓[/green] Imported profile '[cyan]{profile.name}[/cyan]'"
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to import profile: {e}")
        sys.exit(ExitCode.PROCESSING_ERROR)

    sys.exit(ExitCode.SUCCESS)


@main.command(name="install-builtins", help="Install built-in profiles")
def install_builtins():
    """Install built-in configuration profiles (quick, standard, high-quality)."""
    count = install_builtin_profiles()
    console.print(f"[green]✓[/green] Installed {count} built-in profiles:")

    for profile in get_builtin_profiles():
        console.print(f"  • [cyan]{profile.name}[/cyan] - {profile.description}")

    sys.exit(ExitCode.SUCCESS)


# ============================================================================
# API Key Management Commands
# ============================================================================


@main.command(name="set-key", help="Set an API key")
@click.argument(
    "service", type=click.Choice(["openai", "anthropic", "openrouter", "notion"])
)
@click.option("--key", prompt=True, hide_input=True, help="API key value")
def set_key(service: str, key: str):
    """Set API key for a service.

    Keys are stored in ~/.podx/.env file.

    Supported services:
    - openai: OpenAI API (GPT models, Whisper)
    - anthropic: Anthropic API (Claude models)
    - openrouter: OpenRouter API (multi-provider access)
    - notion: Notion API (for notion integration)
    """
    env_file = Path.home() / ".podx" / ".env"
    env_file.parent.mkdir(parents=True, exist_ok=True)

    # Map service to env var name
    env_vars = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "notion": "NOTION_TOKEN",
    }

    var_name = env_vars[service]

    # Read existing .env
    lines = []
    if env_file.exists():
        lines = env_file.read_text().splitlines()

    # Update or add key
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{var_name}="):
            lines[i] = f"{var_name}={key}"
            found = True
            break

    if not found:
        lines.append(f"{var_name}={key}")

    # Write back
    env_file.write_text("\n".join(lines) + "\n")
    env_file.chmod(0o600)  # Secure permissions

    console.print(f"[green]✓[/green] Set {service} API key")
    console.print(f"  Stored in: [dim]{env_file}[/dim]")


@main.command(name="list-keys", help="List configured API keys")
def list_keys():
    """List which API keys are configured (values hidden)."""
    env_file = Path.home() / ".podx" / ".env"

    if not env_file.exists():
        console.print("[yellow]No API keys configured.[/yellow]")
        console.print("\nSet a key with: podx config set-key <service>")
        sys.exit(ExitCode.SUCCESS)

    # Parse .env
    configured = {}
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            if value.strip():
                configured[key] = value

    # Show configured keys
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Service")
    table.add_column("Status")
    table.add_column("Preview")

    services = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "OPENROUTER_API_KEY": "OpenRouter",
        "NOTION_TOKEN": "Notion",
    }

    for env_var, service_name in services.items():
        if env_var in configured:
            value = configured[env_var]
            # Show first 8 chars and last 4
            preview = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
            table.add_row(service_name, "[green]✓ Configured[/green]", preview)
        else:
            table.add_row(service_name, "[dim]Not set[/dim]", "-")

    console.print(table)
    sys.exit(ExitCode.SUCCESS)


@main.command(name="remove-key", help="Remove an API key")
@click.argument(
    "service", type=click.Choice(["openai", "anthropic", "openrouter", "notion"])
)
def remove_key(service: str):
    """Remove API key for a service."""
    env_file = Path.home() / ".podx" / ".env"

    if not env_file.exists():
        console.print("[yellow]No API keys configured.[/yellow]")
        sys.exit(ExitCode.SUCCESS)

    # Map service to env var
    env_vars = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "notion": "NOTION_TOKEN",
    }

    var_name = env_vars[service]

    # Read and filter lines
    lines = env_file.read_text().splitlines()
    new_lines = [line for line in lines if not line.startswith(f"{var_name}=")]

    # Write back
    env_file.write_text("\n".join(new_lines) + "\n")

    console.print(f"[green]✓[/green] Removed {service} API key")


if __name__ == "__main__":
    main()
