"""Configuration commands for podx."""

from typing import Optional

import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from podx.config import get_config
from podx.yaml_config import get_yaml_config_manager


@click.command("config")
@click.argument(
    "action",
    type=click.Choice(["show", "edit", "reset"]),
    required=False,
    default="show",
)
def config_command(action):
    """Configuration management for podx."""
    config = get_config()

    if action == "show":
        console = Console()
        table = Table(title="🔧 Podx Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Environment Variable", style="yellow")

        # Show key configuration values
        table.add_row("ASR Model", config.default_asr_model, "PODX_DEFAULT_MODEL")
        table.add_row("Compute Type", config.default_compute, "PODX_DEFAULT_COMPUTE")
        table.add_row("OpenAI Model", config.openai_model, "OPENAI_MODEL")
        table.add_row(
            "OpenAI Temperature", str(config.openai_temperature), "OPENAI_TEMPERATURE"
        )
        table.add_row("Log Level", config.log_level, "PODX_LOG_LEVEL")
        table.add_row("Log Format", config.log_format, "PODX_LOG_FORMAT")
        table.add_row("Max Retries", str(config.max_retries), "PODX_MAX_RETRIES")

        # Show API keys status (without revealing them)
        openai_status = "✅ Set" if config.openai_api_key else "❌ Not set"
        notion_status = "✅ Set" if config.notion_token else "❌ Not set"

        table.add_row("OpenAI API Key", openai_status, "OPENAI_API_KEY")
        table.add_row("Notion Token", notion_status, "NOTION_TOKEN")
        table.add_row(
            "Notion DB ID", config.notion_db_id or "❌ Not set", "NOTION_DB_ID"
        )

        console.print(table)

        console.print(
            "\n💡 [bold]Tip:[/bold] Set environment variables in your shell or .env file"
        )

    elif action == "edit":
        click.echo("📝 Opening configuration help...")
        click.echo("\nTo configure podx, set these environment variables:")
        click.echo("  export PODX_DEFAULT_MODEL=medium.en")
        click.echo("  export OPENAI_API_KEY=your_key_here")
        click.echo("  export NOTION_TOKEN=your_token_here")
        click.echo("  export NOTION_DB_ID=your_db_id_here")
        click.echo("\nOr create a .env file in your project directory.")

    elif action == "reset":
        from podx.config import reset_config

        reset_config()
        click.echo(
            "✅ Configuration cache reset. New values will be loaded on next run."
        )


def register_config_group(main_group):
    """Register config subcommands group.

    Args:
        main_group: The main Click group to register commands to
    """

    @main_group.group("config")
    def config_group():
        """Advanced YAML-based configuration management."""
        pass

    @config_group.command("init")
    def config_init():
        """Create an example YAML configuration file."""
        console = Console()
        manager = get_yaml_config_manager()

        # Check if config already exists
        if manager.config_file.exists():
            console.print(
                f"⚠️  Configuration file already exists at: {manager.config_file}"
            )
            if not click.confirm("Overwrite existing configuration?"):
                console.print("Cancelled.")
                return

        # Create example config
        manager.create_example_config()
        console.print(
            f"✅ Created example YAML configuration at: [cyan]{manager.config_file}[/cyan]"
        )
        console.print(
            "\n📝 Edit this file to customize your podcast processing settings:"
        )
        console.print("   - Multiple Notion databases with different API keys")
        console.print("   - Podcast-specific analysis types and prompts")
        console.print("   - Global pipeline defaults")
        console.print("   - Custom variables and advanced settings")

    @config_group.command("show")
    def config_show():
        """Show current YAML configuration."""
        console = Console()
        manager = get_yaml_config_manager()

        if not manager.config_file.exists():
            console.print("❌ No YAML configuration found.")
            console.print("💡 Create one with [cyan]podx config init[/cyan]")
            return

        # Read and display config file
        config_content = manager.config_file.read_text()
        syntax = Syntax(config_content, "yaml", theme="monokai", line_numbers=True)

        console.print(f"📝 Configuration: [cyan]{manager.config_file}[/cyan]")
        console.print(syntax)

    @config_group.command("validate")
    def config_validate():
        """Validate YAML configuration syntax and settings."""
        console = Console()
        manager = get_yaml_config_manager()

        if not manager.config_file.exists():
            console.print("❌ No YAML configuration found.")
            return

        try:
            config = manager.load_config()
            console.print("✅ Configuration is valid!")

            # Show summary
            if config.podcasts:
                console.print(f"📋 Found {len(config.podcasts)} podcast mappings")
            if config.notion_databases:
                console.print(
                    f"🗃️  Found {len(config.notion_databases)} Notion databases"
                )
            if config.defaults:
                console.print("⚙️  Global defaults configured")

        except Exception as e:
            console.print(f"❌ Configuration validation failed: {e}")
            console.print("💡 Check your YAML syntax and fix any errors")

    @config_group.command("databases")
    def config_databases():
        """List configured Notion databases."""
        console = Console()
        manager = get_yaml_config_manager()
        databases = manager.list_notion_databases()

        if not databases:
            console.print("📭 No Notion databases configured.")
            console.print(
                f"💡 Add them to your YAML config: [cyan]{manager.config_file}[/cyan]"
            )
            return

        table = Table(title="🗃️ Configured Notion Databases")
        table.add_column("Name", style="cyan")
        table.add_column("Database ID", style="yellow")
        table.add_column("Token", style="magenta")
        table.add_column("Podcast Prop", style="green")
        table.add_column("Date Prop", style="green")
        table.add_column("Episode Prop", style="green")
        table.add_column("Description", style="blue")

        for name, db in databases.items():

            def _mask(value: Optional[str]) -> str:
                if not value:
                    return "(none)"
                if len(value) <= 10:
                    return value
                return f"{value[:6]}…{value[-4:]}"

            masked_id = _mask(db.database_id)
            masked_token = _mask(db.token)

            table.add_row(
                name,
                masked_id,
                masked_token,
                db.podcast_property,
                db.date_property,
                db.episode_property,
                db.description or "No description",
            )

        console.print(table)
