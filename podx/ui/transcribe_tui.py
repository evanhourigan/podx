"""Textual TUI components for transcription."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Static

# Available ASR models in order of sophistication
ASR_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]


class ASRModelModal(ModalScreen[Optional[str]]):
    """Modal for selecting ASR model for transcription."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    ASRModelModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.5);
    }

    #asr-modal-container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 3;
    }

    #asr-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #asr-table-container {
        height: auto;
        max-height: 20;
        border: solid $primary;
        margin-bottom: 1;
    }

    #asr-info {
        text-align: center;
        margin-top: 1;
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
            yield Static(
                "Use arrow keys to select • Enter to confirm • Esc to cancel",
                id="asr-info",
            )
        yield Footer()

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

        # Move cursor to recommended model
        if self.recommended:
            try:
                rec_idx = self.display_models.index(self.recommended)
                table.move_cursor(row=rec_idx)
            except (ValueError, IndexError):
                pass

    def action_confirm(self) -> None:
        """Confirm and return selected model."""
        table = self.query_one("#asr-table", DataTable)
        if table.cursor_row >= len(self.display_models):
            return

        selected_model = self.display_models[table.cursor_row]

        # Check if already transcribed - show warning but allow
        if selected_model in self.transcribed_models:
            # Could add confirmation modal here, but for now just allow it
            pass

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


def select_asr_model_tui(
    transcribed_models: List[str],
) -> Optional[str]:
    """Show TUI modal for ASR model selection.

    Args:
        transcribed_models: List of models already used for this episode

    Returns:
        Selected model string, or None if cancelled
    """
    app = App()
    result = None

    async def show_modal() -> None:
        nonlocal result
        modal = ASRModelModal(transcribed_models)
        result = await app.push_screen_wait(modal)
        app.exit()

    app.run(show_modal())
    return result
