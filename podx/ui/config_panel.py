"""Interactive configuration panel using Textual."""

from typing import Any, Dict, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, OptionList, Static
from textual.widgets.option_list import Option


class DeepcastTypeSelector(ModalScreen[str]):
    """Modal screen for selecting deepcast analysis type."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel", show=False),
    ]

    def __init__(self, current_type: str, *args: Any, **kwargs: Any) -> None:
        """Initialize deepcast type selector.

        Args:
            current_type: Currently selected deepcast type
        """
        super().__init__(*args, **kwargs)
        self.current_type = current_type

    def compose(self) -> ComposeResult:
        """Compose the modal screen."""
        from ..deepcast import ALIAS_TYPES, CANONICAL_TYPES

        # Build selectable list: canonical + aliases
        type_options = [t.value for t in CANONICAL_TYPES] + list(ALIAS_TYPES.keys())

        # Build descriptions
        desc: dict[str, str] = {
            "interview_guest_focused": "Interview; emphasize guest insights",
            "panel_discussion": "Multi-speaker panel; perspectives & dynamics",
            "solo_commentary": "Single voice; host analysis/thoughts",
            "general": "Generic structure; adapt to content",
            "host_moderated_panel": "Host sets sections; panel discussion per section",
            "cohost_commentary": "Two peers; back-and-forth commentary",
        }

        with Container(id="type-selector-container"):
            yield Label("Select Deepcast Type", id="type-selector-title")
            option_widgets = []
            for tname in type_options:
                d = desc.get(tname, "")
                prompt_text = f"{tname}\n  [dim]{d}[/dim]"
                option_widgets.append(Option(prompt_text, id=tname))

            yield OptionList(*option_widgets, id="type-options")
            yield Label("[dim]↑/↓ to navigate • Enter to select • Esc to cancel[/dim]")

    def on_mount(self) -> None:
        """Set focus and highlight current selection on mount."""
        option_list = self.query_one("#type-options", OptionList)
        option_list.focus()

        # Highlight current type if it exists
        for idx, option in enumerate(option_list._options):
            if option.id == self.current_type:
                option_list.highlighted = idx
                break

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        self.dismiss(event.option.id or self.current_type)


class ModelInput(ModalScreen[Optional[str]]):
    """Modal screen for editing model name."""

    BINDINGS = [
        Binding("escape", "dismiss_cancel", "Cancel", show=False),
    ]

    def __init__(
        self, field_name: str, current_value: str, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize model input screen.

        Args:
            field_name: Name of the field being edited
            current_value: Current field value
        """
        super().__init__(*args, **kwargs)
        self.field_name = field_name
        self.current_value = current_value

    def compose(self) -> ComposeResult:
        """Compose the modal screen."""
        with Container(id="model-input-container"):
            yield Label(f"Edit {self.field_name}", id="model-input-title")
            yield Input(
                value=self.current_value,
                placeholder=f"Enter {self.field_name.lower()}",
                id="model-input-field",
            )
            yield Label("[dim]Enter to save • Esc to cancel[/dim]")

    def on_mount(self) -> None:
        """Set focus on input field."""
        self.query_one("#model-input-field", Input).focus()

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        self.dismiss(event.value)

    def action_dismiss_cancel(self) -> None:
        """Dismiss without changes."""
        self.dismiss(None)


