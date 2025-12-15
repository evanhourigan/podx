"""Enhanced error handling and user-friendly error messages for CLI commands.

Provides helpful error messages with:
- Clear problem statements
- Actionable suggestions
- File suggestions when files are missing
- Common fixes and documentation links
"""

import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.panel import Panel

from podx.domain.exit_codes import ExitCode

console = Console()


def format_error_message(
    title: str,
    message: str,
    suggestions: Optional[List[str]] = None,
    similar_files: Optional[List[Path]] = None,
    docs_link: Optional[str] = None,
) -> str:
    """Format a comprehensive error message.

    Args:
        title: Short error title (e.g., "File not found")
        message: Detailed error message
        suggestions: List of actionable suggestions
        similar_files: List of similar files found
        docs_link: Optional documentation link

    Returns:
        Formatted error message
    """
    lines = [
        f"[red]✗ Error:[/red] {title}",
        "",
        message,
    ]

    if suggestions:
        lines.append("")
        lines.append("[bold]Suggestions:[/bold]")
        for suggestion in suggestions:
            lines.append(f"  • {suggestion}")

    if similar_files:
        lines.append("")
        lines.append("[bold]Did you mean one of these?[/bold]")
        for file_path in similar_files[:5]:  # Limit to 5 suggestions
            lines.append(f"  ✓ {file_path}")

    if docs_link:
        lines.append("")
        lines.append(f"[dim]📚 Documentation: {docs_link}[/dim]")

    return "\n".join(lines)


def find_similar_files(target_path: Path, pattern: str = "*", max_results: int = 5) -> List[Path]:
    """Find files similar to the target path.

    Args:
        target_path: The file that wasn't found
        pattern: Glob pattern to search
        max_results: Maximum number of results

    Returns:
        List of similar file paths
    """
    similar_files = []

    # Search in the target directory
    search_dir = target_path.parent if target_path.parent.exists() else Path.cwd()
    target_name = target_path.name.lower()

    # Try exact match first
    for file in search_dir.glob(pattern):
        if file.is_file():
            file_name = file.name.lower()
            # Fuzzy match based on common substrings
            if (
                target_name in file_name
                or file_name in target_name
                or target_path.suffix in file.suffix
            ):
                similar_files.append(file)
                if len(similar_files) >= max_results:
                    break

    return similar_files


def handle_file_not_found(
    file_path: Path,
    description: str = "File",
    supported_formats: Optional[List[str]] = None,
) -> None:
    """Handle file not found errors with helpful suggestions.

    Args:
        file_path: The file that wasn't found
        description: Description of the file type
        supported_formats: List of supported file formats
    """
    # Find similar files
    similar_files = find_similar_files(file_path)

    suggestions = [
        f"Check the file path is correct: {file_path}",
        f"Verify the file exists: ls {file_path}",
    ]

    if supported_formats:
        formats_str = ", ".join(supported_formats)
        suggestions.append(f"Supported formats: {formats_str}")

    message = format_error_message(
        title=f"{description} not found",
        message=f"File: [cyan]{file_path}[/cyan]",
        suggestions=suggestions,
        similar_files=similar_files,
    )

    console.print(message)
    sys.exit(ExitCode.USER_ERROR)


def handle_missing_api_key(service: str, env_var: str, config_file: str = "~/.podx/.env") -> None:
    """Handle missing API key errors with setup instructions.

    Args:
        service: Service name (e.g., "OpenAI", "Anthropic")
        env_var: Environment variable name
        config_file: Config file path
    """
    suggestions = []

    # Service-specific instructions
    if service.lower() == "openai":
        suggestions.extend(
            [
                "1. Get an API key: https://platform.openai.com/api-keys",
                f"2. Set the environment variable: export {env_var}=sk-...",
                "3. Or use podx-config: podx-config set-key openai",
                f"4. Or add to {config_file}",
            ]
        )
    elif service.lower() == "anthropic":
        suggestions.extend(
            [
                "1. Get an API key: https://console.anthropic.com/settings/keys",
                f"2. Set the environment variable: export {env_var}=sk-ant-...",
                "3. Or use podx-config: podx-config set-key anthropic",
                f"4. Or add to {config_file}",
            ]
        )
    elif service.lower() == "notion":
        suggestions.extend(
            [
                "1. Create a Notion integration: https://www.notion.so/my-integrations",
                f"2. Set the environment variable: export {env_var}=secret_...",
                "3. Or use podx-config: podx-config set-key notion",
                f"4. Or add to {config_file}",
            ]
        )
    else:
        suggestions.extend(
            [
                f"1. Get an API key from {service}",
                f"2. Set the environment variable: export {env_var}=YOUR_KEY",
                f"3. Or add to {config_file}",
            ]
        )

    message = format_error_message(
        title=f"{service} API key not found",
        message=f"This command requires a {service} API key.\n\n"
        f"Environment variable: [cyan]{env_var}[/cyan]",
        suggestions=suggestions,
    )

    console.print(message)
    sys.exit(ExitCode.USER_ERROR)


