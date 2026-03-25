"""CLI commands for analysis template management."""

from pathlib import Path

import click
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from podx.templates.manager import TemplateError, TemplateManager

console = Console()


def _list_templates_output() -> None:
    """Display the templates list."""
    manager = TemplateManager()
    templates = manager.list_templates()

    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=None,
        expand=False,
    )
    table.add_column("Template", style="cyan", no_wrap=True, width=23)
    table.add_column("Description", style="white")

    for name in templates:
        template = manager.load(name)

        # Parse description - get meaningful part
        desc = template.description
        if "Format:" in desc:
            parts = desc.split("Example podcasts:")
            desc = parts[0].replace("Format:", "").strip()

        # Allow wrapping for long descriptions
        table.add_row(template.name, desc)

    console.print("\n[bold]Available Templates[/bold]\n")
    console.print(table)
    console.print("\n[dim]Run 'podx templates show NAME' to view template details.[/dim]")
    console.print("[dim]Run 'podx templates export NAME' to export a template as YAML.[/dim]")
    console.print("[dim]Run 'podx templates import FILE' to import a custom template.[/dim]\n")


@click.group(
    invoke_without_command=True,
    context_settings={"max_content_width": 120},
)
@click.pass_context
def main(ctx: click.Context) -> None:
    """View and manage templates that customize how 'podx analyze' processes transcripts."""
    if ctx.invoked_subcommand is None:
        # No subcommand - list templates directly
        try:
            _list_templates_output()
        except Exception as e:
            raise click.ClickException(f"Error listing templates: {e}")


@main.command(name="list")
def list_templates() -> None:
    """List available analysis templates."""
    try:
        _list_templates_output()
    except Exception as e:
        raise click.ClickException(f"Error listing templates: {e}")


@main.command(name="show")
@click.argument("template_name")
def show_template(template_name: str) -> None:
    """Show detailed information about a template.

    \b
    Arguments:
      TEMPLATE_NAME    Name of template to show
    """
    try:
        manager = TemplateManager()
        template = manager.load(template_name)

        console.print(f"\n[bold cyan]Template:[/bold cyan] {template.name}")
        console.print(f"[bold]Format:[/bold] {template.format or 'N/A'}")
        console.print(f"[bold]Variables:[/bold] {', '.join(template.variables)}")
        console.print(f"\n[bold]Description:[/bold]\n{template.description}\n")

        console.print(
            Panel(
                template.system_prompt,
                title="System Prompt",
                border_style="blue",
            )
        )

        user_preview = template.user_prompt
        if len(user_preview) > 500:
            user_preview = user_preview[:500] + "..."

        console.print(
            Panel(
                user_preview,
                title="User Prompt (preview)",
                border_style="green",
            )
        )

    except TemplateError as e:
        raise click.ClickException(str(e))


@main.command(name="export")
@click.argument("template_name")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
def export_template(template_name: str, output: str | None) -> None:
    """Export a template as YAML.

    \b
    Arguments:
      TEMPLATE_NAME    Name of template to export

    \b
    Examples:
      podx templates export interview-1on1
      podx templates export interview-1on1 -o my-template.yaml
    """
    try:
        manager = TemplateManager()
        yaml_content = manager.export(template_name)

        if output:
            Path(output).write_text(yaml_content, encoding="utf-8")
            console.print(f"[green]Exported '{template_name}' to {output}[/green]")
        else:
            console.print(yaml_content)

    except TemplateError as e:
        raise click.ClickException(str(e))


@main.command(name="import")
@click.argument("source")
def import_template(source: str) -> None:
    """Import a custom template from a YAML file or URL.

    \b
    Arguments:
      SOURCE    Path to YAML file or URL

    \b
    Examples:
      podx templates import my-template.yaml
      podx templates import https://example.com/templates/custom.yaml
    """
    try:
        if source.startswith("http://") or source.startswith("https://"):
            response = requests.get(source, timeout=30)
            response.raise_for_status()
            yaml_content = response.text
        else:
            path = Path(source)
            if not path.exists():
                raise click.ClickException(f"File not found: {source}")
            yaml_content = path.read_text(encoding="utf-8")

        manager = TemplateManager()
        template = manager.import_template(yaml_content)
        console.print(f"[green]Imported template '{template.name}'[/green]")
        console.print(f"[dim]Saved to ~/.podx/templates/{template.name}.yaml[/dim]")
        console.print(f"[dim]Use with: podx analyze --template {template.name}[/dim]")

    except TemplateError as e:
        raise click.ClickException(str(e))
    except requests.RequestException as e:
        raise click.ClickException(f"Failed to fetch URL: {e}")


@main.command(name="delete")
@click.argument("template_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_template(template_name: str, yes: bool) -> None:
    """Delete a user-imported template.

    \b
    Arguments:
      TEMPLATE_NAME    Name of template to delete

    Built-in templates cannot be deleted.
    """
    try:
        manager = TemplateManager()

        if not yes:
            click.confirm(f"Delete template '{template_name}'?", abort=True)

        if manager.delete(template_name):
            console.print(f"[green]Deleted template '{template_name}'[/green]")
        else:
            raise click.ClickException(f"Template '{template_name}' not found in user templates")

    except TemplateError as e:
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
