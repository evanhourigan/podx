"""Interactive prompt utilities for CLI commands.

Provides reusable functions for prompting users with help text and defaults.
"""

import select
import sys
from typing import Callable, List, Optional

from rich.console import Console

console = Console()


def _read_paste_continuation() -> List[str]:
    """Read additional lines from a multiline paste.

    After an input() call, checks if more data is buffered in stdin
    (indicating a multiline paste) and reads all remaining lines.

    Returns:
        List of additional lines (empty for single-line input).
    """
    lines: List[str] = []
    try:
        while select.select([sys.stdin], [], [], 0.05)[0]:
            line = sys.stdin.readline()
            if not line:  # EOF
                break
            lines.append(line.rstrip("\n"))
    except (OSError, ValueError):
        pass  # select not available (non-tty stdin), skip
    return lines


def prompt_with_help(
    help_text: str,
    prompt_label: str,
    default: str,
    validator: Optional[Callable[[str], bool]] = None,
    error_message: str = "Invalid input. Please try again.",
) -> str:
    """Display help text and prompt user for input with a default value.

    Args:
        help_text: Multi-line help text to display above the prompt
        prompt_label: Label for the prompt (e.g., "Model", "Template")
        default: Default value shown and used if user presses Enter
        validator: Optional function to validate input; returns True if valid
        error_message: Message shown when validation fails

    Returns:
        User's input or the default if Enter was pressed
    """
    # Display help text
    console.print()
    console.print(help_text)
    console.print()

    while True:
        try:
            user_input = input(f"{prompt_label} (default: {default}): ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled[/dim]")
            raise SystemExit(0)

        # Empty input means use default
        if not user_input:
            return default

        # Validate if validator provided
        if validator is not None:
            if validator(user_input):
                return user_input
            else:
                console.print(f"[red]{error_message}[/red]")
                continue

        return user_input


def prompt_optional(prompt_label: str, hint: str = "Enter to skip") -> str:
    """Prompt for optional free-text input. Supports multiline paste.

    Args:
        prompt_label: Label for the prompt
        hint: Hint text shown in parentheses

    Returns:
        User's input or empty string if Enter was pressed
    """
    try:
        first_line = input(f"{prompt_label} ({hint}): ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled[/dim]")
        raise SystemExit(0)

    if not first_line:
        return ""

    # Capture remaining lines from multiline paste
    extra_lines = _read_paste_continuation()
    if extra_lines:
        all_text = first_line + "\n" + "\n".join(extra_lines)
        total_lines = 1 + len(extra_lines)
        console.print(f"[dim]  (captured {total_lines} lines)[/dim]")
        return all_text.strip()

    return first_line


def prompt_compact(
    prompt_label: str,
    default: str,
    help_text: str,
    validator: Optional[Callable[[str], bool]] = None,
    error_message: str = "Invalid input. Please try again.",
    allow_empty: bool = False,
) -> str:
    """Prompt with on-demand help via '?'.

    Like prompt_with_help but help is shown only when user types '?'.
    More compact for prompts where most users accept the default.

    Args:
        prompt_label: Label for the prompt
        default: Default value shown and used if user presses Enter
        help_text: Help text displayed when user types '?'
        validator: Optional function to validate input; returns True if valid
        error_message: Message shown when validation fails
        allow_empty: Whether to allow empty input (return "")

    Returns:
        User's input or the default if Enter was pressed
    """
    while True:
        try:
            user_input = input(f"{prompt_label} (default: {default}, ? for help): ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled[/dim]")
            raise SystemExit(0)

        # Show help on '?'
        if user_input == "?":
            console.print()
            console.print(help_text)
            console.print()
            continue

        # Empty input means use default
        if not user_input:
            if allow_empty:
                return ""
            return default

        # Validate if validator provided
        if validator is not None:
            if validator(user_input):
                return user_input
            else:
                console.print(f"[red]{error_message}[/red]")
                continue

        return user_input


def show_confirmation(label: str, value: str) -> None:
    """Display a confirmation line for a pre-specified option.

    Args:
        label: Label for the option (e.g., "Model", "Template")
        value: The value being used
    """
    console.print(f"[cyan]{label}:[/cyan] {value}")


# --- Validators ---


def validate_asr_model(model: str) -> bool:
    """Validate ASR model name against known models."""
    # Known local models
    local_models = {
        "local:large-v3-turbo",
        "local:large-v3",
        "local:large-v2",
        "local:medium",
        "local:base",
        "local:tiny",
        # Also accept without prefix for backwards compatibility
        "large-v3-turbo",
        "large-v3",
        "large-v2",
        "medium",
        "base",
        "tiny",
    }

    # Cloud models
    cloud_models = {"openai:whisper-1"}

    # HuggingFace models
    hf_models = {"hf:distil-large-v3"}

    # RunPod cloud models
    runpod_models = {
        "runpod:large-v3-turbo",
        "runpod:turbo",
        "runpod:large-v3",
        "runpod:large-v2",
        "runpod:medium",
        "runpod:small",
        "runpod:base",
        "runpod:tiny",
    }

    all_models = local_models | cloud_models | hf_models | runpod_models
    return model.lower() in {m.lower() for m in all_models}


