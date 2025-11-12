"""Command execution utilities for CLI orchestration.

Provides functions for running external CLI tools with JSON I/O handling
and passthrough mode for interactive processes.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from podx.constants import DEFAULT_ENCODING, PREVIEW_MAX_LENGTH
from podx.errors import ValidationError
from podx.logging import get_logger

logger = get_logger(__name__)


def run_command(
    cmd: List[str],
    stdin_payload: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    save_to: Optional[Path] = None,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a CLI tool that prints JSON to stdout; return parsed dict.

    Args:
        cmd: Command and arguments to execute
        stdin_payload: Optional JSON payload to send to stdin
        verbose: Print command output to console
        save_to: Optional file path to save raw output
        label: Optional label for debug logging

    Returns:
        Parsed JSON output as dictionary, or {"stdout": <text>} for non-JSON output

    Raises:
        ValidationError: If command exits with non-zero status
    """
    if label:
        logger.debug("Running command", command=" ".join(cmd), label=label)

    proc = subprocess.run(
        cmd,
        input=json.dumps(stdin_payload) if stdin_payload else None,
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        logger.error(
            "Command failed",
            command=" ".join(cmd),
            return_code=proc.returncode,
            error=err,
        )
        raise ValidationError(f"Command failed: {' '.join(cmd)}\n{err}")

    # stdout should be JSON; optionally mirror to console
    out = proc.stdout

    if verbose:
        # Show a compact preview of the JSON output
        preview = (
            out[:PREVIEW_MAX_LENGTH] + "..." if len(out) > PREVIEW_MAX_LENGTH else out
        )
        click.secho(preview, fg="white")

    try:
        data = json.loads(out)
        logger.debug("Command completed successfully", command=cmd[0])
    except json.JSONDecodeError:
        # Some subcommands (e.g., deepcast/notion) print plain text "Wrote: ..."
        data = {"stdout": out.strip()}
        logger.debug("Command returned non-JSON output", command=cmd[0])

    if save_to:
        save_to.write_text(out, encoding=DEFAULT_ENCODING)
        logger.debug("Output saved", file=str(save_to))

    return data


def run_passthrough(cmd: List[str]) -> int:
    """Run a CLI tool in passthrough mode (inherit stdio). Returns returncode.

    Use this for interactive child processes so the user sees the UI and can interact.

    Args:
        cmd: Command and arguments to execute

    Returns:
        Process exit code
    """
    proc = subprocess.run(cmd)
    return proc.returncode
