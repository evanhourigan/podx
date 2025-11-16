"""Textual TUI components for transcription."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Static

# Available ASR models in order of sophistication
ASR_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]

# Model information for display
ASR_MODEL_INFO = {
    "tiny": {
        "size": "~75 MB",
        "speed": "Very Fast",
        "accuracy": "Basic",
        "description": "Fastest model, suitable for quick drafts or testing",
    },
    "base": {
        "size": "~145 MB",
        "speed": "Fast",
        "accuracy": "Good",
        "description": "Balanced speed and accuracy for most use cases",
    },
    "small": {
        "size": "~485 MB",
        "speed": "Moderate",
        "accuracy": "Very Good",
        "description": "Good accuracy with reasonable speed",
    },
    "medium": {
        "size": "~1.5 GB",
        "speed": "Slower",
        "accuracy": "Excellent",
        "description": "High accuracy for professional transcription",
    },
    "large": {
        "size": "~3 GB",
        "speed": "Slow",
        "accuracy": "Best",
        "description": "Highest accuracy, best for critical content",
    },
    "large-v2": {
        "size": "~3 GB",
        "speed": "Slow",
        "accuracy": "Best",
        "description": "Improved version of large with better accuracy",
    },
    "large-v3": {
        "size": "~3 GB",
        "speed": "Slow",
        "accuracy": "Best",
        "description": "Latest large model with best overall accuracy",
    },
    "small.en": {
        "size": "~485 MB",
        "speed": "Moderate",
        "accuracy": "Very Good",
        "description": "English-only version of small (slightly more accurate)",
    },
    "medium.en": {
        "size": "~1.5 GB",
        "speed": "Slower",
        "accuracy": "Excellent",
        "description": "English-only version of medium (slightly more accurate)",
    },
    "openai:large-v3-turbo": {
        "size": "API",
        "speed": "Fast",
        "accuracy": "Excellent",
        "description": "OpenAI's API model - requires API key, faster than local large",
    },
    "hf:distil-large-v3": {
        "size": "~1.5 GB",
        "speed": "Fast",
        "accuracy": "Very Good",
        "description": "Distilled version of large-v3 - much faster with minimal accuracy loss",
    },
}


class ASRModelModal(ModalScreen[Optional[str]]):
    """Modal for selecting ASR model for transcription (used within other apps)."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    ASRModelModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.5);
    }

    #asr-modal-container {
        width: 80;
        height: auto;
        max-height: 28;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #asr-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #asr-table-container {
        height: 10;
        border: solid $primary;
        margin-bottom: 1;
    }

    #asr-table {
        height: 100%;
    }

    #asr-detail-panel {
        height: 6;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
        background: $panel;
    }

    #asr-detail-content {
        height: 100%;
        overflow: hidden;
    }

    #asr-info {
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Select Model", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(
        self, transcribed_models: List[str], *args: Any, **kwargs: Any
    ) -> None:
        """Initialize ASR model selection modal.

        Args:
            transcribed_models: List of models already used for this episode
        """
        super().__init__(*args, **kwargs)
        self.transcribed_models = transcribed_models
        self.display_models: List[str] = []
        self.recommended: Optional[str] = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="asr-modal-container"):
            yield Static("Select ASR Model", id="asr-title")
            with Container(id="asr-table-container"):
                yield DataTable(id="asr-table", cursor_type="row", zebra_stripes=True)
            with Container(id="asr-detail-panel"):
                yield Static("", id="asr-detail-content", markup=True)
            yield Static(
                "Use arrow keys to select • Enter to confirm • Esc to cancel",
                id="asr-info",
            )

    def on_mount(self) -> None:
        """Set up the modal on mount."""
        # Determine recommended model (most sophisticated not yet transcribed)
        for model in reversed(ASR_MODELS):
            if model not in self.transcribed_models:
                self.recommended = model
                break

        if not self.recommended:
            self.recommended = ASR_MODELS[-1]  # Default to most sophisticated

        # Build display models list - ensure we have a fresh list
        self.display_models = []
        self.display_models.extend(ASR_MODELS)
        # Add common variants and provider examples
        for extra in [
            "small.en",
            "medium.en",
            "openai:large-v3-turbo",
            "hf:distil-large-v3",
        ]:
            if extra not in self.display_models:
                self.display_models.append(extra)

        # Set up table
        table = self.query_one("#asr-table", DataTable)
        table.add_column("Model", key="model", width=24)
        table.add_column("Status", key="status", width=20)

        # Populate table
        for model in self.display_models:
            if model in self.transcribed_models:
                status_text = Text("✓ Already transcribed", style="dim")
            elif model == self.recommended:
                status_text = Text("← Recommended", style="green")
            else:
                status_text = Text("", style="")

            table.add_row(
                Text(model, style="cyan"),
                status_text,
            )

        # Focus table
        table.focus()

        # Move cursor to recommended model and update detail panel
        if self.recommended:
            try:
                rec_idx = self.display_models.index(self.recommended)
                table.move_cursor(row=rec_idx)
                self._update_detail_panel(self.recommended)
            except (ValueError, IndexError):
                pass

    def _update_detail_panel(self, model: str) -> None:
        """Update detail panel with model information."""
        detail = self.query_one("#asr-detail-content", Static)

        info = ASR_MODEL_INFO.get(
            model,
            {
                "size": "Unknown",
                "speed": "Unknown",
                "accuracy": "Unknown",
                "description": "No information available",
            },
        )

        content = (
            f"[bold cyan]{model}[/bold cyan]\n"
            f"[yellow]Size:[/yellow] {info['size']}  "
            f"[yellow]Speed:[/yellow] {info['speed']}  "
            f"[yellow]Accuracy:[/yellow] {info['accuracy']}\n"
            f"[dim]{info['description']}[/dim]"
        )
        detail.update(content)

    @on(DataTable.RowHighlighted, "#asr-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight to update detail panel."""
        if event.cursor_row is not None and event.cursor_row < len(self.display_models):
            model = self.display_models[event.cursor_row]
            self._update_detail_panel(model)

    @on(DataTable.RowSelected, "#asr-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key pressed on a row)."""
        self.action_confirm()

    def action_confirm(self) -> None:
        """Confirm and return selected model."""
        table = self.query_one("#asr-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.display_models):
            selected_model = self.display_models[table.cursor_row]
            self.dismiss(selected_model)

    def action_cancel(self) -> None:
        """Cancel and return None."""
        self.dismiss(None)


class TranscriptionProgressApp(App[Optional[Dict[str, Any]]]):
    """App to show transcription progress with live updates."""

    TITLE = "Transcribing Audio"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    #progress-container {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #progress-panel {
        width: 80;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 3;
    }

    #progress-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }

    #progress-status {
        text-align: center;
        margin-bottom: 1;
    }

    #progress-details {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        episode_title: str,
        model: str,
        audio_path: Path,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize transcription progress app.

        Args:
            episode_title: Title of episode being transcribed
            model: ASR model being used
            audio_path: Path to audio file
        """
        super().__init__(*args, **kwargs)
        self.episode_title = episode_title
        self.model = model
        self.audio_path = audio_path
        self.result: Optional[Dict[str, Any]] = None

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header(show_clock=False, icon="")
        with Container(id="progress-container"):
            with Vertical(id="progress-panel"):
                yield Static("Transcription in Progress", id="progress-title")
                yield Static(f"Episode: {self.episode_title}", id="progress-status")
                yield Static(
                    f"Model: {self.model}\nAudio: {self.audio_path.name}",
                    id="progress-details",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Start transcription worker on mount."""
        self.run_transcription()

    @work(exclusive=True, thread=True)
    def run_transcription(self) -> None:
        """Run transcription in background worker.

        Note: Actual transcription logic will be passed in from transcribe.py
        This is a placeholder that shows the pattern.
        """
        # The actual transcription will be run from transcribe.py
        # This app just displays progress
        pass

    def update_status(self, message: str) -> None:
        """Update status message.

        Args:
            message: Status message to display
        """
        status = self.query_one("#progress-status", Static)
        status.update(message)

    def complete_transcription(self, result: Dict[str, Any]) -> None:
        """Complete transcription and exit with result.

        Args:
            result: Transcription result dictionary
        """
        self.result = result
        self.exit(result)


class ASRModelSelectionApp(App[Optional[str]]):
    """Standalone app for ASR model selection."""

    TITLE = "Select ASR Model"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: $background;
        align: center middle;
    }

    #asr-container {
        width: 80;
        height: auto;
        max-height: 32;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #asr-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #asr-table-container {
        height: 12;
        border: solid $primary;
        margin-bottom: 1;
    }

    #asr-table {
        height: 100%;
    }

    #asr-detail-panel {
        height: 5;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
        background: $panel;
    }

    #asr-detail-content {
        height: 100%;
    }

    #asr-info {
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Select Model", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, transcribed_models: List[str], *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.transcribed_models = transcribed_models
        self.display_models: List[str] = []
        self.recommended: Optional[str] = None

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header(show_clock=False, icon="")
        with Vertical(id="asr-container"):
            yield Static("Select ASR Model", id="asr-title")
            with Container(id="asr-table-container"):
                yield DataTable(id="asr-table", cursor_type="row", zebra_stripes=True)
            with Container(id="asr-detail-panel"):
                yield Static("", id="asr-detail-content", markup=True)
            yield Static(
                "Use arrow keys to select • Enter to confirm • Esc to cancel",
                id="asr-info",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Set up the app on mount."""
        # Determine recommended model (most sophisticated not yet transcribed)
        for model in reversed(ASR_MODELS):
            if model not in self.transcribed_models:
                self.recommended = model
                break

        if not self.recommended:
            self.recommended = ASR_MODELS[-1]  # Default to most sophisticated

        # Build display models list
        self.display_models = []
        self.display_models.extend(ASR_MODELS)
        # Add common variants and provider examples
        for extra in [
            "small.en",
            "medium.en",
            "openai:large-v3-turbo",
            "hf:distil-large-v3",
        ]:
            if extra not in self.display_models:
                self.display_models.append(extra)

        # Set up table
        table = self.query_one("#asr-table", DataTable)
        table.add_column("Model", key="model", width=24)
        table.add_column("Status", key="status", width=20)

        # Populate table
        for model in self.display_models:
            if model in self.transcribed_models:
                status_text = Text("✓ Already transcribed", style="dim")
            elif model == self.recommended:
                status_text = Text("← Recommended", style="green")
            else:
                status_text = Text("", style="")

            table.add_row(
                Text(model, style="cyan"),
                status_text,
            )

        # Focus table
        table.focus()

        # Move cursor to recommended model and update detail panel
        if self.recommended:
            try:
                rec_idx = self.display_models.index(self.recommended)
                table.move_cursor(row=rec_idx)
                self._update_detail_panel(self.recommended)
            except (ValueError, IndexError):
                pass

    def _update_detail_panel(self, model: str) -> None:
        """Update detail panel with model information."""
        detail = self.query_one("#asr-detail-content", Static)

        info = ASR_MODEL_INFO.get(
            model,
            {
                "size": "Unknown",
                "speed": "Unknown",
                "accuracy": "Unknown",
                "description": "No information available",
            },
        )

        content = (
            f"[bold cyan]{model}[/bold cyan]\n"
            f"[yellow]Size:[/yellow] {info['size']}  "
            f"[yellow]Speed:[/yellow] {info['speed']}  "
            f"[yellow]Accuracy:[/yellow] {info['accuracy']}\n"
            f"[dim]{info['description']}[/dim]"
        )
        detail.update(content)

    @on(DataTable.RowHighlighted, "#asr-table")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight to update detail panel."""
        if event.cursor_row is not None and event.cursor_row < len(self.display_models):
            model = self.display_models[event.cursor_row]
            self._update_detail_panel(model)

    @on(DataTable.RowSelected, "#asr-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key pressed on a row)."""
        self.action_confirm()

    def action_confirm(self) -> None:
        """Confirm and return selected model."""
        table = self.query_one("#asr-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.display_models):
            selected_model = self.display_models[table.cursor_row]
            self.exit(selected_model)

    def action_cancel(self) -> None:
        """Cancel and return None."""
        self.exit(None)


def select_asr_model_tui(
    transcribed_models: List[str],
) -> Optional[str]:
    """Show TUI modal for ASR model selection.

    Args:
        transcribed_models: List of models already used for this episode

    Returns:
        Selected model string, or None if cancelled
    """
    app = ASRModelSelectionApp(transcribed_models)
    return app.run()
