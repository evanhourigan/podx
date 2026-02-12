"""CLI commands for cloud acceleration.

Provides setup wizard and management commands for RunPod
cloud transcription and diarization.
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
      setup     Configure RunPod cloud processing
      status    Check cloud configuration status

    \b
    Usage:
      podx cloud setup     # Interactive setup wizard
      podx cloud status    # Check if configured

    \b
    After setup, use cloud processing with:
      podx transcribe --model runpod:large-v3-turbo ./episode/
      podx diarize --provider runpod ./episode/
    """
    pass


@main.command()
def setup() -> None:
    """Configure RunPod cloud processing.

    Interactive wizard to configure RunPod API credentials for
    cloud transcription and diarization.

    \b
    Steps:
      1. Enter RunPod API key (from runpod.io/console)
      2. Enter transcription endpoint ID (faster-whisper template)
      3. Optionally enter diarization endpoint ID (pyannote template)
      4. Test connections

    \b
    Pricing:
      Transcription: ~$0.05-0.10 per hour of podcast audio
      Diarization: ~$0.10-0.20 per hour (more GPU-intensive)
    """
    console.print("\n[bold]RunPod Cloud Setup[/bold]\n")
    console.print("Cloud processing is ~20-30x faster than local.")
    console.print("Pricing: ~$0.05-0.20 per hour of podcast audio\n")

    # Step 1: API Key
    api_key = _setup_api_key()
    if not api_key:
        sys.exit(1)

    # Step 2: Transcription Endpoint ID
    endpoint_id = _setup_endpoint_id(api_key, "transcription", "runpod-endpoint-id")
    if not endpoint_id:
        sys.exit(1)

    # Step 3: Save API key and transcription endpoint
    _set_value("runpod-api-key", api_key)
    _set_value("runpod-endpoint-id", endpoint_id)

    # Step 4: Optional Diarization Endpoint
    console.print("\n[bold]Step 3: Diarization Endpoint (Optional)[/bold]")
    console.print("Cloud diarization offloads speaker identification to cloud GPUs.")
    console.print("[dim]Skip this if you only need transcription.[/dim]\n")

    if Confirm.ask("Configure cloud diarization?", default=False):
        diarize_endpoint_id = _setup_endpoint_id(
            api_key, "diarization", "runpod-diarize-endpoint-id"
        )
        if diarize_endpoint_id:
            _set_value("runpod-diarize-endpoint-id", diarize_endpoint_id)
            console.print("\n[green]Cloud setup complete![/green]")
            console.print("\n[dim]Usage:[/dim]")
            console.print("  podx transcribe --model runpod:large-v3-turbo ./episode/")
            console.print("  podx diarize --provider runpod ./episode/")
            console.print("  podx run --model runpod:large-v3-turbo ./episode/\n")
        else:
            console.print("\n[yellow]Diarization skipped.[/yellow]")
            _print_transcription_usage()
    else:
        console.print("\n[green]Cloud setup complete![/green]")
        _print_transcription_usage()


def _print_transcription_usage() -> None:
    """Print transcription-only usage instructions."""
    console.print("\n[dim]Usage:[/dim]")
    console.print("  podx transcribe --model runpod:large-v3-turbo ./episode/")
    console.print("  podx run --model runpod:large-v3-turbo ./episode/")
    console.print("\n[dim]To add cloud diarization later, run 'podx cloud setup' again.[/dim]\n")


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


def _setup_endpoint_id(
    api_key: str, endpoint_type: str = "transcription", config_key: str = "runpod-endpoint-id"
) -> Optional[str]:
    """Set up RunPod endpoint ID.

    Args:
        api_key: RunPod API key for validation
        endpoint_type: Type of endpoint ("transcription" or "diarization")
        config_key: Config key to check for existing value
    """
    # Template suggestions based on endpoint type
    if endpoint_type == "transcription":
        template_name = "faster-whisper"
        step_num = "2"
    else:
        template_name = "pyannote"
        step_num = "3"

    # Check for existing endpoint
    existing_endpoint = _get_value(config_key)
    if existing_endpoint:
        console.print(f"\n[dim]Found existing {endpoint_type} endpoint: {existing_endpoint}[/dim]")
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
    if endpoint_type == "transcription":
        console.print(f"\n[bold]Step {step_num}: Transcription Endpoint ID[/bold]")
        console.print("You need a faster-whisper serverless endpoint.")
        console.print(
            "Deploy from: [link=https://runpod.io/console/serverless]"
            "https://runpod.io/console/serverless[/link]"
        )
        console.print(f"[dim](Search for '{template_name}' in templates)[/dim]\n")
    else:
        console.print(f"\n[bold]Step {step_num}: Diarization Endpoint ID[/bold]")
        console.print("You need a pyannote diarization serverless endpoint.")
        console.print(
            "Deploy from: [link=https://runpod.io/console/serverless]"
            "https://runpod.io/console/serverless[/link]"
        )
        console.print("[dim](Search for 'pyannote' or deploy custom handler)[/dim]\n")

    endpoint_id = Prompt.ask(f"Enter {endpoint_type} endpoint ID").strip()
    if not endpoint_id:
        console.print(f"[red]Error: {endpoint_type.title()} endpoint ID is required[/red]")
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

    Shows whether RunPod cloud processing is configured
    and endpoints are responding.
    """
    console.print("\n[bold]Cloud Status[/bold]\n")

    # Check API key
    api_key = _get_value("runpod-api-key")
    if api_key:
        masked = api_key[:8] + "..." if len(api_key) > 8 else "[set]"
        console.print(f"  API Key:              [green]{masked}[/green]")
    else:
        console.print("  API Key:              [red]not set[/red]")

    # Check transcription endpoint ID
    endpoint_id = _get_value("runpod-endpoint-id")
    if endpoint_id:
        console.print(f"  Transcription:        [green]{endpoint_id}[/green]")
    else:
        console.print("  Transcription:        [red]not set[/red]")

    # Check diarization endpoint ID
    diarize_endpoint_id = _get_value("runpod-diarize-endpoint-id")
    if diarize_endpoint_id:
        console.print(f"  Diarization:          [green]{diarize_endpoint_id}[/green]")
    else:
        console.print("  Diarization:          [dim]not set (optional)[/dim]")

    # Test connections if API key is set
    if api_key:
        console.print()

        # Test transcription endpoint
        if endpoint_id:
            console.print("[dim]Testing transcription endpoint...[/dim]")
            if _validate_endpoint(api_key, endpoint_id):
                console.print("[green]Transcription endpoint responding[/green]")
            else:
                console.print(
                    "[yellow]Transcription endpoint not responding (may be cold)[/yellow]"
                )

        # Test diarization endpoint
        if diarize_endpoint_id:
            console.print("[dim]Testing diarization endpoint...[/dim]")
            if _validate_endpoint(api_key, diarize_endpoint_id):
                console.print("[green]Diarization endpoint responding[/green]")
            else:
                console.print("[yellow]Diarization endpoint not responding (may be cold)[/yellow]")

        if not endpoint_id and not diarize_endpoint_id:
            console.print("[dim]No endpoints configured. Run 'podx cloud setup'[/dim]")
    else:
        console.print("\n[dim]Run 'podx cloud setup' to configure[/dim]")

    console.print()


if __name__ == "__main__":
    main()