class ConfigPanel(ModalScreen[Optional[Dict[str, Any]]]):
    """Interactive configuration panel for pipeline options (as a modal)."""

    ENABLE_COMMAND_PALETTE = False

    # Mapping of config keys to display info (keyboard key, display name, option type)
    OPTION_INFO = {
        "diarize": ("D", "Diarize (speakers)", "toggle"),
        "preprocess": ("P", "Preprocess (merge/norm)", "toggle"),
        "restore": ("R", "Restore (LLM semantic)", "toggle"),
        "deepcast": ("C", "Deepcast (AI analysis)", "toggle"),
        "model": ("M", "ASR Model", "text"),
        "deepcast_model": ("I", "AI Model", "text"),
        "yaml_analysis_type": ("T", "Deepcast Type", "select"),
        "extract_markdown": ("X", "Extract Markdown", "toggle"),
        "deepcast_pdf": ("F", "Render PDF", "toggle"),
    }

    CSS = """
    ConfigPanel {
        align: center middle;
        background: rgba(0, 0, 0, 0.5);
    }

    #config-modal-container {
        width: 80;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 2 3;
    }

    #config-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .config-option {
        margin: 0 1;
        height: 1;
    }

    .option-key {
        color: $warning;
        text-style: bold;
    }

    .option-name {
        color: $text;
    }

    .option-value {
        color: $success;
        text-style: bold;
    }

    .option-value-no {
        color: $error;
    }

    .option-hint {
        color: $text-muted;
    }

    .section-divider {
        margin: 1 0;
        color: $text-disabled;
    }

    #instructions {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }

    #type-selector-container, #model-input-container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #type-selector-title, #model-input-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #type-options {
        height: 15;
        margin: 1 0;
    }

    #model-input-field {
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("d", "toggle_diarize", "Toggle Diarize", show=False),
        Binding("p", "toggle_preprocess", "Toggle Preprocess", show=False),
        Binding("r", "toggle_restore", "Toggle Restore", show=False),
        Binding("c", "toggle_deepcast", "Toggle Deepcast", show=False),
        Binding("m", "edit_asr_model", "Edit ASR Model", show=False),
        Binding("i", "edit_ai_model", "Edit AI Model", show=False),
        Binding("t", "select_deepcast_type", "Select Type", show=False),
        Binding("x", "toggle_markdown", "Toggle Markdown", show=False),
        Binding("f", "toggle_pdf", "Toggle PDF", show=False),
        Binding("enter", "confirm", "Continue", show=True),
        Binding("escape", "go_back", "Cancel", show=True),
    ]

    def __init__(self, config: Dict[str, Any], *args: Any, **kwargs: Any) -> None:
        """Initialize config panel.

        Args:
            config: Pipeline configuration dictionary
        """
        super().__init__(*args, **kwargs)
        self.config = config.copy()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="config-modal-container"):
            yield Static("Select the settings for the pipeline", id="config-title")

            yield self._make_option("D", "Diarize (speakers)", "diarize")
            yield self._make_option("P", "Preprocess (merge/norm)", "preprocess")
            yield self._make_option("R", "Restore (LLM semantic)", "restore")
            yield self._make_option("C", "Deepcast (AI analysis)", "deepcast")

            yield Static("─" * 60, classes="section-divider")

            yield self._make_text_option("M", "ASR Model", "model")
            yield self._make_text_option("I", "AI Model", "deepcast_model")
            yield self._make_select_option("T", "Deepcast Type", "yaml_analysis_type")

            yield Static("─" * 60, classes="section-divider")

            yield self._make_option("X", "Extract Markdown", "extract_markdown")
            yield self._make_option("F", "Render PDF", "deepcast_pdf")

            yield Static(
                "Press key to toggle • Enter to continue • Esc to go back",
                id="instructions",
            )

    def _make_option(self, key: str, name: str, config_key: str) -> Static:
        """Create a toggle option widget.

        Args:
            key: Keyboard shortcut key
            name: Display name
            config_key: Key in config dictionary

        Returns:
            Static widget displaying the option
        """
        value = self.config.get(config_key, False)
        value_str = "✓ yes" if value else "✗ no"
        value_class = "option-value" if value else "option-value-no"

        return Static(
            f"[option-key]\\[{key}][/option-key] "
            f"[option-name]{name:<25}[/option-name] : "
            f"[{value_class}]{value_str}[/{value_class}]",
            classes="config-option",
            id=f"opt-{config_key}",
        )

    def _make_text_option(self, key: str, name: str, config_key: str) -> Static:
        """Create a text input option widget.

        Args:
            key: Keyboard shortcut key
            name: Display name
            config_key: Key in config dictionary

        Returns:
            Static widget displaying the option
        """
        value = self.config.get(config_key) or ""
        return Static(
            f"[option-key]\\[{key}][/option-key] "
            f"[option-name]{name:<25}[/option-name] : "
            f"[option-value]{value:<20}[/option-value] [option-hint]\\[edit][/option-hint]",
            classes="config-option",
            id=f"opt-{config_key}",
        )

    def _make_select_option(self, key: str, name: str, config_key: str) -> Static:
        """Create a select option widget.

        Args:
            key: Keyboard shortcut key
            name: Display name
            config_key: Key in config dictionary

        Returns:
            Static widget displaying the option
        """
        value = self.config.get(config_key) or "general"
        return Static(
            f"[option-key]\\[{key}][/option-key] "
            f"[option-name]{name:<25}[/option-name] : "
            f"[option-value]{value:<20}[/option-value] [option-hint]\\[select][/option-hint]",
            classes="config-option",
            id=f"opt-{config_key}",
        )

    def _update_option(self, config_key: str) -> None:
        """Update the display of a toggle option.

        Args:
            config_key: Key in config dictionary
        """
        if config_key not in self.OPTION_INFO:
            return

        key, name, _ = self.OPTION_INFO[config_key]
        value = self.config.get(config_key, False)
        value_str = "✓ yes" if value else "✗ no"
        value_class = "option-value" if value else "option-value-no"

        option = self.query_one(f"#opt-{config_key}", Static)
        option.update(
            f"[option-key]\\[{key}][/option-key] "
            f"[option-name]{name:<25}[/option-name] : "
            f"[{value_class}]{value_str}[/{value_class}]"
        )

    def _update_text_option(self, config_key: str) -> None:
        """Update the display of a text option.

        Args:
            config_key: Key in config dictionary
        """
        if config_key not in self.OPTION_INFO:
            return

        key, name, _ = self.OPTION_INFO[config_key]
        value = self.config.get(config_key) or ""

        option = self.query_one(f"#opt-{config_key}", Static)
        option.update(
            f"[option-key]\\[{key}][/option-key] "
            f"[option-name]{name:<25}[/option-name] : "
            f"[option-value]{value:<20}[/option-value] [option-hint]\\[edit][/option-hint]"
        )

    def _update_select_option(self, config_key: str) -> None:
        """Update the display of a select option.

        Args:
            config_key: Key in config dictionary
        """
        if config_key not in self.OPTION_INFO:
            return

        key, name, _ = self.OPTION_INFO[config_key]
        value = self.config.get(config_key) or "general"

        option = self.query_one(f"#opt-{config_key}", Static)
        option.update(
            f"[option-key]\\[{key}][/option-key] "
            f"[option-name]{name:<25}[/option-name] : "
            f"[option-value]{value:<20}[/option-value] [option-hint]\\[select][/option-hint]"
        )

    def action_toggle_diarize(self) -> None:
        """Toggle diarize option."""
        self.config["diarize"] = not self.config.get("diarize", False)
        self._update_option("diarize")

    def action_toggle_preprocess(self) -> None:
        """Toggle preprocess option."""
        self.config["preprocess"] = not self.config.get("preprocess", False)
        self._update_option("preprocess")

    def action_toggle_restore(self) -> None:
        """Toggle restore option."""
        self.config["restore"] = not self.config.get("restore", False)
        self._update_option("restore")

    def action_toggle_deepcast(self) -> None:
        """Toggle deepcast option."""
        self.config["deepcast"] = not self.config.get("deepcast", False)
        self._update_option("deepcast")

    def action_toggle_markdown(self) -> None:
        """Toggle extract markdown option."""
        self.config["extract_markdown"] = not self.config.get("extract_markdown", False)
        self._update_option("extract_markdown")

    def action_toggle_pdf(self) -> None:
        """Toggle render PDF option."""
        self.config["deepcast_pdf"] = not self.config.get("deepcast_pdf", False)
        self._update_option("deepcast_pdf")

    def action_edit_asr_model(self) -> None:
        """Edit ASR model."""

        async def edit_model() -> None:
            result = await self.push_screen_wait(
                ModelInput("ASR Model", self.config.get("model") or "")
            )
            if result is not None:
                self.config["model"] = result
                self._update_text_option("model")

        self.run_worker(edit_model())

    def action_edit_ai_model(self) -> None:
        """Edit AI model."""

        async def edit_model() -> None:
            result = await self.push_screen_wait(
                ModelInput("AI Model", self.config.get("deepcast_model") or "")
            )
            if result is not None:
                self.config["deepcast_model"] = result
                self._update_text_option("deepcast_model")

        self.run_worker(edit_model())

    def action_select_deepcast_type(self) -> None:
        """Select deepcast type."""

        async def select_type() -> None:
            result = await self.push_screen_wait(
                DeepcastTypeSelector(self.config.get("yaml_analysis_type") or "general")
            )
            if result:
                self.config["yaml_analysis_type"] = result
                self._update_select_option("yaml_analysis_type")

        self.run_worker(select_type())

    def action_confirm(self) -> None:
        """Confirm and return config."""
        self.dismiss(self.config)

    def action_go_back(self) -> None:
        """Go back to episode selection without changes."""
        self.dismiss(None)


class ConfigPanelApp(App[Optional[Dict[str, Any]]]):
    """Standalone app wrapper for ConfigPanel modal (for backwards compatibility)."""

    TITLE = "Pipeline Settings"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: $surface;
    }

    #base-container {
        width: 100%;
        height: 100%;
        align: center middle;
    }
    """

    def __init__(self, config: Dict[str, Any], *args: Any, **kwargs: Any) -> None:
        """Initialize wrapper app.

        Args:
            config: Pipeline configuration dictionary
        """
        super().__init__(*args, **kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose a minimal base screen (modal will overlay)."""
        from textual.containers import Container
        from textual.widgets import Static

        yield Header(show_clock=False, icon="")
        with Container(id="base-container"):
            yield Static("Loading configuration...", id="loading-message")
        yield Footer()

    def on_mount(self) -> None:
        """Show config panel modal on mount."""
        # Run in a worker context for push_screen_wait
        self.show_config_panel()

    @work(exclusive=True)
    async def show_config_panel(self) -> None:
        """Show the config panel modal and exit with result."""
        result = await self.push_screen_wait(ConfigPanel(self.config))
        self.exit(result)


def configure_pipeline_interactive(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run interactive configuration panel and return updated config.

    Args:
        config: Initial pipeline configuration

    Returns:
        Updated configuration dictionary, or None if cancelled
    """
    import time

    from ..logging import restore_logging, suppress_logging

    # Brief pause to ensure terminal is ready after previous TUI
    time.sleep(0.1)

    # Suppress logging during TUI interaction
    suppress_logging()

    try:
        app = ConfigPanelApp(config)
        result = app.run()
        return result
    except Exception as e:
        # If there's an error, restore logging and show it
        restore_logging()
        print(f"❌ Error launching configuration panel: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        # Always restore logging after TUI exits
        restore_logging()
