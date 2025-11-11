#!/usr/bin/env python3
"""Shared UI helpers for consistent styling across podx CLIs."""

from __future__ import annotations

import os
import re
from typing import Iterable

from rich.console import Console
from rich.text import Text


# Standard color convention
CMD_STYLE = "bold white"
FLAG_STYLE = "bright_black"
ARG_STYLE = "yellow"
SYMBOL_STYLE = "white"  # pipes, arrows, redirects
COMMENT_STYLE = "khaki1"
HEADING_STYLE = "bold bright_green"
EXAMPLE_HEADING_STYLE = "green"

# Table styles
TABLE_BORDER_STYLE = "grey50"
TABLE_HEADER_STYLE = "bold magenta"  # pink-ish
TABLE_TITLE_STYLE = "grey70"
TABLE_NUM_STYLE = "cyan"
TABLE_SHOW_STYLE = "yellow3"
TABLE_DATE_STYLE = "bright_blue"
TABLE_FLAG_VALUE_STYLE = "magenta"
TABLE_TITLE_COL_STYLE = "white"


def make_console() -> Console:
    """Create a Console that respects NO_COLOR and works well for CLIs."""
    force_terminal = None
    if os.environ.get("NO_COLOR"):
        force_terminal = False
    return Console(force_terminal=force_terminal, highlight=False)


_QUOTE_RE = re.compile(r"('([^']*)'|\"([^\"]*)\")")


def format_example_line(line: str) -> Text:
    """Format an example line according to the standard color convention.

    - Comments starting with '# ' are tan
    - Commands (tokens starting with 'podx' or 'podx-') are bold white
    - Flags starting with '--' are light gray
    - Quoted flag args are yellow
    - Pipes/redirects/arrows are white
    """
    text = Text()

    # Comment line
    if line.strip().startswith("#"):
        text.append(line, style=COMMENT_STYLE)
        return text

    tokens: Iterable[str] = re.findall(r"\S+|\s+", line)
    for tok in tokens:
        if tok.isspace():
            text.append(tok)
            continue
        if tok.startswith("#"):
            # Rest of line as comment
            text.append(line[line.index(tok) :], style=COMMENT_STYLE)
            break
        if tok in {"|", ">", "<", "→", "•"}:
            text.append(tok, style=SYMBOL_STYLE)
        elif tok.startswith("--"):
            text.append(tok, style=FLAG_STYLE)
        elif tok.startswith("podx"):
            text.append(tok, style=CMD_STYLE)
        elif _QUOTE_RE.fullmatch(tok):
            text.append(tok, style=ARG_STYLE)
        else:
            text.append(tok)
    return text
