"""Console-based progress reporter for CLI applications."""

import sys
from typing import Optional

from rich.console import Console

from .base import ProgressReporter


class ConsoleProgressReporter(ProgressReporter):
    """Progress reporter that outputs to console using Rich.

    Provides simple text-based progress updates suitable for CLI applications.
    Uses Rich for colored output and formatting.
    """

    def __init__(self, console: Optional[Console] = None, verbose: bool = False):
        """Initialize console progress reporter.

        Args:
            console: Optional Rich Console instance (creates one if not provided)
            verbose: Enable verbose output (shows all updates)
        """
        self.console = console or Console(file=sys.stderr)
        self.verbose = verbose
        self.current_task: Optional[str] = None
        self.current_step: int = 0
        self.total_steps: Optional[int] = None

    def start_task(self, task_name: str, total_steps: Optional[int] = None) -> None:
        """Start a new task."""
        self.current_task = task_name
        self.current_step = 0
        self.total_steps = total_steps

        if total_steps:
            self.console.print(f"[bold blue]▶[/bold blue] {task_name} ({total_steps} steps)")
        else:
            self.console.print(f"[bold blue]▶[/bold blue] {task_name}")

    def update_step(
        self,
        message: str,
        step: Optional[int] = None,
        progress: Optional[float] = None,
    ) -> None:
        """Update progress for current step."""
        if step is not None:
            self.current_step = step

        # Show progress indicator if we have total steps
        if self.total_steps and step is not None:
            prefix = f"  [{step}/{self.total_steps}]"
        elif progress is not None:
            percentage = int(progress * 100)
            prefix = f"  [{percentage}%]"
        else:
            prefix = "  •"

        if self.verbose or step is not None or progress is not None:
            self.console.print(f"{prefix} {message}")

    def complete_step(self, message: str, duration: Optional[float] = None) -> None:
        """Mark current step as complete."""
        if duration is not None:
            self.console.print(f"  [green]✓[/green] {message} ({duration:.2f}s)")
        else:
            self.console.print(f"  [green]✓[/green] {message}")

    def fail_step(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark current step as failed."""
        if error:
            self.console.print(f"  [red]✗[/red] {message}: {error}", style="red")
        else:
            self.console.print(f"  [red]✗[/red] {message}", style="red")

    def complete_task(self, message: str, duration: Optional[float] = None) -> None:
        """Mark entire task as complete."""
        if duration is not None:
            self.console.print(f"[bold green]✓[/bold green] {message} ({duration:.2f}s)")
        else:
            self.console.print(f"[bold green]✓[/bold green] {message}")

    def fail_task(self, message: str, error: Optional[Exception] = None) -> None:
        """Mark entire task as failed."""
        if error:
            self.console.print(f"[bold red]✗[/bold red] {message}: {error}", style="bold red")
        else:
            self.console.print(f"[bold red]✗[/bold red] {message}", style="bold red")

    def log(self, message: str, level: str = "info") -> None:
        """Log a message without affecting progress tracking."""
        # Color by log level
        colors = {
            "debug": "dim",
            "info": "blue",
            "warning": "yellow",
            "error": "red",
        }
        color = colors.get(level.lower(), "white")

        if level.lower() == "debug" and not self.verbose:
            return  # Skip debug messages unless verbose

        self.console.print(f"  [{color}]{message}[/{color}]")
