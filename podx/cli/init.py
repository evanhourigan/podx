#!/usr/bin/env python3
"""CLI command for interactive first-time setup.

Provides a user-friendly wizard for configuring podx.
"""

import click

from podx.cli.setup_wizard import SetupWizard


@click.command()
def main() -> None:
    """Interactive setup wizard for first-time configuration.

    Guides you through:
    - API key configuration (OpenAI, Anthropic, etc.)
    - Default transcription and AI settings
    - Output preferences
    - Optional features (shell completion, profiles)

    Examples:
        # Run interactive setup
        podx-init

        # After setup, verify configuration
        podx-models --status
        podx-config list-keys
    """
    wizard = SetupWizard()
    wizard.run()


if __name__ == "__main__":
    main()
