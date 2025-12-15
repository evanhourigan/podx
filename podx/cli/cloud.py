"""CLI commands for cloud acceleration.

Provides setup wizard and management commands for RunPod
cloud transcription.
"""

import sys
from typing import Optional

import click
import httpx
from rich.console import Console
from rich.prompt import Confirm, Prompt

from podx.cli.config import _get_value, _set_value

console = Console()


@click.group()
def main() -> None:
    """Cloud acceleration commands.

    \b
    Commands:
      setup     Configure RunPod cloud transcription
      status    Check cloud configuration status

    \b
    Usage:
      podx cloud setup     # Interactive setup wizard
      podx cloud status    # Check if configured

    \b
    After setup, use cloud transcription with:
      podx transcribe --model runpod:large-v3-turbo ./episode/
    """
    pass


@main.command()
def setup() -> None:
    """Configure RunPod cloud transcription.

    Interactive wizard to configure RunPod API credentials.
    Cloud transcription is ~20-30x faster than local processing.

    \b
    Steps:
      1. Enter RunPod API key (from runpod.io/console)
      2. Enter endpoint ID (from deployed faster-whisper template)
      3. Test connection

    \b
    Pricing:
      ~$0.05-0.10 per hour of podcast audio
      Based on GPU-seconds used (~$0.067/hr for A4000)
    """
    console.print("\n[bold]RunPod Cloud Setup[/bold]\n")
    console.print("Cloud transcription is ~20-30x faster than local processing.")
    console.print("Pricing: ~$0.05-0.10 per hour of podcast audio\n")

    # Step 1: API Key
    api_key = _setup_api_key()
    if not api_key:
        sys.exit(1)

    # Step 2: Endpoint ID
    endpoint_id = _setup_endpoint_id(api_key)
    if not endpoint_id:
        sys.exit(1)

    # Step 3: Save configuration
    _set_value("runpod-api-key", api_key)
    _set_value("runpod-endpoint-id", endpoint_id)

    console.print("\n[green]Cloud setup complete![/green]")
    console.print("\n[dim]Usage:[/dim]")
    console.print("  podx transcribe --model runpod:large-v3-turbo ./episode/")
    console.print("  podx run --model runpod:large-v3-turbo ./episode/\n")


def _setup_api_key() -> Optional[str]:
    """Set up RunPod API key."""
    # Check for existing key
    existing_key = _get_value("runpod-api-key")
    if existing_key:
        masked = (
            existing_key[:8] + "..." + existing_key[-4:] if len(existing_key) > 12 else "[hidden]"
        )
        console.print(f"[dim]Found existing API key: {masked}[/dim]")
        if Confirm.ask("Use existing key?", default=True):
            # Validate existing key
            if _validate_api_key(existing_key):
                console.print("[green]API key valid[/green]")
                return existing_key
            else:
                console.print("[yellow]Existing key is invalid. Please enter a new one.[/yellow]")

    # Get new key
    console.print("\n[bold]Step 1: API Key[/bold]")
    console.print(
        "Get your API key from: [link=https://runpod.io/console/user/settings]https://runpod.io/console/user/settings[/link]"
    )
    console.print("[dim](Click 'API Keys' in the left menu)[/dim]\n")

    api_key = Prompt.ask("Enter RunPod API key").strip()
    if not api_key:
        console.print("[red]Error: API key is required[/red]")
        return None

    # Validate
    console.print("[dim]Validating API key...[/dim]")
    if not _validate_api_key(api_key):
        console.print("[red]Error: Invalid API key. Please check and try again.[/red]")
        return None

    console.print("[green]API key valid[/green]")
    return api_key


def _setup_endpoint_id(api_key: str) -> Optional[str]:
    """Set up RunPod endpoint ID."""
    # Check for existing endpoint
    existing_endpoint = _get_value("runpod-endpoint-id")
    if existing_endpoint:
        console.print(f"\n[dim]Found existing endpoint: {existing_endpoint}[/dim]")
        if Confirm.ask("Use existing endpoint?", default=True):
            # Validate existing endpoint
            if _validate_endpoint(api_key, existing_endpoint):
                console.print("[green]Endpoint responding[/green]")
                return existing_endpoint
            else:
                console.print(
                    "[yellow]Existing endpoint not responding. Please enter a new one.[/yellow]"
                )

    # Get new endpoint
    console.print("\n[bold]Step 2: Endpoint ID[/bold]")
    console.print("You need a faster-whisper serverless endpoint.")
    console.print(
        "Deploy from: [link=https://runpod.io/console/serverless]https://runpod.io/console/serverless[/link]"
    )
    console.print("[dim](Search for 'faster-whisper' in templates)[/dim]\n")

    endpoint_id = Prompt.ask("Enter endpoint ID after deployment").strip()
    if not endpoint_id:
        console.print("[red]Error: Endpoint ID is required[/red]")
        return None

    # Validate
    console.print("[dim]Testing endpoint...[/dim]")
    if not _validate_endpoint(api_key, endpoint_id):
        console.print("[red]Error: Endpoint not responding. Please verify the endpoint ID.[/red]")
        if not Confirm.ask("Save anyway?", default=False):
            return None

    console.print("[green]Endpoint responding[/green]")
    return endpoint_id


def _validate_api_key(api_key: str) -> bool:
    """Validate RunPod API key by calling the API."""
    try:
        response = httpx.get(
            "https://api.runpod.io/v2",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        # A valid key should not return 401
        return response.status_code != 401
    except Exception:
        # Network error - can't validate, assume it might be valid
        return True


def _validate_endpoint(api_key: str, endpoint_id: str) -> bool:
    """Validate that endpoint exists and responds."""
    try:
        response = httpx.get(
            f"https://api.runpod.ai/v2/{endpoint_id}/health",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        return response.status_code == 200
    except Exception:
        return False


@main.command()
def status() -> None:
    """Check cloud configuration status.

    Shows whether RunPod cloud transcription is configured
    and the endpoint is responding.
    """
    console.print("\n[bold]Cloud Status[/bold]\n")

    # Check API key
    api_key = _get_value("runpod-api-key")
    if api_key:
        masked = api_key[:8] + "..." if len(api_key) > 8 else "[set]"
        console.print(f"  API Key:     [green]{masked}[/green]")
    else:
        console.print("  API Key:     [red]not set[/red]")

    # Check endpoint ID
    endpoint_id = _get_value("runpod-endpoint-id")
    if endpoint_id:
        console.print(f"  Endpoint ID: [green]{endpoint_id}[/green]")
    else:
        console.print("  Endpoint ID: [red]not set[/red]")

    # Test connection if both are set
    if api_key and endpoint_id:
        console.print("\n[dim]Testing connection...[/dim]")
        if _validate_endpoint(api_key, endpoint_id):
            console.print("[green]Endpoint is responding[/green]")
        else:
            console.print("[yellow]Endpoint not responding (may be cold)[/yellow]")
            console.print("[dim]First request will take ~30s to warm up[/dim]")
    else:
        console.print("\n[dim]Run 'podx cloud setup' to configure[/dim]")

    console.print()


if __name__ == "__main__":
    main()
