#!/usr/bin/env python3
"""
Progress tracking for podx orchestrator with rich output and persistent spinner.
"""

import threading
import time
from typing import Optional

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

console = Console()


class PodxProgress:
    """Persistent progress tracker for podx orchestrator with spinner and elapsed time."""

    def __init__(self):
        self.spinner = Spinner("dots", text="")
        self.total_start_time: float = 0.0
        self.running = False
        self.current_text = ""
        self.live = None
        self.spinner_thread = None
        self.spinner_started = False
        self.spinner_running = False
        self.enabled = console.is_terminal

    def __enter__(self):
        self.total_start_time = time.time()
        self.running = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        if self.live:
            self.live.stop()
        if self.spinner_thread and self.spinner_thread.is_alive():
            self.spinner_thread.join(timeout=1)

    def start_step(self, description: str):
        """Start a new step with persistent spinner."""
        self.current_text = description

        # Stop any existing spinner first
        self.stop_spinner()

        # In non-TTY contexts, just log a simple line and skip spinner
        if not self.enabled:
            console.print(f"→ {description}")
            return

        def update_spinner():
            with Live(
                self.spinner, console=console, refresh_per_second=1, transient=True
            ) as live:
                self.live = live
                self.spinner_running = True
                while self.running and self.spinner_running:
                    elapsed = int(time.time() - self.total_start_time)
                    minutes = elapsed // 60
                    seconds = elapsed % 60
                    time_str = f"{minutes:02d}:{seconds:02d}"

                    # Update spinner text with description and time
                    self.spinner.text = f"{self.current_text} {time_str}"
                    time.sleep(1)
                self.spinner_running = False

        # Run the spinner in a daemon thread
        self.spinner_thread = threading.Thread(target=update_spinner, daemon=True)
        self.spinner_thread.start()
        self.spinner_started = True

    def complete_step(
        self, final_message: Optional[str] = None, step_duration: Optional[float] = None
    ):
        """Complete the current step."""
        # Clear the spinner first, before printing completion message
        self.stop_spinner()
        if final_message:
            if step_duration is not None:
                duration_str = format_duration(step_duration)
                console.print(f"✅ {final_message} ({duration_str})")
            else:
                console.print(f"✅ {final_message}")

    def stop_spinner(self):
        """Stop the current spinner display."""
        self.spinner_running = False
        try:
            if self.live:
                self.live.stop()
        finally:
            self.live = None
            # Give the thread a moment to clean up
            if self.spinner_thread and self.spinner_thread.is_alive():
                time.sleep(0.2)


def print_podx_header():
    """Print the podx orchestrator header."""
    if not console.is_terminal:
        console.print("Starting: Podx Podcast Processing Pipeline")
        return
    panel = Panel(
        Text("🎙️  Podx Podcast Processing Pipeline", style="bold blue"),
        title="🚀 Starting",
        border_style="blue",
        box=box.SQUARE,
    )
    console.print(panel)


def print_podx_success(message: str):
    """Print a success message in a nice panel."""
    if not console.is_terminal:
        console.print(f"Complete: {message}")
        return
    panel = Panel(
        Text(message, style="bold green"),
        title="✅ Complete",
        border_style="green",
        box=box.SQUARE,
    )
    console.print(panel)


def print_podx_info(message: str):
    """Print an info message in a nice panel."""
    if not console.is_terminal:
        console.print(message)
        return
    panel = Panel(
        Text(message, style="bold cyan"),
        title="ℹ️ Info",
        border_style="cyan",
        box=box.SQUARE,
    )
    console.print(panel)


def format_duration(seconds: float) -> str:
    """Convert seconds to H:MM:SS format, showing hours only when needed."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"
