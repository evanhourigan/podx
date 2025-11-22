#!/usr/bin/env python3
"""Interactive setup wizard for first-time podx configuration.

Guides users through API key setup, default settings, and optional features.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from podx.config import ProfileManager

console = Console()


class SetupWizard:
    """Interactive setup wizard for podx."""

    def __init__(self) -> None:
        """Initialize setup wizard."""
        self.config: Dict[str, str] = {}
        self.api_keys: Dict[str, str] = {}
        self.profile_manager = ProfileManager()
        self.env_file = Path.home() / ".podx" / ".env"

    def run(self) -> None:
        """Run the complete interactive setup wizard."""
        self._show_welcome()

        if not self._check_prerequisites():
            return

        # Step 1: API Keys
        self._configure_api_keys()

        # Step 2: Default Settings
        self._configure_defaults()

        # Step 3: Optional Features
        self._configure_optional_features()

        # Step 4: Summary & Save
        self._show_summary()
        if Confirm.ask("\n[bold]Save this configuration?[/bold]", default=True):
            self._save_configuration()
            self._show_next_steps()
        else:
            console.print(
                "\n[yellow]Setup cancelled. No changes were saved.[/yellow]\n"
            )

    def _show_welcome(self) -> None:
        """Display welcome message."""
        console.print("\n")
        console.print(
            Panel.fit(
                "[bold cyan]Welcome to PodX![/bold cyan]\n\n"
                "This wizard will help you configure PodX for first-time use.\n"
                "[dim]You can skip any step by pressing Enter.[/dim]",
                border_style="cyan",
            )
        )
        console.print()

    def _check_prerequisites(self) -> bool:
        """Check if user wants to continue with setup."""
        console.print("[bold]What we'll configure:[/bold]")
        console.print("  1. API keys (OpenAI, Anthropic, etc.)")
        console.print("  2. Default transcription settings")
        console.print("  3. Default output preferences")
        console.print("  4. Optional integrations\n")

        if not Confirm.ask("Ready to begin?", default=True):
            console.print("\n[dim]Run 'podx-init' anytime to complete setup.[/dim]\n")
            return False

        return True

    def _configure_api_keys(self) -> None:
        """Configure API keys for LLM providers."""
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]Step 1: API Keys[/bold cyan]")
        console.print("=" * 60 + "\n")

        console.print(
            "API keys enable AI-powered features (transcription, analysis, etc.).\n"
            "[dim]You can skip providers you don't plan to use.[/dim]\n"
        )

        # OpenAI
        self._prompt_for_api_key(
            provider="OpenAI",
            env_var="OPENAI_API_KEY",
            url="https://platform.openai.com/api-keys",
            description="GPT models and Whisper API",
        )

        # Anthropic
        self._prompt_for_api_key(
            provider="Anthropic",
            env_var="ANTHROPIC_API_KEY",
            url="https://console.anthropic.com/settings/keys",
            description="Claude models (Opus, Sonnet, Haiku)",
        )

        # OpenRouter
        if Confirm.ask(
            "\nDo you want to configure OpenRouter? (access many models via one API)",
            default=False,
        ):
            self._prompt_for_api_key(
                provider="OpenRouter",
                env_var="OPENROUTER_API_KEY",
                url="https://openrouter.ai/keys",
                description="Multi-model API aggregator",
            )

        # Notion (optional)
        if Confirm.ask("\nDo you want to configure Notion integration?", default=False):
            self._prompt_for_api_key(
                provider="Notion",
                env_var="NOTION_API_KEY",
                url="https://www.notion.so/my-integrations",
                description="Notion workspace integration",
            )

    def _prompt_for_api_key(
        self, provider: str, env_var: str, url: str, description: str
    ) -> None:
        """Prompt for a single API key.

        Args:
            provider: Provider name (e.g., "OpenAI")
            env_var: Environment variable name (e.g., "OPENAI_API_KEY")
            url: URL to get API key
            description: Provider description
        """
        # Check if already configured
        existing_key = os.getenv(env_var)

        console.print(f"\n[bold]{provider}[/bold]")
        console.print(f"[dim]{description}[/dim]")

        if existing_key:
            console.print(f"[green]✓ Already configured ({env_var})[/green]")
            if not Confirm.ask("Update this key?", default=False):
                return

        console.print(f"[dim]Get your API key at: {url}[/dim]")

        api_key = Prompt.ask(
            f"Enter your {provider} API key (or press Enter to skip)",
            password=True,
            default="",
        )

        if api_key:
            self.api_keys[env_var] = api_key
            console.print(f"[green]✓ {provider} API key saved[/green]")
        else:
            console.print(f"[dim]Skipped {provider}[/dim]")

    def _configure_defaults(self) -> None:
        """Configure default processing settings."""
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]Step 2: Default Settings[/bold cyan]")
        console.print("=" * 60 + "\n")

        # ASR Model
        console.print("[bold]Transcription Model[/bold]")
        console.print("Choose your default transcription model:\n")
        console.print("  [cyan]large-v3[/cyan] - Best quality (recommended)")
        console.print("  [dim]medium[/dim] - Balanced quality/speed")
        console.print("  [dim]base[/dim] - Fast, less accurate\n")

        asr_model = Prompt.ask(
            "Default transcription model",
            choices=["large-v3", "medium", "base"],
            default="large-v3",
        )
        self.config["default_asr_model"] = asr_model

        # LLM Model
        if self.api_keys.get("OPENAI_API_KEY") or self.api_keys.get(
            "ANTHROPIC_API_KEY"
        ):
            console.print("\n[bold]AI Analysis Model[/bold]")
            console.print("Choose your default model for summaries and analysis:\n")
            console.print("  [cyan]gpt-4o[/cyan] - Best quality (OpenAI)")
            console.print("  [dim]gpt-4o-mini[/dim] - Fast and affordable (OpenAI)")
            console.print(
                "  [dim]claude-3-5-sonnet[/dim] - Excellent reasoning (Anthropic)\n"
            )

            llm_model = Prompt.ask(
                "Default AI model",
                choices=["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet"],
                default="gpt-4o-mini",
            )
            self.config["default_llm_model"] = llm_model

        # Output directory
        console.print("\n[bold]Output Directory[/bold]")
        default_output = str(Path.home() / "podx-episodes")
        output_dir = Prompt.ask("Default output directory", default=default_output)
        self.config["default_output_dir"] = output_dir

        # Export formats
        console.print("\n[bold]Export Formats[/bold]")
        console.print(
            "Available formats: txt, srt, vtt, md, pdf, html\n"
            "[dim]Enter comma-separated formats (e.g., txt,srt,md)[/dim]"
        )
        export_formats = Prompt.ask("Default export formats", default="txt,srt,md")
        self.config["default_export_formats"] = export_formats

    def _configure_optional_features(self) -> None:
        """Configure optional features."""
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]Step 3: Optional Features[/bold cyan]")
        console.print("=" * 60 + "\n")

        # Shell completion
        console.print("[bold]Shell Completion[/bold]")
        if Confirm.ask("Install shell completion for podx commands?", default=True):
            self.config["install_completion"] = "true"
            console.print(
                "[dim]Instructions will be shown after setup completes.[/dim]"
            )

        # Built-in profiles
        console.print("\n[bold]Configuration Profiles[/bold]")
        if Confirm.ask(
            "Install built-in configuration profiles (quick, standard, high-quality)?",
            default=True,
        ):
            self.config["install_profiles"] = "true"

    def _show_summary(self) -> None:
        """Show configuration summary."""
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]Configuration Summary[/bold cyan]")
        console.print("=" * 60 + "\n")

        # API Keys
        if self.api_keys:
            console.print("[bold]API Keys:[/bold]")
            for env_var in self.api_keys:
                provider = env_var.replace("_API_KEY", "").replace("_", " ").title()
                console.print(f"  [green]✓[/green] {provider}")
            console.print()

        # Default Settings
        if self.config:
            console.print("[bold]Default Settings:[/bold]")
            for key, value in self.config.items():
                if not key.startswith("install_"):
                    label = key.replace("default_", "").replace("_", " ").title()
                    console.print(f"  {label}: [cyan]{value}[/cyan]")
            console.print()

        # Optional Features
        optional = [k for k in self.config if k.startswith("install_")]
        if optional:
            console.print("[bold]Optional Features:[/bold]")
            for key in optional:
                feature = key.replace("install_", "").replace("_", " ").title()
                console.print(f"  [green]✓[/green] {feature}")
            console.print()

    def _save_configuration(self) -> None:
        """Save configuration to disk."""
        console.print("\n[bold]Saving configuration...[/bold]")

        # Save API keys to .env
        if self.api_keys:
            self.env_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.env_file, "a") as f:
                for env_var, value in self.api_keys.items():
                    f.write(f'{env_var}="{value}"\n')
            # Set secure permissions
            os.chmod(self.env_file, 0o600)
            console.print(f"  [green]✓[/green] API keys saved to {self.env_file}")

        # Install built-in profiles
        if self.config.get("install_profiles") == "true":
            self.profile_manager.install_builtin_profiles()
            console.print("  [green]✓[/green] Built-in profiles installed")

        console.print("\n[bold green]✓ Configuration saved successfully![/bold green]")

    def _show_next_steps(self) -> None:
        """Show next steps after setup."""
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]Next Steps[/bold cyan]")
        console.print("=" * 60 + "\n")

        console.print("[bold]1. Load your API keys:[/bold]")
        console.print(f"   [cyan]source {self.env_file}[/cyan]")
        console.print("   [dim]Or restart your shell to load automatically[/dim]\n")

        if self.config.get("install_completion") == "true":
            # Detect shell
            import os

            shell = os.environ.get("SHELL", "")
            shell_name = "bash"
            if "zsh" in shell:
                shell_name = "zsh"
                shell_file = "~/.zshrc"
                setup_cmd = "mkdir -p ~/.zsh/completion && _PODX_COMPLETE=zsh_source podx > ~/.zsh/completion/_podx"
            elif "fish" in shell:
                shell_name = "fish"
                shell_file = "~/.config/fish/config.fish"
                setup_cmd = "mkdir -p ~/.config/fish/completions && _PODX_COMPLETE=fish_source podx > ~/.config/fish/completions/podx.fish"
            else:  # bash
                shell_file = "~/.bashrc"
                setup_cmd = "mkdir -p ~/.bash_completion.d && _PODX_COMPLETE=bash_source podx > ~/.bash_completion.d/podx.sh"

            console.print("[bold]2. Set up shell completion:[/bold]")
            console.print(f"   [cyan]{setup_cmd}[/cyan]")
            if shell_name != "fish":
                console.print(f"   [cyan]source {shell_file}[/cyan]")
            console.print(
                f"   [dim]Then restart your shell or run: source {shell_file}[/dim]\n"
            )

        console.print("[bold]3. Try processing your first episode:[/bold]")
        console.print(
            "   [cyan]podx-quick podcast.mp3[/cyan]  [dim]# Fast transcription[/dim]"
        )
        console.print(
            "   [cyan]podx-full podcast.mp3[/cyan]   [dim]# Complete pipeline[/dim]"
        )

        if self.config.get("install_profiles") == "true":
            console.print(
                "   [cyan]podx-config list-profiles[/cyan]  [dim]# See available profiles[/dim]"
            )

        console.print("\n[bold]4. Check configuration:[/bold]")
        console.print(
            "   [cyan]podx-models --status[/cyan]  [dim]# Verify API keys[/dim]"
        )
        console.print(
            "   [cyan]podx-config list-keys[/cyan]  [dim]# List configured keys[/dim]\n"
        )

        console.print(
            Panel.fit(
                "[bold green]Setup complete! You're ready to start using PodX.[/bold green]",
                border_style="green",
            )
        )
        console.print()
