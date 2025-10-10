#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Optional

import click

from .cli_shared import read_stdin_json
from .logging import get_logger
from .deepcast import parse_deepcast_metadata
from .ui import (
    make_console,
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    TABLE_SHOW_STYLE,
    TABLE_DATE_STYLE,
    TABLE_TITLE_COL_STYLE,
)

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
        console = make_console()
        deepcast_files = list(Path(scan_dir).rglob("deepcast-*.json"))
        if not deepcast_files:
            console.print(f"[red]No deepcast files found in {scan_dir}[/red]")
            raise SystemExit(1)

        # Build rich metadata rows like podx-deepcast --interactive
        rows = []
        for p in deepcast_files:
            try:
                meta = parse_deepcast_metadata(p)
            except Exception:
                meta = {"asr_model": "unknown", "ai_model": "unknown", "deepcast_type": "unknown"}
            # Episode-level metadata
            episode_dir = p.parent
            show = "Unknown"
            date = "Unknown"
            title = "Unknown"
            try:
                em = json.loads((episode_dir / "episode-meta.json").read_text(encoding="utf-8"))
                show = em.get("show", show)
                date_val = em.get("episode_published", "")
                if date_val:
                    try:
                        from dateutil import parser as dtparse
                        parsed = dtparse.parse(date_val)
                        date = parsed.strftime("%Y-%m-%d")
                    except Exception:
                        date = date_val[:10] if len(date_val) >= 10 else date_val
                title = em.get("episode_title", title)
            except Exception:
                pass
            rows.append({
                "path": p,
                "asr": meta.get("asr_model", "unknown"),
                "ai": meta.get("ai_model", "unknown"),
                "dtype": meta.get("deepcast_type", "unknown"),
                "show": show,
                "date": date,
                "title": title,
            })

        # Display table (full width, compact fixed columns; only Title flexes)
        # Compute a title width that ensures all columns fit the terminal
        term_width = console.size.width
        fixed_widths = {
            "num": 4,  # includes a little padding
            "asr": 16,
            "type": 26,
            "show": 20,
            "date": 12,
        }
        borders_allowance = 16  # table borders/separators/padding
        title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)

        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            title="🤖 Deepcast Analyses",
            expand=False,
            border_style=TABLE_BORDER_STYLE,
        )
        table.add_column("#", style=TABLE_NUM_STYLE, width=fixed_widths["num"], justify="right", no_wrap=True)
        table.add_column("ASR", style="yellow", width=fixed_widths["asr"], no_wrap=True, overflow="ellipsis")
        table.add_column("Type", style="white", width=fixed_widths["type"], no_wrap=True, overflow="ellipsis")
        table.add_column("Show", style=TABLE_SHOW_STYLE, width=fixed_widths["show"], no_wrap=True, overflow="ellipsis")
        table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed_widths["date"], no_wrap=True)
        table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_width, no_wrap=True, overflow="ellipsis")
        for idx, r in enumerate(rows, start=1):
            table.add_row(str(idx), r["asr"], r["dtype"], r["show"], r["date"], r["title"])
        console.print(table)
        console.print("\n[dim]Enter two selections: first then second. Q to cancel.[/dim]")
        choice1 = input(f"👉 First (1-{len(rows)}): ").strip().upper()
        if choice1 in ["Q", "QUIT", "EXIT"]:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        choice2 = input(f"👉 Second (1-{len(rows)}): ").strip().upper()
        if choice2 in ["Q", "QUIT", "EXIT"]:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        try:
            i1 = int(choice1); i2 = int(choice2)
            pa = rows[i1 - 1]["path"]; pb = rows[i2 - 1]["path"]
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