def handle_invalid_model(
    model: str, available_models: List[str], model_type: str = "model"
) -> None:
    """Handle invalid model name errors with suggestions.

    Args:
        model: The invalid model name
        available_models: List of available models
        model_type: Type of model (e.g., "ASR model", "LLM model")
    """
    # Find similar model names
    similar = []
    model_lower = model.lower()
    for available in available_models:
        if model_lower in available.lower() or available.lower() in model_lower:
            similar.append(available)

    suggestions = [
        f"Use one of the available models: {', '.join(available_models[:5])}",
        "Run 'podx-models list' to see all available models",
    ]

    message = format_error_message(
        title=f"Invalid {model_type}",
        message=f"Model '[cyan]{model}[/cyan]' is not recognized.",
        suggestions=suggestions,
        similar_files=([Path(m) for m in similar] if similar else None),  # Reuse file display
        docs_link="https://docs.podx.ai/models",
    )

    console.print(message)
    sys.exit(ExitCode.USER_ERROR)


def handle_processing_error(
    operation: str,
    error: Exception,
    retry_command: Optional[str] = None,
    debug_info: Optional[str] = None,
) -> None:
    """Handle processing errors with debugging help.

    Args:
        operation: Operation that failed
        error: The exception that occurred
        retry_command: Command to retry
        debug_info: Additional debug information
    """
    suggestions = []

    if retry_command:
        suggestions.append(f"Retry: {retry_command}")

    suggestions.extend(
        [
            "Check the logs for more details",
            "Try with a different model or settings",
            "Report this issue: https://github.com/anthropics/podx/issues",
        ]
    )

    error_details = f"[dim]{str(error)}[/dim]"
    if debug_info:
        error_details += f"\n\n[dim]Debug info:[/dim]\n{debug_info}"

    message = format_error_message(
        title=f"{operation} failed",
        message=error_details,
        suggestions=suggestions,
    )

    console.print(message)
    sys.exit(ExitCode.PROCESSING_ERROR)


def handle_validation_error(
    field: str, value: str, expected: str, examples: Optional[List[str]] = None
) -> None:
    """Handle validation errors with format examples.

    Args:
        field: Field that failed validation
        value: Invalid value
        expected: Expected format
        examples: Example valid values
    """
    suggestions = [f"Expected format: {expected}"]

    if examples:
        suggestions.append("Examples:")
        for example in examples:
            suggestions.append(f"  - {example}")

    message = format_error_message(
        title=f"Invalid {field}",
        message=f"Value '[cyan]{value}[/cyan]' is not valid.",
        suggestions=suggestions,
    )

    console.print(message)
    sys.exit(ExitCode.USER_ERROR)


def confirm_action(message: str, default: bool = False) -> bool:
    """Ask user to confirm an action.

    Args:
        message: Confirmation message
        default: Default value if user presses enter

    Returns:
        True if user confirms, False otherwise
    """
    return click.confirm(message, default=default)


def show_warning(message: str, details: Optional[str] = None) -> None:
    """Show a warning message to the user.

    Args:
        message: Warning message
        details: Optional detailed information
    """
    lines = [f"[yellow]⚠ Warning:[/yellow] {message}"]
    if details:
        lines.append("")
        lines.append(details)

    console.print("\n".join(lines))


def show_success(message: str, details: Optional[str] = None) -> None:
    """Show a success message to the user.

    Args:
        message: Success message
        details: Optional detailed information
    """
    lines = [f"[green]✓[/green] {message}"]
    if details:
        lines.append(details)

    console.print("\n".join(lines))


def show_info(message: str, title: Optional[str] = None) -> None:
    """Show an informational message in a panel.

    Args:
        message: Info message
        title: Optional panel title
    """
    if title:
        console.print(Panel(message, title=title, border_style="blue"))
    else:
        console.print(f"[blue]ℹ[/blue] {message}")
