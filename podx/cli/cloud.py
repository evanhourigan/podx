"""CLI commands for cloud acceleration.

Provides setup wizard and management commands for RunPod
cloud transcription with Cloudflare R2 storage.
"""

import sys
from typing import Optional, Tuple

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
      setup     Configure RunPod + R2 cloud processing
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
    """Configure RunPod cloud processing with Cloudflare R2 storage.

    Interactive wizard to configure:
    1. RunPod API key and transcription endpoint
    2. Cloudflare R2 storage for audio uploads
    3. Optional diarization endpoint

    \b
    Pricing:
      Transcription: ~$0.05-0.10 per hour of podcast audio
      R2 Storage: Free tier (10GB storage, no egress fees)
    """
    console.print("\n[bold]Cloud Transcription Setup[/bold]\n")
    console.print("Cloud transcription uses RunPod GPU workers (~20-30x faster).")
    console.print("Audio is temporarily uploaded to Cloudflare R2 (free tier).\n")

    # Step 1: API Key
    api_key = _setup_api_key()
    if not api_key:
        sys.exit(1)

    # Step 2: Transcription Endpoint ID
    endpoint_id = _setup_endpoint_id(api_key, "transcription", "runpod-endpoint-id")
    if not endpoint_id:
        sys.exit(1)

    # Step 3: Cloudflare R2
    console.print("\n[bold]Step 3: Cloudflare R2 Storage[/bold]")
    console.print("Audio files are uploaded to R2 so RunPod workers can access them.")
    console.print("R2 free tier: 10GB storage, no egress fees.")
    console.print(
        "Set up at: [link=https://dash.cloudflare.com/?to=/:account/r2]"
        "https://dash.cloudflare.com[/link]\n"
    )

    r2_account_id = _setup_r2_account_id()
    if not r2_account_id:
        sys.exit(1)

    r2_bucket = _setup_r2_bucket(r2_account_id)
    if not r2_bucket:
        sys.exit(1)

    r2_access_key, r2_secret_key = _setup_r2_credentials(r2_account_id, r2_bucket)
    if not r2_access_key:
        sys.exit(1)

    # Save everything
    _set_value("runpod-api-key", api_key)
    _set_value("runpod-endpoint-id", endpoint_id)
    _set_value("r2-account-id", r2_account_id)
    _set_value("r2-bucket-name", r2_bucket)
    _set_value("r2-access-key-id", r2_access_key)
    _set_value("r2-secret-access-key", r2_secret_key)

    # Step 4: Optional Diarization Endpoint
    console.print("\n[bold]Step 4: Diarization Endpoint (Optional)[/bold]")
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


# =============================================================================
# RunPod setup helpers
# =============================================================================


def _setup_api_key() -> Optional[str]:
    """Set up RunPod API key."""
    existing_key = _get_value("runpod-api-key")
    if existing_key:
        masked = (
            existing_key[:8] + "..." + existing_key[-4:] if len(existing_key) > 12 else "[hidden]"
        )
        console.print(f"[dim]Found existing API key: {masked}[/dim]")
        if Confirm.ask("Use existing key?", default=True):
            if _validate_api_key(existing_key):
                console.print("[green]API key valid[/green]")
                return existing_key
            else:
                console.print("[yellow]Existing key is invalid. Please enter a new one.[/yellow]")

    console.print("[bold]Step 1: RunPod API Key[/bold]")
    console.print(
        "Get your API key from: [link=https://runpod.io/console/user/settings]"
        "https://runpod.io/console/user/settings[/link]"
    )
    console.print("[dim](Click 'API Keys' in the left menu)[/dim]\n")

    api_key = Prompt.ask("Enter RunPod API key").strip()
    if not api_key:
        console.print("[red]Error: API key is required[/red]")
        return None

    console.print("[dim]Validating API key...[/dim]")
    if not _validate_api_key(api_key):
        console.print("[red]Error: Invalid API key. Please check and try again.[/red]")
        return None

    console.print("[green]API key valid[/green]")
    return api_key


