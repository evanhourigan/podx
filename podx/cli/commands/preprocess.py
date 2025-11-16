"""Preprocess command shim."""

import sys

import click

from podx.cli.services import run_passthrough


@click.command(
    "preprocess", help="Run preprocessing on transcripts (merge/normalize/restore)"
)
@click.argument("args", nargs=-1)
def preprocess_shim(args: tuple[str, ...]):
    """Run preprocessing on transcripts (merge/normalize/restore)."""
    code = run_passthrough(["podx-preprocess", *args])
    sys.exit(code)
