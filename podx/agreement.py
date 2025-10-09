#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Optional

import click

from .cli_shared import read_stdin_json
from .logging import get_logger

logger = get_logger(__name__)

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False


@click.command()
@click.option("--a", "input_a", type=click.Path(exists=True, path_type=Path), help="First deepcast JSON/MD (JSON preferred)")
@click.option("--b", "input_b", type=click.Path(exists=True, path_type=Path), help="Second deepcast JSON/MD (JSON preferred)")
@click.option("--model", default="gpt-4.1", help="OpenAI model for comparison")
@click.option("--interactive", is_flag=True, help="Interactive browser to select two analyses to compare")
@click.option("--scan-dir", type=click.Path(exists=True, path_type=Path), default=".", help="Directory to scan for deepcast files")
def main(input_a: Optional[Path], input_b: Optional[Path], model: str, interactive: bool, scan_dir: Path):
    """
    Compare two deepcast analyses and output a structured agreement report.
    If JSON inputs are provided, extracts markdown internally.
    """
    def load_content(p: Path) -> str:
        text = p.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
            # Prefer markdown field in unified JSON
            return data.get("markdown") or text
        except Exception:
            return text

    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit("Interactive mode requires rich library. Install with: pip install rich")
        console = Console()
        deepcasts = list(Path(scan_dir).rglob("deepcast-*.json"))
        if not deepcasts:
            console.print(f"[red]No deepcast files found in {scan_dir}[/red]")
            raise SystemExit(1)

        table = Table(show_header=True, header_style="bold magenta", title="🤖 Deepcast Analyses")
        table.add_column("#", style="cyan", width=3, justify="right")
        table.add_column("File", style="white")
        for idx, p in enumerate(deepcasts, start=1):
            table.add_row(str(idx), p.name)
        console.print(table)
        choice1 = input(f"\n👉 Select first analysis (1-{len(deepcasts)}) or Q to cancel: ").strip().upper()
        if choice1 in ["Q", "QUIT", "EXIT"]:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        choice2 = input(f"👉 Select second analysis (1-{len(deepcasts)}) or Q to cancel: ").strip().upper()
        if choice2 in ["Q", "QUIT", "EXIT"]:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        try:
            i1 = int(choice1); i2 = int(choice2)
            pa = deepcasts[i1 - 1]; pb = deepcasts[i2 - 1]
        except Exception:
            console.print("[red]Invalid selection[/red]")
            raise SystemExit(1)
        input_a = pa; input_b = pb

    if input_a and input_b:
        a_text = load_content(input_a)
        b_text = load_content(input_b)
    else:
        # Fallback: expect a JSON object with fields 'a' and 'b' on stdin
        data = read_stdin_json()
        if not data or not isinstance(data, dict) or not data.get("a") or not data.get("b"):
            raise SystemExit("Provide --a and --b files or pipe JSON with fields 'a' and 'b'")
        a_text = data["a"]
        b_text = data["b"]

    try:
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI()
            use_new = True
        except Exception:
            import openai  # type: ignore
            use_new = False

        prompt = (
            "Compare these two podcast analyses of the same episode. "
            "Return JSON with keys: agreement_score (0-100), unique_to_a, unique_to_b, contradictions, summary.\n"
            "---A---\n" + a_text + "\n---B---\n" + b_text
        )

        if use_new:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
        else:
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                functions=[],
            )
            content = resp.choices[0].message.get("content") or "{}"

        print(content)
    except Exception as e:
        raise SystemExit(f"Agreement check failed: {e}")


if __name__ == "__main__":
    main()


