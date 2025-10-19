#!/usr/bin/env python3
"""podx-consensus: Merge precision and recall deepcasts into a single unified output.

Features:
- Accepts two deepcast unified JSON files (precision and recall) and optional agreement JSON
- Produces a consensus JSON with merged sections and provenance flags
- Adds consensus_metadata (timestamp, models, sources)
- Interactive mode to select eligible episodes (those with both precision & recall and optional agreement)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .ui.deepcast_browser import parse_deepcast_metadata
from .cli_shared import read_stdin_json
from .ui import (
    make_console,
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    TABLE_SHOW_STYLE,
    TABLE_DATE_STYLE,
    TABLE_TITLE_COL_STYLE,
)

try:
    from rich.table import Table
    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False


def _read_json(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


def _dedup_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        key = it.strip()
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _merge_lists(a: List[str] | None, b: List[str] | None) -> List[str]:
    return _dedup_preserve_order((a or []) + (b or []))


def build_consensus(
    precision: Dict[str, Any],
    recall: Dict[str, Any],
    agreement: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Pull common sections from unified deepcast JSONs
    p = precision
    r = recall

    # Confidence heuristic: 1.0 if appears in both, else 0.7 base; scale by agreement if available
    agr_score = None
    if agreement and isinstance(agreement, dict):
        try:
            agr_score = float(agreement.get("agreement_score")) / 100.0
        except Exception:
            agr_score = None

    def score_item(text: str, in_both: bool) -> float:
        base = 1.0 if in_both else 0.7
        if agr_score is not None:
            return round(min(1.0, max(0.0, base * (0.8 + 0.4 * agr_score))), 2)
        return base

    def merge_with_provenance(
        a_list: List[str] | None, b_list: List[str] | None
    ) -> List[Dict[str, Any]]:
        a_set = set((a_list or []))
        b_set = set((b_list or []))
        merged = _merge_lists(list(a_set), list(b_set))
        out: List[Dict[str, Any]] = []
        for item in merged:
            in_a = item in a_set
            in_b = item in b_set
            out.append(
                {
                    "text": item,
                    "provenance": [s for s, ok in [("precision", in_a), ("recall", in_b)] if ok],
                    "confidence": score_item(item, in_a and in_b),
                }
            )
        return out

    # Merge sections
    consensus: Dict[str, Any] = {
        "summary": {
            "precision": p.get("summary"),
            "recall": r.get("summary"),
        },
        "key_points": merge_with_provenance(p.get("key_points"), r.get("key_points")),
        "gold_nuggets": merge_with_provenance(p.get("gold_nuggets"), r.get("gold_nuggets")),
        "actions": merge_with_provenance(p.get("actions"), r.get("actions")),
        "outline": merge_with_provenance(
            [json.dumps(x, ensure_ascii=False) for x in (p.get("outline") or [])],
            [json.dumps(x, ensure_ascii=False) for x in (r.get("outline") or [])],
        ),
        # Keep quotes separate for now (volume is high)
        "quotes": {
            "precision": p.get("quotes", []),
            "recall": r.get("quotes", []),
        },
    }

    return consensus


def find_episode_rows(scan_dir: Path) -> List[Dict[str, Any]]:
    """Find episodes that have both precision and recall deepcasts (and optional agreement)."""
    rows: List[Dict[str, Any]] = []
    for json_path in scan_dir.rglob("deepcast-*-*.json"):
        name = json_path.name
        # Look for our dual naming: deepcast-{asr}-{ai}-{suffix}.json where suffix in {precision,recall}
        if not (name.endswith("-precision.json") or name.endswith("-recall.json")):
            continue
        meta = parse_deepcast_metadata(json_path)
        episode_dir = json_path.parent
        # derive counterpart
        other = name.replace("-precision.json", "-recall.json") if name.endswith("-precision.json") else name.replace("-recall.json", "-precision.json")
        other_path = episode_dir / other
        if not other_path.exists():
            continue
        # agreement optional
        agr = None
        for p in episode_dir.glob("agreement-*.json"):
            agr = p
            break

        # episode meta
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

        rows.append(
            {
                "dir": episode_dir,
                "asr": meta.get("asr_model", "unknown"),
                "ai": meta.get("ai_model", "unknown"),
                "precision": json_path if name.endswith("-precision.json") else other_path,
                "recall": other_path if name.endswith("-precision.json") else json_path,
                "agreement": agr,
                "show": show,
                "date": date,
                "title": title,
            }
        )

    # Deduplicate by directory/asr/ai
    uniq = {}
    for r in rows:
        key = (str(r["dir"]), r["asr"], r["ai"])
        if key not in uniq:
            uniq[key] = r
    return list(uniq.values())


@click.command()
@click.option("--precision", "-p", type=click.Path(exists=True, path_type=Path), help="Precision deepcast JSON (from dual mode)")
@click.option("--recall", "-r", type=click.Path(exists=True, path_type=Path), help="Recall deepcast JSON (from dual mode)")
@click.option("--agreement", "-a", type=click.Path(exists=True, path_type=Path), help="Optional agreement JSON to inform confidence scores")
@click.option("--input", "-i", "inp", type=click.Path(exists=True, path_type=Path), help="Read inputs from a JSON file or stdin with keys: precision, recall, agreement (objects or file paths)")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output consensus JSON file")
@click.option("--interactive", is_flag=True, help="Interactive browser to select eligible episodes")
@click.option("--scan-dir", type=click.Path(exists=True, path_type=Path), default=".", help="Directory to scan for deepcasts")
def main(precision: Optional[Path], recall: Optional[Path], agreement: Optional[Path], inp: Optional[Path], output: Optional[Path], interactive: bool, scan_dir: Path):
    """Merge precision and recall deepcasts into a unified consensus JSON with provenance.

    Composable usage: pipe a JSON object with fields {"precision": <obj|path>, "recall": <obj|path>, "agreement": <obj|path?>}.
    """
    if interactive:
        if not RICH_AVAILABLE:
            raise SystemExit("Interactive mode requires rich. pip install rich")
        console = make_console()
        rows = find_episode_rows(Path(scan_dir))
        if not rows:
            console.print(f"[red]No precision/recall deepcasts found in {scan_dir}[/red]")
            raise SystemExit(1)

        # Compute dynamic title width
        term_width = console.size.width
        fixed = {"num": 4, "asr": 16, "ai": 14, "show": 20, "date": 12}
        borders = 16
        title_w = max(30, term_width - sum(fixed.values()) - borders)

        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            title="🧩 Consensus candidates",
            expand=False,
            border_style=TABLE_BORDER_STYLE,
        )
        table.add_column("#", style=TABLE_NUM_STYLE, width=fixed["num"], justify="right", no_wrap=True)
        table.add_column("ASR", style="yellow", width=fixed["asr"], no_wrap=True, overflow="ellipsis")
        table.add_column("AI", style="green", width=fixed["ai"], no_wrap=True, overflow="ellipsis")
        table.add_column("Show", style=TABLE_SHOW_STYLE, width=fixed["show"], no_wrap=True, overflow="ellipsis")
        table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed["date"], no_wrap=True)
        table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_w, no_wrap=True, overflow="ellipsis")

        for idx, r in enumerate(rows, start=1):
            table.add_row(str(idx), r["asr"], r["ai"], r["show"], r["date"], r["title"])
        console.print(table)
        console.print("\n[dim]Select a row to build consensus, Q to cancel.[/dim]")
        try:
            choice = input(f"👉 1-{len(rows)}: ")
        except EOFError:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        choice = (choice or "").strip().upper()
        if choice in ["Q", "QUIT", "EXIT"]:
            console.print("[dim]Cancelled[/dim]")
            raise SystemExit(0)
        try:
            sel = int(choice)
            r = rows[sel - 1]
        except Exception:
            raise SystemExit("Invalid selection")
        precision = r["precision"]
        recall = r["recall"]
        agreement = r.get("agreement")
        # Default output path in episode dir
        output = r["dir"] / f"consensus-{r['asr'].replace('.', '_')}-{r['ai'].replace('.', '_')}.json"

    if not precision or not recall:
        # Try input file or stdin JSON
        data: Optional[Dict[str, Any]] = None
        if inp:
            data = json.loads(Path(inp).read_text(encoding="utf-8"))
        else:
            try:
                data = read_stdin_json()
            except SystemExit:
                data = None
        if not data:
            raise SystemExit("Provide --precision and --recall files, or pipe JSON with keys precision/recall (agreement optional)")

        def coerce(v):
            if isinstance(v, str) and v.strip().endswith(".json") and Path(v).exists():
                return _read_json(Path(v))
            return v

        p = coerce(data.get("precision"))
        r = coerce(data.get("recall"))
        agr = coerce(data.get("agreement")) if data.get("agreement") is not None else None
        if not isinstance(p, dict) or not isinstance(r, dict):
            raise SystemExit("stdin/input must contain JSON objects for precision and recall (or valid file paths)")
    else:
        p = _read_json(precision)
        r = _read_json(recall)
        agr = _read_json(agreement) if agreement else None

    consensus = build_consensus(p, r, agr)

    # Metadata
    meta_p = p.get("deepcast_metadata", {})
    meta_r = r.get("deepcast_metadata", {})
    dc_type = meta_p.get("deepcast_type") or meta_r.get("deepcast_type")
    out = {
        "sources": {
            "precision": str(precision),
            "recall": str(recall),
            "agreement": str(agreement) if agreement else None,
        },
        "consensus": consensus,
        "consensus_metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "asr_model": meta_p.get("asr_model") or meta_r.get("asr_model"),
            "ai_model": meta_p.get("model") or meta_r.get("model"),
            "deepcast_type": dc_type,
        },
    }

    if output is None:
        # Default to cwd
        output = Path("consensus.json")

    output.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    # In interactive mode, don't dump JSON to stdout; show a friendly message
    try:
        if interactive and RICH_AVAILABLE:
            console = make_console()
            console.print(f"[green]✅ Consensus saved to: {output}[/green]")
        elif not interactive:
            print(json.dumps(out, ensure_ascii=False))
    except Exception:
        # Fallback to plain message
        if interactive:
            print(f"Consensus saved to: {output}")


if __name__ == "__main__":
    main()
