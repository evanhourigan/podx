"""CLI commands for analysis template management.

Simplified v4.0 - list and show only.
For custom templates, add YAML files to ~/.podx/templates/
"""

import click
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
    console.print("[dim]For custom templates: add YAML files to ~/.podx/templates/[/dim]\n")


@click.group(
    invoke_without_command=True,
    context_settings={"max_content_width": 120},
)
@click.pass_context
def main(ctx: click.Context) -> None:
    """View templates that customize how 'podx analyze' processes transcripts.

    \b
    For custom templates: add YAML files to ~/.podx/templates/
    """
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


if __name__ == "__main__":
    main()
