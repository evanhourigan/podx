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
        table = Table(title="Available Deepcast Templates", show_header=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Format", style="magenta")
        table.add_column("Description", style="white")
        table.add_column("Variables", style="yellow")

        for name in templates:
            template = manager.load(name)
            # Extract format from description if present
            desc = template.description
            if desc.startswith("Format:"):
                parts = desc.split("Example podcasts:")
                desc = parts[0].replace("Format:", "").strip()
                if len(parts) > 1:
                    desc = desc + "\n[dim]" + parts[1].strip()[:60] + "...[/dim]"

            table.add_row(
                template.name,
                template.format or "N/A",
                desc[:80] + "..." if len(desc) > 80 else desc,
                ", ".join(template.variables[:3]) + ("..." if len(template.variables) > 3 else "")
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
                enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding

                system_tokens = len(enc.encode(system_prompt))
                user_tokens = len(enc.encode(user_prompt))
                total_input_tokens = system_tokens + user_tokens

                # Estimate output tokens (rough heuristic based on prompt structure)
                estimated_output_tokens = min(4000, total_input_tokens // 2)

                # Cost estimates (approximate, varies by model)
                # Using GPT-4o rates as baseline: $2.50/1M input, $10/1M output
                input_cost = (total_input_tokens / 1_000_000) * 2.50
                output_cost = (estimated_output_tokens / 1_000_000) * 10.00
                total_cost = input_cost + output_cost

                console.print("\n[bold yellow]═══ Cost Estimation ═══[/bold yellow]\n")
                console.print(f"System prompt tokens: [cyan]{system_tokens:,}[/cyan]")
                console.print(f"User prompt tokens:   [cyan]{user_tokens:,}[/cyan]")
                console.print(f"Total input tokens:   [bold cyan]{total_input_tokens:,}[/bold cyan]")
                console.print(f"Estimated output:     [dim cyan]~{estimated_output_tokens:,}[/dim cyan]")
                console.print("\n[bold]Estimated cost (GPT-4o rates):[/bold]")
                console.print(f"  Input:  [green]${input_cost:.4f}[/green]")
                console.print(f"  Output: [green]${output_cost:.4f}[/green] (estimated)")
                console.print(f"  Total:  [bold green]${total_cost:.4f}[/bold green]\n")
                console.print("[dim]Note: Actual costs vary by model and provider[/dim]")

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
