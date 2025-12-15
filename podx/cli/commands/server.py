"""Server management commands for PodX API Server."""

import click
from rich.console import Console

console = Console()


@click.group()
def server() -> None:
    """Manage the PodX API Server."""
    pass


@server.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1)",
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="Port to bind to (default: 8000)",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development",
)
@click.option(
    "--workers",
    default=1,
    type=int,
    help="Number of worker processes (default: 1)",
)
def start(host: str, port: int, reload: bool, workers: int) -> None:
    """Start the PodX API Server.

    Examples:
        podx server start
        podx server start --host 0.0.0.0 --port 8080
        podx server start --reload  # Development mode
    """
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Error:[/red] uvicorn not installed. " "Install with: pip install podx[server]"
        )
        raise click.Abort()

    console.print(f"[green]Starting PodX API Server on {host}:{port}...[/green]")
    console.print(f"[dim]API docs available at: http://{host}:{port}/docs[/dim]")

    # Run uvicorn
    uvicorn.run(
        "podx.server.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # Can't use workers with reload
        log_level="info",
    )


if __name__ == "__main__":
    server()
