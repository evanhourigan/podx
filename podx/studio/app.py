"""PodX Studio - Main application."""


from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

# Import PodX SDK
from podx import (
    ManifestManager,
    YouTubeEngine,
    __version__,
    find_feed_url,
)


class WelcomeScreen(Screen):
    """Welcome screen with quick actions."""

    CSS = """
    WelcomeScreen {
        align: center middle;
    }

    #welcome-box {
        width: 80;
        height: auto;
        border: solid $accent;
        padding: 2 4;
    }

    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 1 0;
    }

    #subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }

    .action-button {
        width: 100%;
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("escape", "quit_app", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with Container(id="welcome-box"):
            yield Static(f"PodX Studio v{__version__}", id="title")
            yield Static(
                "Interactive podcast processing pipeline", id="subtitle"
            )
            yield Button("📥 Fetch Episode", id="fetch", classes="action-button")
            yield Button(
                "🎙️ Process Audio", id="process", classes="action-button"
            )
            yield Button("📊 View Episodes", id="browse", classes="action-button")
            yield Button("⚙️  Settings", id="settings", classes="action-button")
            yield Button("❌ Exit", id="exit", classes="action-button")
            yield Static("", id="session-status")
        yield Footer()

    def on_mount(self) -> None:
        """Check for incomplete sessions on mount."""
        manager = ManifestManager()
        incomplete = manager.get_incomplete_sessions()

        if incomplete:
            status = self.query_one("#session-status", Static)
            status.update(
                f"\n💡 {len(incomplete)} incomplete pipeline session(s) found\n"
                "Use 'podx run --resume' to continue processing"
            )

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.app.exit()

    @on(Button.Pressed, "#fetch")
    def action_fetch(self) -> None:
        """Go to fetch screen."""
        self.app.push_screen(FetchScreen())

    @on(Button.Pressed, "#process")
    def action_process(self) -> None:
        """Go to process screen."""
        self.app.push_screen(ProcessScreen())

    @on(Button.Pressed, "#browse")
    def action_browse(self) -> None:
        """Go to browse screen."""
        self.app.push_screen(BrowseScreen())

    @on(Button.Pressed, "#settings")
    def action_settings(self) -> None:
        """Go to settings screen."""
        self.app.push_screen(SettingsScreen())

    @on(Button.Pressed, "#exit")
    def action_exit(self) -> None:
        """Exit the app."""
        self.app.exit()


class FetchScreen(Screen):
    """Screen for fetching podcast episodes."""

    CSS = """
    FetchScreen {
        layout: vertical;
    }

    #fetch-container {
        width: 90;
        height: auto;
        border: solid $accent;
        padding: 2 4;
        margin: 2 auto;
    }

    .input-row {
        height: auto;
        margin: 1 0;
    }

    .input-label {
        width: 20;
        text-align: right;
        padding-right: 2;
    }

    .input-field {
        width: 1fr;
    }

    #status {
        height: auto;
        min-height: 3;
        border: solid $primary;
        padding: 1 2;
        margin: 2 0;
    }

    .button-row {
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    status_text: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with ScrollableContainer():
            with Container(id="fetch-container"):
                yield Static("Fetch Podcast Episode", classes="title")

                with Horizontal(classes="input-row"):
                    yield Static("Show Name:", classes="input-label")
                    yield Input(
                        placeholder="e.g., Lenny's Podcast",
                        id="show-name",
                        classes="input-field",
                    )

                with Horizontal(classes="input-row"):
                    yield Static("Episode Date:", classes="input-label")
                    yield Input(
                        placeholder="YYYY-MM-DD (optional)",
                        id="episode-date",
                        classes="input-field",
                    )

                with Horizontal(classes="input-row"):
                    yield Static("YouTube URL:", classes="input-label")
                    yield Input(
                        placeholder="https://youtube.com/watch?v=...",
                        id="youtube-url",
                        classes="input-field",
                    )

                with Horizontal(classes="button-row"):
                    yield Button("🔍 Fetch", id="fetch-button", variant="primary")
                    yield Button("« Back", id="back-button")

                yield Static("", id="status")

        yield Footer()

    def watch_status_text(self, new_status: str) -> None:
        """Update status display."""
        status_widget = self.query_one("#status", Static)
        status_widget.update(new_status)

    def action_go_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    @on(Button.Pressed, "#fetch-button")
    async def handle_fetch(self) -> None:
        """Handle fetch button press."""
        show_input = self.query_one("#show-name", Input)
        youtube_input = self.query_one("#youtube-url", Input)

        if youtube_input.value:
            self.status_text = "Fetching YouTube video..."
            try:
                # Use YouTube engine
                engine = YouTubeEngine()
                result = engine.download(youtube_input.value)
                self.status_text = (
                    f"✓ Downloaded: {result.get('title', 'Unknown')}"
                )
            except Exception as e:
                self.status_text = f"✗ Error: {str(e)}"

        elif show_input.value:
            self.status_text = f"Searching for: {show_input.value}..."
            try:
                feed_url = find_feed_url(show_input.value)
                self.status_text = f"✓ Found feed: {feed_url}"
            except Exception as e:
                self.status_text = f"✗ Error: {str(e)}"
        else:
            self.status_text = "⚠ Please enter a show name or YouTube URL"

    @on(Button.Pressed, "#back-button")
    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class ProcessScreen(Screen):
    """Screen for processing audio files."""

    CSS = """
    ProcessScreen {
        layout: vertical;
    }

    #process-container {
        width: 90;
        height: auto;
        border: solid $accent;
        padding: 2 4;
        margin: 2 auto;
    }

    .process-step {
        margin: 1 0;
    }

    .step-label {
        text-style: bold;
        color: $accent;
    }

    .button-row {
        margin-top: 2;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with ScrollableContainer():
            with Container(id="process-container"):
                yield Static("Process Audio Pipeline", classes="title")

                yield Static(
                    "💡 Use CLI commands for full pipeline processing:",
                    classes="step-label",
                )
                yield Static("")
                yield Static("podx-transcribe - Transcribe audio with Whisper")
                yield Static("podx-diarize - Add speaker identification")
                yield Static("podx-deepcast - AI analysis and summarization")
                yield Static("podx-export - Export to TXT/SRT/VTT/MD")
                yield Static("")
                yield Static("Or use: podx run --interactive")

                with Horizontal(classes="button-row"):
                    yield Button("« Back", id="back-button")

        yield Footer()

    def action_go_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    @on(Button.Pressed, "#back-button")
    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class BrowseScreen(Screen):
    """Screen for browsing processed episodes."""

    CSS = """
    BrowseScreen {
        layout: vertical;
    }

    #browse-container {
        width: 90;
        height: 100%;
        border: solid $accent;
        padding: 2 4;
        margin: 2 auto;
    }

    #episode-list {
        height: 1fr;
        margin: 2 0;
    }

    .button-row {
        margin-top: 1;
    }

    .episode-item {
        padding: 1 2;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with Container(id="browse-container"):
            yield Static("Browse Episodes", classes="title")

            yield ListView(id="episode-list")

            with Horizontal(classes="button-row"):
                yield Button("🔄 Refresh", id="refresh-button")
                yield Button("« Back", id="back-button")

        yield Footer()

    def on_mount(self) -> None:
        """Load episodes when screen mounts."""
        self.load_episodes()

    def load_episodes(self) -> None:
        """Scan current directory for processed episodes using manifest."""
        list_view = self.query_one("#episode-list", ListView)
        list_view.clear()

        # Use ManifestManager to scan and sync
        manager = ManifestManager()
        manifest = manager.scan_and_sync()

        if manifest.episodes:
            # Sort by date (newest first)
            episodes = sorted(
                manifest.episodes,
                key=lambda e: (e.show, e.date),
                reverse=True,
            )

            for ep in episodes:
                # Build stage badges
                badges = []
                stage_order = ["fetch", "transcribe", "diarize", "deepcast", "export", "notion"]

                for stage in stage_order:
                    if stage in ep.stages:
                        stage_info = ep.stages[stage]
                        if stage_info.completed:
                            badges.append(f"✓{stage[:4]}")
                        elif stage_info.progress > 0:
                            pct = int(stage_info.progress * 100)
                            badges.append(f"⏳{stage[:4]}({pct}%)")
                        else:
                            badges.append(f"○{stage[:4]}")

                badge_str = " ".join(badges) if badges else "no stages"

                # Build episode line with title if available
                title_part = f" - {ep.title}" if ep.title else ""
                item_text = f"📁 {ep.show} / {ep.date}{title_part}\n   {badge_str}"

                list_view.append(ListItem(Label(item_text)))

            self.notify(f"Found {len(episodes)} episode(s)", severity="information")
        else:
            list_view.append(
                ListItem(
                    Label("No episodes found. Process audio first with podx CLI commands.")
                )
            )

    def action_go_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    def action_refresh(self) -> None:
        """Refresh episode list."""
        self.load_episodes()

    @on(Button.Pressed, "#refresh-button")
    def handle_refresh(self) -> None:
        """Handle refresh button."""
        self.load_episodes()

    @on(Button.Pressed, "#back-button")
    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class SettingsScreen(Screen):
    """Screen for app settings."""

    CSS = """
    SettingsScreen {
        layout: vertical;
    }

    #settings-container {
        width: 90;
        height: auto;
        border: solid $accent;
        padding: 2 4;
        margin: 2 auto;
    }

    .setting-row {
        height: auto;
        margin: 1 0;
    }

    .button-row {
        margin-top: 2;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with ScrollableContainer():
            with Container(id="settings-container"):
                yield Static("Settings", classes="title")

                with Vertical():
                    yield Static("ASR Model: base", classes="setting-row")
                    yield Static("AI Model: gpt-4.1", classes="setting-row")
                    yield Static("Output Directory: ./", classes="setting-row")
                    yield Static(f"Working Directory: {Path.cwd()}", classes="setting-row")

                yield Static("\n💡 Use environment variables or config file to customize settings")
                yield Static("See docs/QUICK_START.md for configuration options")

                with Horizontal(classes="button-row"):
                    yield Button("« Back", id="back-button")

        yield Footer()

    def action_go_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()

    @on(Button.Pressed, "#back-button")
    def action_back(self) -> None:
        """Go back to welcome screen."""
        self.app.pop_screen()


class StudioApp(App):
    """PodX Studio - Interactive TUI application."""

    TITLE = "PodX Studio"
    CSS = """
    Screen {
        background: $surface;
    }

    .title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 1 0 2 0;
    }
    """

    # Disable command palette
    ENABLE_COMMAND_PALETTE = False

    # No app-level bindings - let screens handle their own
    BINDINGS = []

    def on_mount(self) -> None:
        """Initialize the app."""
        self.push_screen(WelcomeScreen())


def main() -> None:
    """Entry point for PodX Studio."""
    app = StudioApp()
    app.run()


if __name__ == "__main__":
    main()
