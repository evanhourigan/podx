#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Optional

import click

from .cli_shared import read_stdin_json
from .logging import get_logger

logger = get_logger(__name__)


@click.command()
@click.option("--a", "input_a", type=click.Path(exists=True, path_type=Path), help="First deepcast JSON/MD (JSON preferred)")
@click.option("--b", "input_b", type=click.Path(exists=True, path_type=Path), help="Second deepcast JSON/MD (JSON preferred)")
@click.option("--model", default="gpt-4.1", help="OpenAI model for comparison")
def main(input_a: Optional[Path], input_b: Optional[Path], model: str):
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


