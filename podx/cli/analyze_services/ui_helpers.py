"""UI helper utilities for analyze interactive mode."""

from typing import Any, Dict, List, Optional

from rich.console import Console

from podx.prompt_templates import PodcastType

# Canonical analysis types presented to users
CANONICAL_TYPES: List[PodcastType] = [
    PodcastType.INTERVIEW_GUEST_FOCUSED,  # interview_guest_focused
    PodcastType.PANEL_DISCUSSION,  # multi_guest_panel
    PodcastType.SOLO_COMMENTARY,  # host_analysis_mode
    PodcastType.GENERAL,  # general
]

# Alias analysis types that inject prompt hints but map to canonical templates
ALIAS_TYPES: dict[str, dict[str, Any]] = {
    "host_moderated_panel": {
        "canonical": PodcastType.PANEL_DISCUSSION,
        "prompt": (
            "- Use the HOST's topic introductions as section headings.\n"
            "- Under each section, synthesize panelists' viewpoints (agreements, disagreements, notable quotes).\n"
            "- Attribute quotes with speaker labels; include timestamps when useful."
        ),
    },
    "cohost_commentary": {
        "canonical": PodcastType.PANEL_DISCUSSION,
        "prompt": (
            "- Treat both hosts as equal participants (no host/guest framing).\n"
            "- Synthesize joint reasoning, back-and-forth refinements, and final takeaways.\n"
            "- Emphasize consensus vs. divergences; include brief quotes with timestamps."
        ),
    },
}


def select_analysis_type(row: Dict[str, Any], console: Console) -> Optional[str]:
    """Prompt user to select analysis type."""
    # Get default type from config if available
    episode = row["episode"]
    show_name = episode.get("show", "")
    default_type = None

    # Try to get default from podcast config
    try:
        from podx.podcast_config import get_podcast_config

        config = get_podcast_config(show_name)
        if config and hasattr(config, "default_type"):
            default_type = config.default_type
    except Exception:
        pass

    # If no config default, use "general"
    if not default_type:
        default_type = "general"

    # List canonical analysis types plus friendly aliases
    all_types = [t.value for t in CANONICAL_TYPES] + list(ALIAS_TYPES.keys())

    console.print("\n[bold cyan]Select an analysis type:[/bold cyan]")
    for idx, dtype in enumerate(all_types, start=1):
        marker = " ← Default" if dtype == default_type else ""
        console.print(f"  {idx:2}  {dtype}{marker}")

    choice = input(f"\n👉 Select analysis type (1-{len(all_types)}) or Q to cancel: ").strip()

    if choice.upper() in ["Q", "QUIT", "EXIT"]:
        return None

    if not choice:
        return default_type

    try:
        selection = int(choice)
        if 1 <= selection <= len(all_types):
            return all_types[selection - 1]
        else:
            console.print(f"[red]Invalid choice. Using default: {default_type}[/red]")
            return default_type
    except ValueError:
        console.print(f"[red]Invalid input. Using default: {default_type}[/red]")
        return default_type


# Backwards compatibility alias
select_deepcast_type = select_analysis_type


def select_ai_model(console: Console) -> Optional[str]:
    """Prompt user to select AI model."""
    default_model = "gpt-4.1-mini"

    choice = input(
        f"\n👉 Select AI model (e.g. gpt-4.1, gpt-4o, claude-4-sonnet; default: {default_model}) or Q to cancel: "
    ).strip()

    if choice.upper() in ["Q", "QUIT", "EXIT"]:
        return None

    return choice if choice else default_model
