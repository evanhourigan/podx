"""Interactive analysis type selection UI."""

from typing import Optional


def select_analysis_type(
    console,
    default_type: Optional[str] = None,
) -> str:
    """Interactively select analysis type.

    Args:
        console: Rich console instance
        default_type: Default analysis type (if None, uses "general")

    Returns:
        Chosen analysis type name

    Raises:
        SystemExit: If user cancels
    """
    from ..cli.analyze_services import ALIAS_TYPES, CANONICAL_TYPES

    type_prompt_default = default_type or "general"

    # Build selectable list: canonical + aliases
    type_options = [t.value for t in CANONICAL_TYPES] + list(ALIAS_TYPES.keys())

    # Build short descriptions
    desc: dict[str, str] = {
        "interview_guest_focused": "Interview; emphasize guest insights",
        "panel_discussion": "Multi-speaker panel; perspectives & dynamics",
        "solo_commentary": "Single voice; host analysis/thoughts",
        "general": "Generic structure; adapt to content",
        "host_moderated_panel": "Host sets sections; panel discussion per section",
        "cohost_commentary": "Two peers; back-and-forth commentary",
    }

    console.print("\n[bold cyan]Select analysis type:[/bold cyan]")
    for i, tname in enumerate(type_options, start=1):
        marker = " ← default" if tname == type_prompt_default else ""
        d = desc.get(tname, "")
        console.print(f"  {i:2}  {tname}  [dim]{d}[/dim]{marker}")

    t_in = input(
        f"👉 Choose 1-{len(type_options)} (Enter keeps '{type_prompt_default}', Q=cancel): "
    ).strip()

    if t_in.upper() in {"Q", "QUIT", "EXIT"}:
        raise SystemExit(0)

    if t_in:
        try:
            t_idx = int(t_in)
            if 1 <= t_idx <= len(type_options):
                return type_options[t_idx - 1]
        except ValueError:
            pass

    # Return default if no valid input
    return type_prompt_default


# Backwards compatibility alias
select_deepcast_type = select_analysis_type