def validate_language(language: str) -> bool:
    """Validate language code."""
    if language.lower() == "auto":
        return True

    # ISO 639-1 two-letter codes (common ones)
    valid_codes = {
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "nl",
        "pl",
        "ru",
        "ja",
        "zh",
        "ko",
        "ar",
        "hi",
        "tr",
        "vi",
        "th",
        "id",
        "ms",
        "sv",
        "da",
        "no",
        "fi",
        "cs",
        "sk",
        "hu",
        "ro",
        "bg",
        "uk",
        "he",
        "el",
        "ca",
        "eu",
        "gl",
        "hr",
        "sr",
        "sl",
        "et",
        "lv",
        "lt",
        "mt",
        "cy",
        "ga",
        "is",
        "mk",
        "sq",
        "bs",
        "af",
        "sw",
        "tl",
        "bn",
        "ta",
        "te",
        "mr",
        "gu",
        "kn",
        "ml",
        "pa",
        "ur",
        "fa",
        "ne",
        "si",
        "my",
        "km",
        "lo",
        "ka",
        "am",
        "mn",
        "bo",
        "jw",
        "su",
    }
    return language.lower() in valid_codes


def validate_llm_model(model: str) -> bool:
    """Validate LLM model name against known models."""
    try:
        from podx.models import get_model

        result = get_model(model)
        return result is not None
    except Exception:
        # If catalog not available, accept any provider:model format
        if ":" in model:
            return True
        return False


def validate_template(template: str) -> bool:
    """Validate template name against known templates."""
    try:
        from podx.templates.manager import TemplateManager

        manager = TemplateManager()
        templates = manager.list_templates()
        return template in templates
    except Exception:
        # If templates not available, accept any non-empty string
        return bool(template)


def validate_export_format(fmt: str, export_type: str = "transcript") -> bool:
    """Validate export format(s), comma-separated.

    Args:
        fmt: Format string, can be comma-separated (e.g., "md,srt")
        export_type: Either "transcript" or "analysis"
    """
    if export_type == "transcript":
        valid_formats = {"txt", "md", "srt", "vtt"}
    else:  # analysis
        valid_formats = {"md", "html", "pdf"}

    # Split by comma and validate each format
    formats = [f.strip().lower() for f in fmt.split(",")]
    return all(f in valid_formats for f in formats)


# --- Help text generators ---


def get_asr_models_help() -> str:
    """Get help text for ASR models."""
    return """Models - Local (free, runs on your machine):
  local:large-v3-turbo  Best quality, optimized
  local:large-v3        Best quality
  local:large-v2        Previous best
  local:medium          Good balance of speed/quality
  local:base            Fast, lower accuracy
  local:tiny            Fastest, lowest accuracy

Models - RunPod Cloud (requires 'podx cloud setup'):
  runpod:large-v3-turbo  ~$0.05/hr, fastest cloud option
  runpod:large-v3        ~$0.05/hr, best quality

Models - OpenAI (requires API key):
  openai:whisper-1  $0.006/min, requires OPENAI_API_KEY

Models - HuggingFace (downloads locally, free):
  hf:distil-large-v3  Distilled, faster than large-v3"""


def get_languages_help() -> str:
    """Get help text for languages."""
    return """Languages:
  auto    Auto-detect language
  en      English
  es      Spanish
  fr      French
  de      German
  ja      Japanese
  zh      Chinese
  ...     (ISO 639-1 two-letter codes)"""


def get_llm_models_help() -> str:
    """Get help text for LLM models."""
    return """Models (use 'podx models' for full list):
  openai:gpt-5.2               Latest, highest quality
  openai:gpt-5.1               Previous generation
  openai:gpt-5-mini            Fast and affordable
  openai:gpt-4o                Multimodal capable
  anthropic:claude-opus-4-5    Anthropic highest quality
  anthropic:claude-sonnet-4-5  Anthropic alternative"""


def get_templates_help() -> str:
    """Get help text for templates."""
    return """Templates (use 'podx templates' for full list):
  general             Works for any podcast
  interview-1on1      Host interviewing a single guest
  panel-discussion    Multiple hosts/guests discussing
  solo-commentary     Single host sharing thoughts
  technical-deep-dive In-depth technical discussion"""


def get_export_formats_help(export_type: str = "transcript") -> str:
    """Get help text for export formats.

    Args:
        export_type: Either "transcript" or "analysis"
    """
    if export_type == "transcript":
        return """Formats (comma-separated for multiple):
  txt    Plain text transcript
  md     Markdown with speakers
  srt    SubRip subtitles (for video editing)
  vtt    WebVTT subtitles (for web players)"""
    else:  # analysis
        return """Formats (comma-separated for multiple):
  md     Markdown summary
  html   HTML document
  pdf    PDF document (requires pandoc)"""
