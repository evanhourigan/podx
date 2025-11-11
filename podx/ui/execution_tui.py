"""Execution TUI for displaying pipeline progress in real-time."""

import time
from typing import Any, Callable, Dict, List, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, ProgressBar, Static


class ExecutionTUI(App[Optional[Dict[str, Any]]]):
    """Full-screen TUI for displaying pipeline execution progress."""

    TITLE = "Pipeline Execution"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #execution-container {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }

    #progress-section {
        height: auto;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    #progress-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #current-step {
        text-align: center;
        color: $text;
        margin-bottom: 1;
    }

    #progress-bar-container {
        height: 3;
        margin-bottom: 1;
    }

    #progress-stats {
        text-align: center;
        color: $text-muted;
    }

    #log-section {
        height: 1fr;
        border: solid $accent;
        padding: 0;
    }

    #log-title {
        text-style: bold;
        color: $accent;
        padding: 1 1 0 1;
        background: $surface;
    }

    #log-content {
        height: 1fr;
        padding: 1;
        overflow-y: scroll;
    }

    .log-entry {
        margin: 0;
    }

    .log-starting {
        color: $warning;
    }

    .log-complete {
        color: $success;
    }

    .log-error {
        color: $error;
    }

    .log-info {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    # Reactive attributes
    current_step: reactive[str] = reactive("Initializing...")
    completed_steps: reactive[int] = reactive(0)
    total_steps: reactive[int] = reactive(0)
    elapsed_time: reactive[str] = reactive("00:00")

    def __init__(
        self,
        total_steps: int,
        verbose: bool = False,
        pipeline_executor: Optional[Callable[[Any], Dict[str, Any]]] = None,
        executor_args: Optional[Any] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize execution TUI.

        Args:
            total_steps: Total number of pipeline steps
            verbose: Whether to show verbose logging
            pipeline_executor: Optional callable to execute the pipeline
            executor_args: Optional arguments to pass to pipeline executor
        """
        super().__init__(*args, **kwargs)
        self.total_steps = total_steps
        self.verbose = verbose
        self.log_entries: List[str] = []
        self.start_time = time.time()
        self.cancelled = False
        self.result_data: Optional[Dict[str, Any]] = None
        self.pipeline_executor = pipeline_executor
        self.executor_args = executor_args
        self.execution_error: Optional[Exception] = None

    def compose(self) -> ComposeResult:
        """Compose the execution TUI layout."""
        yield Header(show_clock=False, icon="")

        with Vertical(id="execution-container"):
            # Progress section (top)
            with Container(id="progress-section"):
                yield Label("Pipeline Execution Progress", id="progress-title")
                yield Label(self.current_step, id="current-step")
                with Container(id="progress-bar-container"):
                    yield ProgressBar(
                        total=max(self.total_steps, 1),
                        show_eta=False,
                        id="progress-bar",
                    )
                yield Label(
                    f"Step {self.completed_steps}/{self.total_steps} • Elapsed: {self.elapsed_time}",
                    id="progress-stats",
                )

            # Log section (bottom)
            with Container(id="log-section"):
                yield Label("Execution Log", id="log-title")
                with VerticalScroll(id="log-content"):
                    yield Static("", id="log-text")

        yield Footer()

    def on_mount(self) -> None:
        """Start elapsed time counter and pipeline execution when mounted."""
        self.update_elapsed_time()

        # Start pipeline execution if executor provided
        if self.pipeline_executor:
            self.run_pipeline()

    def update_elapsed_time(self) -> None:
        """Update elapsed time display."""
        if not self.cancelled:
            elapsed = int(time.time() - self.start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.elapsed_time = f"{minutes:02d}:{seconds:02d}"

            # Update progress stats label
            stats = self.query_one("#progress-stats", Label)
            stats.update(
                f"Step {self.completed_steps}/{self.total_steps} • Elapsed: {self.elapsed_time}"
            )

            # Schedule next update
            self.set_timer(1.0, self.update_elapsed_time)

    def start_step(self, description: str) -> None:
        """Start a new pipeline step.

        Args:
            description: Description of the step
        """
        self.current_step = description

        # Update current step label
        step_label = self.query_one("#current-step", Label)
        step_label.update(f"→ {description}")

        # Add to log
        self.add_log_entry(f"→ {description}", "log-starting")

    def complete_step(self, message: str, duration: Optional[float] = None) -> None:
        """Complete the current step.

        Args:
            message: Completion message
            duration: Optional step duration in seconds
        """
        self.completed_steps += 1

        # Update progress bar
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=self.completed_steps)

        # Format completion message
        if duration is not None:
            from ..progress import format_duration

            duration_str = format_duration(duration)
            log_message = f"✅ {message} ({duration_str})"
        else:
            log_message = f"✅ {message}"

        # Add to log
        self.add_log_entry(log_message, "log-complete")

        # Update progress stats
        stats = self.query_one("#progress-stats", Label)
        stats.update(
            f"Step {self.completed_steps}/{self.total_steps} • Elapsed: {self.elapsed_time}"
        )

    def add_log_entry(self, message: str, style_class: str = "log-info") -> None:
        """Add an entry to the execution log.

        Args:
            message: Log message
            style_class: CSS class for styling
        """
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[dim]{timestamp}[/dim] {message}"

        self.log_entries.append(formatted_message)

        # Update log display
        log_text = self.query_one("#log-text", Static)
        log_content = "\n".join(self.log_entries)
        log_text.update(log_content)

        # Auto-scroll to bottom
        log_scroll = self.query_one("#log-content", VerticalScroll)
        log_scroll.scroll_end(animate=False)

    def log_info(self, message: str) -> None:
        """Add an info log entry (only if verbose).

        Args:
            message: Info message
        """
        if self.verbose:
            self.add_log_entry(f"[INFO] {message}", "log-info")

    def log_error(self, message: str) -> None:
        """Add an error log entry.

        Args:
            message: Error message
        """
        self.add_log_entry(f"❌ ERROR: {message}", "log-error")

    def set_result(self, result: Dict[str, Any]) -> None:
        """Set the final result and prepare to exit.

        Args:
            result: Pipeline execution result
        """
        self.result_data = result

        # Update UI to show completion
        step_label = self.query_one("#current-step", Label)
        step_label.update("✅ Pipeline Complete!")

        # Add final log entry
        self.add_log_entry("Pipeline execution completed successfully", "log-complete")

    def action_cancel(self) -> None:
        """Cancel execution and exit."""
        self.cancelled = True
        self.exit(None)

    def finish_execution(self, result: Optional[Dict[str, Any]] = None) -> None:
        """Finish execution and exit with result.

        Args:
            result: Optional result dictionary
        """
        self.exit(result or self.result_data)

    @work(exclusive=True, thread=True)
    def run_pipeline(self) -> None:
        """Run the pipeline executor in a background thread."""
        if not self.pipeline_executor:
            return

        try:
            # Execute pipeline
            result = self.pipeline_executor(self.executor_args)

            # Update TUI from thread
            self.app.call_from_thread(self.set_result, result)

            # Auto-exit after 2 seconds to let user see completion
            time.sleep(2)
            self.app.call_from_thread(self.finish_execution, result)

        except Exception as e:
            # Handle execution error
            self.execution_error = e
            error_msg = f"Pipeline execution failed: {str(e)}"
            self.app.call_from_thread(self.log_error, error_msg)
            self.app.call_from_thread(self.action_cancel)


class TUIProgress:
    """Progress tracker that integrates with ExecutionTUI.

    This is a drop-in replacement for PodxProgress that works with the TUI.
    Thread-safe for use in background workers.
    """

    def __init__(
        self, execution_tui: Optional[ExecutionTUI] = None, app: Optional[App] = None
    ):
        """Initialize TUI progress tracker.

        Args:
            execution_tui: Optional ExecutionTUI instance to send updates to
            app: Optional App instance for thread-safe calls
        """
        self.execution_tui = execution_tui
        self.app = app or execution_tui
        self.total_start_time = 0.0
        self.running = False

    def __enter__(self):
        """Enter context manager."""
        self.total_start_time = time.time()
        self.running = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self.running = False

    def start_step(self, description: str) -> None:
        """Start a new step (thread-safe).

        Args:
            description: Step description
        """
        if self.execution_tui and self.app:
            self.app.call_from_thread(self.execution_tui.start_step, description)

    def complete_step(
        self, final_message: Optional[str] = None, step_duration: Optional[float] = None
    ) -> None:
        """Complete the current step (thread-safe).

        Args:
            final_message: Final message to display
            step_duration: Optional step duration
        """
        if self.execution_tui and self.app and final_message:
            self.app.call_from_thread(
                self.execution_tui.complete_step, final_message, step_duration
            )

    def log_info(self, message: str) -> None:
        """Log an info message (thread-safe).

        Args:
            message: Info message
        """
        if self.execution_tui and self.app:
            self.app.call_from_thread(self.execution_tui.log_info, message)

    def log_error(self, message: str) -> None:
        """Log an error message (thread-safe).

        Args:
            message: Error message
        """
        if self.execution_tui and self.app:
            self.app.call_from_thread(self.execution_tui.log_error, message)

    def stop_spinner(self) -> None:
        """Stop spinner (no-op for TUI, provided for compatibility with PodxProgress)."""
        pass
