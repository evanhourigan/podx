"""CLI commands for deepcast template management.

Handles:
- Listing available templates
- Showing template details
- Previewing template output (dry-run without LLM calls)
- Exporting templates to YAML
- Importing templates from YAML files or URLs
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import tiktoken
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger
from podx.templates.manager import TemplateError, TemplateManager

console = Console()
logger = get_logger(__name__)


@click.group(help="Manage deepcast analysis templates")
def main():
    """Template management commands."""
    pass


# ============================================================================
# Template Listing and Information
# ============================================================================


@main.command(name="list", help="List all available templates")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Output format")
def list_templates(format: str):
    """List all available deepcast templates."""
    try:
        manager = TemplateManager()
        templates = manager.list_templates()

        if format == "json":
            output = []
            for name in templates:
                template = manager.load(name)
                output.append({
                    "name": template.name,
                    "description": template.description,
                    "format": template.format,
                    "variables": template.variables,
                })
            click.echo(json.dumps(output, indent=2))
            return

        # Table format
        table = Table(title="Available Deepcast Templates", show_header=True, box=None, expand=False)
        table.add_column("Template", style="cyan bold", no_wrap=True, width=23)
        table.add_column("Description & Example Podcasts", style="white", ratio=1)

        for name in templates:
            template = manager.load(name)

            # Parse description to extract main description and examples
            desc = template.description
            examples = ""

            if "Format:" in desc:
                # Extract the format description part
                parts = desc.split("Example podcasts:")
                desc = parts[0].replace("Format:", "").strip()
                if len(parts) > 1:
                    # Get first 2-3 podcast examples
                    example_text = parts[1].strip()
                    examples_list = [e.strip() for e in example_text.split(",")[:3]]
                    examples = ", ".join(examples_list)

            # Format the display with better readability
            display_desc = desc
            if examples:
                display_desc = f"{desc}\n[dim italic]Examples: {examples}[/dim italic]"

            table.add_row(
                template.name,
                display_desc
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing templates: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR.value)


@main.command(name="show", help="Show detailed information about a template")
@click.argument("template_name")
def show_template(template_name: str):
    """Show detailed information about a specific template."""
    try:
        manager = TemplateManager()
        template = manager.load(template_name)

        console.print(f"\n[bold cyan]Template:[/bold cyan] {template.name}")
        console.print(f"[bold magenta]Format:[/bold magenta] {template.format or 'N/A'}")
        console.print(f"[bold yellow]Variables:[/bold yellow] {', '.join(template.variables)}")
        console.print(f"\n[bold]Description:[/bold]\n{template.description}\n")

        console.print(Panel(template.system_prompt, title="System Prompt", border_style="blue"))
        console.print(Panel(template.user_prompt[:500] + "..." if len(template.user_prompt) > 500 else template.user_prompt,
                          title="User Prompt (preview)", border_style="green"))

    except TemplateError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR.value)


# ============================================================================
# Template Preview (Dry-run)
# ============================================================================


@main.command(name="preview", help="Preview template output without making LLM calls")
@click.argument("template_name")
@click.option("--title", help="Episode title")
@click.option("--show", help="Show/podcast name")
@click.option("--duration", type=int, help="Episode duration in minutes")
@click.option("--transcript", help="Path to transcript file or sample text")
@click.option("--speakers", help="Speaker names/info (comma-separated)")
@click.option("--speaker-count", type=int, help="Number of speakers")
@click.option("--date", help="Episode date")
@click.option("--description", help="Episode description")
@click.option("--vars-json", help="Path to JSON file with all variables")
@click.option("--sample", is_flag=True, help="Use sample data for preview")
@click.option("--cost", is_flag=True, help="Estimate token count and cost")
@click.option(
    "--model",
    help="Model for cost estimation. Examples: gpt-5, gpt-5-nano, gpt-4.1, o3, claude-opus-4.5, gemini-2.5-flash, deepseek-chat",
    default="gpt-5",
)
def preview_template(
    template_name: str,
    title: Optional[str],
    show: Optional[str],
    duration: Optional[int],
    transcript: Optional[str],
    speakers: Optional[str],
    speaker_count: Optional[int],
    date: Optional[str],
    description: Optional[str],
    vars_json: Optional[str],
    sample: bool,
    cost: bool,
    model: str,
):
    """Preview template output without making LLM calls.

    Provides a dry-run mode to test template rendering with sample or real data.
    Optionally estimates token count and API cost.

    Examples:
        podx templates preview interview-1on1 --sample
        podx templates preview interview-1on1 --title "My Episode" --duration 60 --transcript transcript.txt
        podx templates preview interview-1on1 --vars-json variables.json --cost
    """
    try:
        manager = TemplateManager()
        template = manager.load(template_name)

        # Build context from inputs
        context = {}

        if vars_json:
            # Load variables from JSON file
            vars_path = Path(vars_json)
            if not vars_path.exists():
                console.print(f"[red]Error: JSON file not found: {vars_json}[/red]")
                sys.exit(ExitCode.GENERAL_ERROR.value)

            with open(vars_path, "r") as f:
                context = json.load(f)

        elif sample:
            # Use sample data
            context = {
                "title": "Sample Episode: The Future of AI",
                "show": "Tech Talk Podcast",
                "duration": 45,
                "transcript": "This is a sample transcript with approximately 500 words of content discussing artificial intelligence, machine learning, and the future of technology. " * 50,
                "speakers": "Host: Jane Doe, Guest: Dr. John Smith",
                "speaker_count": 2,
                "date": "2024-11-24",
                "description": "A fascinating discussion about the future of artificial intelligence and its impact on society.",
            }
        else:
            # Build from individual options
            if title:
                context["title"] = title
            if show:
                context["show"] = show
            if duration:
                context["duration"] = duration
            if transcript:
                # Check if it's a file path
                transcript_path = Path(transcript)
                if transcript_path.exists():
                    with open(transcript_path, "r") as f:
                        context["transcript"] = f.read()
                else:
                    # Use as literal text
                    context["transcript"] = transcript
            if speakers:
                context["speakers"] = speakers
            if speaker_count:
                context["speaker_count"] = speaker_count
            if date:
                context["date"] = date
            if description:
                context["description"] = description

        # Check for missing required variables
        missing = set(template.variables) - set(context.keys())
        if missing:
            console.print(f"[yellow]Warning: Missing required variables: {', '.join(missing)}[/yellow]")
            console.print("[dim]Using placeholder values for missing variables...[/dim]\n")

            # Fill with placeholders
            for var in missing:
                if var == "transcript":
                    context[var] = "[Sample transcript content would go here...]"
                elif var == "duration":
                    context[var] = 30
                elif var == "speaker_count":
                    context[var] = 2
                else:
                    context[var] = f"[{var} placeholder]"

        # Render template
        system_prompt, user_prompt = template.render(context)

        # Display preview
        console.print("\n[bold cyan]═══ Template Preview ═══[/bold cyan]\n")
        console.print(f"[bold]Template:[/bold] {template.name}")
        console.print(f"[bold]Format:[/bold] {template.format or 'N/A'}\n")

        console.print(Panel(system_prompt, title="System Prompt", border_style="blue"))
        console.print(Panel(user_prompt, title="User Prompt", border_style="green"))

        # Token counting and cost estimation
        if cost:
            try:
                # Model pricing (per 1M tokens) - Updated January 2025 (Standard tier)
                MODEL_PRICING = {
                    # OpenAI GPT-5.x family (Latest - 2025)
                    "gpt-5.1": {"input": 1.25, "output": 10.00, "name": "GPT-5.1"},
                    "gpt-5": {"input": 1.25, "output": 10.00, "name": "GPT-5"},
                    "gpt-5-mini": {"input": 0.25, "output": 2.00, "name": "GPT-5 mini"},
                    "gpt-5-nano": {"input": 0.05, "output": 0.40, "name": "GPT-5 nano"},
                    "gpt-5-pro": {"input": 15.00, "output": 120.00, "name": "GPT-5 Pro"},
                    # OpenAI GPT-4.1 family
                    "gpt-4.1": {"input": 2.00, "output": 8.00, "name": "GPT-4.1"},
                    "gpt-4.1-mini": {"input": 0.40, "output": 1.60, "name": "GPT-4.1 mini"},
                    "gpt-4.1-nano": {"input": 0.10, "output": 0.40, "name": "GPT-4.1 nano"},
                    # OpenAI GPT-4o family
                    "gpt-4o": {"input": 2.50, "output": 10.00, "name": "GPT-4o"},
                    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "name": "GPT-4o mini"},
                    "chatgpt-4o-latest": {"input": 5.00, "output": 15.00, "name": "ChatGPT-4o Latest"},
                    # OpenAI O-series (reasoning models)
                    "o1": {"input": 15.00, "output": 60.00, "name": "O1"},
                    "o1-mini": {"input": 1.10, "output": 4.40, "name": "O1 mini"},
                    "o1-pro": {"input": 150.00, "output": 600.00, "name": "O1 Pro"},
                    "o3": {"input": 2.00, "output": 8.00, "name": "O3"},
                    "o3-mini": {"input": 1.10, "output": 4.40, "name": "O3 mini"},
                    "o3-pro": {"input": 20.00, "output": 80.00, "name": "O3 Pro"},
                    "o4-mini": {"input": 1.10, "output": 4.40, "name": "O4 mini"},
                    # OpenAI legacy
                    "gpt-4-turbo": {"input": 10.00, "output": 30.00, "name": "GPT-4 Turbo"},
                    "gpt-4": {"input": 30.00, "output": 60.00, "name": "GPT-4"},
                    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "name": "GPT-3.5 Turbo"},
                    # Anthropic Claude family (2025 updates)
                    "claude-opus-4.5": {"input": 5.00, "output": 25.00, "name": "Claude Opus 4.5"},
                    "claude-4-5-opus": {"input": 5.00, "output": 25.00, "name": "Claude Opus 4.5"},
                    "claude-sonnet-4.5": {"input": 3.00, "output": 15.00, "name": "Claude Sonnet 4.5"},
                    "claude-4-5-sonnet": {"input": 3.00, "output": 15.00, "name": "Claude Sonnet 4.5"},
                    "claude-haiku-4.5": {"input": 1.00, "output": 5.00, "name": "Claude Haiku 4.5"},
                    "claude-4-5-haiku": {"input": 1.00, "output": 5.00, "name": "Claude Haiku 4.5"},
                    "claude-opus-4.1": {"input": 15.00, "output": 75.00, "name": "Claude Opus 4.1"},
                    "claude-opus-4": {"input": 15.00, "output": 75.00, "name": "Claude Opus 4"},
                    "claude-4-0-opus": {"input": 15.00, "output": 75.00, "name": "Claude Opus 4.0"},
                    "claude-sonnet-4": {"input": 3.00, "output": 15.00, "name": "Claude Sonnet 4"},
                    "claude-sonnet-3.7": {"input": 3.00, "output": 15.00, "name": "Claude Sonnet 3.7"},
                    "claude-3-7-sonnet": {"input": 3.00, "output": 15.00, "name": "Claude 3.7 Sonnet"},
                    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "name": "Claude 3.5 Sonnet"},
                    "claude-3-5-haiku": {"input": 0.80, "output": 4.00, "name": "Claude 3.5 Haiku"},
                    "claude-3-opus": {"input": 15.00, "output": 75.00, "name": "Claude 3 Opus"},
                    "claude-3-haiku": {"input": 0.25, "output": 1.25, "name": "Claude 3 Haiku"},
                    # Google Gemini family (2025 updates)
                    "gemini-2.5-flash": {"input": 0.10, "output": 0.40, "name": "Gemini 2.5 Flash"},
                    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40, "name": "Gemini 2.5 Flash Lite"},
                    "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "name": "Gemini 2.0 Flash"},
                    "gemini-1.5-pro": {"input": 1.25, "output": 5.00, "name": "Gemini 1.5 Pro"},
                    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "name": "Gemini 1.5 Flash"},
                    "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15, "name": "Gemini 1.5 Flash-8B"},
                    # Meta Llama (via various providers, using typical pricing)
                    "llama-3.3-70b": {"input": 0.60, "output": 0.60, "name": "Llama 3.3 70B"},
                    "llama-3.1-405b": {"input": 3.00, "output": 3.00, "name": "Llama 3.1 405B"},
                    "llama-3.1-70b": {"input": 0.60, "output": 0.60, "name": "Llama 3.1 70B"},
                    "llama-3.1-8b": {"input": 0.20, "output": 0.20, "name": "Llama 3.1 8B"},
                    # DeepSeek
                    "deepseek-chat": {"input": 0.27, "output": 1.10, "name": "DeepSeek Chat"},
                    "deepseek-reasoner": {"input": 0.55, "output": 2.19, "name": "DeepSeek Reasoner"},
                    # Mistral AI
                    "mistral-large": {"input": 2.00, "output": 6.00, "name": "Mistral Large"},
                    "mistral-small": {"input": 0.20, "output": 0.60, "name": "Mistral Small"},
                    "mistral-nemo": {"input": 0.15, "output": 0.15, "name": "Mistral Nemo"},
                    # Cohere
                    "command-r-plus": {"input": 2.50, "output": 10.00, "name": "Command R+"},
                    "command-r": {"input": 0.15, "output": 0.60, "name": "Command R"},
                }

                # Normalize model name
                model_key = model.lower()
                if model_key not in MODEL_PRICING:
                    console.print(f"[yellow]Warning: Unknown model '{model}', using gpt-5 rates[/yellow]")
                    model_key = "gpt-5"

                pricing = MODEL_PRICING[model_key]

                enc = tiktoken.get_encoding("cl100k_base")  # Works for GPT-4, Claude, Gemini

                system_tokens = len(enc.encode(system_prompt))
                user_tokens = len(enc.encode(user_prompt))
                total_input_tokens = system_tokens + user_tokens

                # Estimate output tokens (rough heuristic based on prompt structure)
                estimated_output_tokens = min(4000, total_input_tokens // 2)

                # Calculate costs
                input_cost = (total_input_tokens / 1_000_000) * pricing["input"]
                output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]
                total_cost = input_cost + output_cost

                console.print("\n[bold yellow]═══ Cost Estimation ═══[/bold yellow]\n")
                console.print(f"Model: [bold magenta]{pricing['name']}[/bold magenta]")
                console.print(f"System prompt tokens: [cyan]{system_tokens:,}[/cyan]")
                console.print(f"User prompt tokens:   [cyan]{user_tokens:,}[/cyan]")
                console.print(f"Total input tokens:   [bold cyan]{total_input_tokens:,}[/bold cyan]")
                console.print(f"Estimated output:     [dim cyan]~{estimated_output_tokens:,}[/dim cyan]")
                console.print(f"\n[bold]Estimated cost ({pricing['name']}):[/bold]")
                console.print(f"  Input:  [green]${input_cost:.4f}[/green] (${pricing['input']:.2f}/1M tokens)")
                console.print(f"  Output: [green]${output_cost:.4f}[/green] (${pricing['output']:.2f}/1M tokens, estimated)")
                console.print(f"  Total:  [bold green]${total_cost:.4f}[/bold green]\n")
                console.print("[dim]Note: Pricing as of January 2025. Check provider for current rates.[/dim]")

            except Exception as e:
                console.print(f"[yellow]Warning: Could not estimate cost: {e}[/yellow]")

    except TemplateError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR.value)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.exception("Preview failed")
        sys.exit(ExitCode.GENERAL_ERROR.value)


# ============================================================================
# Template Export/Import
# ============================================================================


@main.command(name="export", help="Export template to YAML file")
@click.argument("template_name")
@click.option("--output", "-o", help="Output file path (default: stdout)")
def export_template(template_name: str, output: Optional[str]):
    """Export a template to YAML format."""
    try:
        manager = TemplateManager()
        yaml_content = manager.export(template_name)

        if output:
            output_path = Path(output)
            output_path.write_text(yaml_content)
            console.print(f"[green]Template exported to: {output}[/green]")
        else:
            console.print(yaml_content)

    except TemplateError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR.value)


@main.command(name="import", help="Import template from YAML file or URL")
@click.argument("source")
def import_template(source: str):
    """Import a template from YAML file or URL.

    Examples:
        podx templates import my-template.yaml
        podx templates import https://example.com/templates/interview.yaml
    """
    try:
        manager = TemplateManager()

        # Check if source is a URL
        if source.startswith(("http://", "https://")):
            import urllib.request

            console.print(f"[dim]Fetching template from {source}...[/dim]")
            with urllib.request.urlopen(source) as response:
                yaml_content = response.read().decode("utf-8")
        else:
            # Load from file
            source_path = Path(source)
            if not source_path.exists():
                console.print(f"[red]Error: File not found: {source}[/red]")
                sys.exit(ExitCode.GENERAL_ERROR.value)

            yaml_content = source_path.read_text()

        template = manager.import_template(yaml_content)
        console.print(f"[green]Template imported: {template.name}[/green]")
        console.print(f"[dim]Saved to: ~/.podx/templates/{template.name}.yaml[/dim]")

    except TemplateError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR.value)
    except Exception as e:
        console.print(f"[red]Failed to import template: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR.value)


@main.command(name="delete", help="Delete a user template")
@click.argument("template_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_template(template_name: str, yes: bool):
    """Delete a user template (cannot delete built-in templates)."""
    try:
        manager = TemplateManager()

        if not yes:
            if not click.confirm(f"Delete template '{template_name}'?"):
                console.print("[dim]Cancelled[/dim]")
                return

        if manager.delete(template_name):
            console.print(f"[green]Template deleted: {template_name}[/green]")
        else:
            console.print(f"[yellow]Template not found: {template_name}[/yellow]")

    except TemplateError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR.value)


if __name__ == "__main__":
    main()