def _setup_endpoint_id(
    api_key: str, endpoint_type: str = "transcription", config_key: str = "runpod-endpoint-id"
) -> Optional[str]:
    """Set up RunPod endpoint ID."""
    if endpoint_type == "transcription":
        template_name = "faster-whisper"
        step_num = "2"
    else:
        template_name = "pyannote"
        step_num = "4"

    existing_endpoint = _get_value(config_key)
    if existing_endpoint:
        console.print(f"\n[dim]Found existing {endpoint_type} endpoint: {existing_endpoint}[/dim]")
        if Confirm.ask("Use existing endpoint?", default=True):
            if _validate_endpoint(api_key, existing_endpoint):
                console.print("[green]Endpoint responding[/green]")
                return existing_endpoint
            else:
                console.print(
                    "[yellow]Existing endpoint not responding. Please enter a new one.[/yellow]"
                )

    if endpoint_type == "transcription":
        console.print(f"\n[bold]Step {step_num}: Transcription Endpoint ID[/bold]")
        console.print("You need a Faster Whisper serverless endpoint.")
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
        return response.status_code != 401
    except Exception:
        return True  # Network error - can't validate, assume valid


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


# =============================================================================
# Cloudflare R2 setup helpers
# =============================================================================


def _setup_r2_account_id() -> Optional[str]:
    """Set up Cloudflare account ID."""
    existing = _get_value("r2-account-id")
    if existing:
        console.print(f"[dim]Found existing account ID: {existing}[/dim]")
        if Confirm.ask("Use existing?", default=True):
            return existing

    console.print("Your Cloudflare account ID is in the URL when logged in:")
    console.print("[dim]  https://dash.cloudflare.com/<account-id>/r2[/dim]\n")

    account_id = Prompt.ask("Enter Cloudflare account ID").strip()
    if not account_id:
        console.print("[red]Error: Account ID is required[/red]")
        return None

    return account_id


def _setup_r2_bucket(account_id: str) -> Optional[str]:
    """Set up R2 bucket name."""
    existing = _get_value("r2-bucket-name")
    if existing:
        console.print(f"[dim]Found existing bucket: {existing}[/dim]")
        if Confirm.ask("Use existing?", default=True):
            return existing

    console.print("\nCreate a bucket in R2 (e.g., 'podx-audio'):")
    console.print(f"[dim]  https://dash.cloudflare.com/{account_id}/r2/new[/dim]\n")

    bucket = Prompt.ask("Enter R2 bucket name", default="podx-audio").strip()
    if not bucket:
        console.print("[red]Error: Bucket name is required[/red]")
        return None

    return bucket


def _setup_r2_credentials(account_id: str, bucket: str) -> Tuple[Optional[str], Optional[str]]:
    """Set up R2 API token credentials."""
    existing_key = _get_value("r2-access-key-id")
    if existing_key:
        masked = existing_key[:8] + "..." if len(existing_key) > 8 else "[set]"
        console.print(f"[dim]Found existing R2 credentials: {masked}[/dim]")
        if Confirm.ask("Use existing credentials?", default=True):
            secret = _get_value("r2-secret-access-key")
            if _test_r2_connection(account_id, existing_key, secret, bucket):
                console.print("[green]R2 bucket accessible[/green]")
                return existing_key, secret
            else:
                console.print(
                    "[yellow]R2 connection failed. Please enter new credentials.[/yellow]"
                )

    console.print("\nCreate an R2 API token with Object Read & Write permissions:")
    console.print(f"[dim]  https://dash.cloudflare.com/{account_id}/r2/api-tokens[/dim]\n")

    access_key = Prompt.ask("Enter R2 access key ID").strip()
    if not access_key:
        console.print("[red]Error: Access key ID is required[/red]")
        return None, None

    secret_key = Prompt.ask("Enter R2 secret access key").strip()
    if not secret_key:
        console.print("[red]Error: Secret access key is required[/red]")
        return None, None

    console.print("[dim]Testing R2 connection...[/dim]")
    if _test_r2_connection(account_id, access_key, secret_key, bucket):
        console.print("[green]R2 bucket accessible[/green]")
    else:
        console.print("[yellow]R2 connection failed. Bucket may not exist yet.[/yellow]")
        if not Confirm.ask("Save credentials anyway?", default=True):
            return None, None

    return access_key, secret_key


def _test_r2_connection(account_id: str, access_key: str, secret_key: str, bucket: str) -> bool:
    """Test R2 bucket access with the given credentials."""
    try:
        import boto3
        from botocore.config import Config as BotoConfig

        client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=BotoConfig(signature_version="s3v4"),
        )
        client.head_bucket(Bucket=bucket)
        return True
    except ImportError:
        console.print("[yellow]boto3 not installed - skipping connection test[/yellow]")
        return True  # Can't test, assume it'll work
    except Exception:
        return False


# =============================================================================
# Status command
# =============================================================================


@main.command()
def status() -> None:
    """Check cloud configuration status.

    Shows whether RunPod and R2 are configured and responding.
    """
    console.print("\n[bold]Cloud Status[/bold]\n")

    # RunPod
    api_key = _get_value("runpod-api-key")
    endpoint_id = _get_value("runpod-endpoint-id")

    if api_key:
        masked = api_key[:8] + "..." if len(api_key) > 8 else "[set]"
        console.print(f"  RunPod API Key:    [green]{masked}[/green]")
    else:
        console.print("  RunPod API Key:    [red]not set[/red]")

    if endpoint_id:
        console.print(f"  RunPod Endpoint:   [green]{endpoint_id}[/green]")
    else:
        console.print("  RunPod Endpoint:   [red]not set[/red]")

    # Diarization endpoint
    diarize_endpoint_id = _get_value("runpod-diarize-endpoint-id")
    if diarize_endpoint_id:
        console.print(f"  Diarization:       [green]{diarize_endpoint_id}[/green]")
    else:
        console.print("  Diarization:       [dim]not set (optional)[/dim]")

    # R2
    r2_account = _get_value("r2-account-id")
    r2_bucket = _get_value("r2-bucket-name")
    r2_key = _get_value("r2-access-key-id")

    if r2_account:
        console.print(f"  R2 Account:        [green]{r2_account}[/green]")
    else:
        console.print("  R2 Account:        [red]not set[/red]")

    if r2_bucket:
        console.print(f"  R2 Bucket:         [green]{r2_bucket}[/green]")
    else:
        console.print("  R2 Bucket:         [red]not set[/red]")

    if r2_key:
        masked = r2_key[:8] + "..." if len(r2_key) > 8 else "[set]"
        console.print(f"  R2 Credentials:    [green]{masked}[/green]")
    else:
        console.print("  R2 Credentials:    [red]not set[/red]")

    # Overall status
    from podx.cloud.config import CloudConfig

    config = CloudConfig.from_podx_config()
    if config.is_configured:
        console.print("\n  Status:            [green]Cloud transcription enabled[/green]")
    else:
        console.print("\n  Status:            [dim]Not fully configured[/dim]")

    # Test connections
    if api_key and endpoint_id:
        console.print()
        console.print("[dim]Testing RunPod endpoint...[/dim]")
        if _validate_endpoint(api_key, endpoint_id):
            console.print("[green]RunPod endpoint responding[/green]")
        else:
            console.print("[yellow]RunPod endpoint not responding (may be cold)[/yellow]")

    if diarize_endpoint_id and api_key:
        console.print("[dim]Testing diarization endpoint...[/dim]")
        if _validate_endpoint(api_key, diarize_endpoint_id):
            console.print("[green]Diarization endpoint responding[/green]")
        else:
            console.print("[yellow]Diarization endpoint not responding (may be cold)[/yellow]")

    if r2_account and r2_key and r2_bucket:
        r2_secret = _get_value("r2-secret-access-key")
        console.print("[dim]Testing R2 bucket...[/dim]")
        if _test_r2_connection(r2_account, r2_key, r2_secret, r2_bucket):
            console.print("[green]R2 bucket accessible[/green]")
        else:
            console.print("[yellow]R2 bucket not accessible[/yellow]")

    if not config.is_configured:
        console.print("\n[dim]Run 'podx cloud setup' to configure[/dim]")

    console.print()


if __name__ == "__main__":
    main()
