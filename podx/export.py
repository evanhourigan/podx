import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click

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


def ts(sec: float) -> str:
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_if_changed(path: Path, content: str, replace: bool = False) -> None:
    """Write content to file only if it has changed (when replace=True)."""
    if replace and path.exists():
        existing_content = path.read_text(encoding="utf-8")
        if existing_content == content:
            return  # Content unchanged, skip write

    path.write_text(content, encoding="utf-8")


@click.command(help="Export final analysis or transcript to files. Interactive mode supports show→episode selection and source override.")
@click.option("--interactive", is_flag=True, help="Interactive selection: show → episode → source")
@click.option("--scan-dir", type=click.Path(exists=True, path_type=Path), default=".", help="Directory to scan (recurses)")
@click.option("--source", type=click.Choice(["auto", "consensus", "precision", "recall", "balanced", "single"]), default="auto", help="Export source when not using --interactive")
@click.option("--pdf", is_flag=True, help="Also render exported markdown to PDF (requires pandoc)")
@click.option("--input", "-i", type=click.Path(exists=True, path_type=Path), help="Input JSON (Deepcast unified JSON or Transcript JSON)")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Save output info JSON (summary of files written)")
@click.option("--formats", default="txt,srt", help="[Transcript mode] Output formats (txt,srt,vtt,md)")
@click.option("--output-dir", type=click.Path(file_okay=False, path_type=Path), help="[Transcript mode] Output directory (default: same as input)")
@click.option("--replace", is_flag=True, help="[Transcript mode] Only overwrite if content changed")
def main(
    interactive: bool,
    scan_dir: Path,
    source: str,
    pdf: bool,
    input: Optional[Path],
    output: Optional[Path],
    formats: str,
    output_dir: Optional[Path],
    replace: bool,
):
    """
    Modes:
    - Interactive: scan for exportable deepcasts grouped by show → episodes, then create exported-<ts>.md/pdf.
    - Non-interactive Deepcast: if --input JSON has 'markdown', write exported-<ts>.md/pdf.
    - Legacy Transcript export: if input/STDIN has 'segments', write txt/srt/vtt/md.
    """
    # Read input
    data: Optional[Dict[str, Any]] = None
    if input:
        try:
            data = json.loads(input.read_text(encoding="utf-8"))
        except Exception:
            data = None
    else:
        raw = read_stdin_json()
        if isinstance(raw, dict):
            data = raw

    # Interactive deepcast export flow
    if interactive:
        run_interactive_export(scan_dir, pdf, output)
        return

    if not data:
        raise SystemExit("Provide JSON via --input or stdin, or use --interactive")

    # Deepcast unified JSON mode (preferred)
    if isinstance(data, dict) and ("markdown" in data or "deepcast_metadata" in data):
        exported = export_from_deepcast_json(data, input.parent if input else Path("."), pdf)
        summary = {"exported_md": str(exported[0])}
        if exported[1] is not None:
            summary["exported_pdf"] = str(exported[1])
        if output:
            output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return

    # Parse formats
    format_list = [f.strip().lower() for f in formats.split(",")]
    valid_formats = {"txt", "srt", "vtt", "md"}
    invalid_formats = set(format_list) - valid_formats
    if invalid_formats:
        raise SystemExit(
            f"Invalid formats: {', '.join(invalid_formats)}. Valid: {', '.join(valid_formats)}"
        )

    # Legacy Transcript export path (segments)
    if "segments" not in data:
        raise SystemExit("JSON does not look like a Transcript (missing 'segments') and not a Deepcast JSON. Use --interactive or pass a deepcast JSON.")

    # Determine output directory
    if output_dir:
        out_dir = output_dir
    elif input:
        out_dir = input.parent
    else:
        out_dir = Path(".")

    # Generate base filename from input
    if input:
        base_name = input.stem
    else:
        base_name = "transcript"

    segs = data.get("segments") or []
    output_files = {}

    # Generate files for each requested format
    for fmt in format_list:
        if fmt == "txt":
            content = "\n".join(s["text"].strip() for s in segs) + "\n"
            out_path = out_dir / f"{base_name}.txt"
            write_if_changed(out_path, content, replace)
            output_files["txt"] = str(out_path)

        elif fmt == "srt":
            lines = []
            for i, s in enumerate(segs, 1):
                speaker = s.get("speaker")
                line = (
                    s["text"].strip()
                    if not speaker
                    else f"[{speaker}] {s['text'].strip()}"
                )
                lines += [str(i), f"{ts(s['start'])} --> {ts(s['end'])}", line, ""]
            content = "\n".join(lines)
            out_path = out_dir / f"{base_name}.srt"
            write_if_changed(out_path, content, replace)
            output_files["srt"] = str(out_path)

        elif fmt == "vtt":
            lines = ["WEBVTT", ""]
            for s in segs:
                speaker = s.get("speaker")
                line = (
                    s["text"].strip()
                    if not speaker
                    else f"[{speaker}] {s['text'].strip()}"
                )
                lines += [
                    f"{ts(s['start']).replace(',', '.')} --> {ts(s['end']).replace(',', '.')}",
                    line,
                    "",
                ]
            content = "\n".join(lines)
            out_path = out_dir / f"{base_name}.vtt"
            write_if_changed(out_path, content, replace)
            output_files["vtt"] = str(out_path)

        elif fmt == "md":
            content = (
                "# Transcript\n\n" + "\n\n".join(s["text"].strip() for s in segs) + "\n"
            )
            out_path = out_dir / f"{base_name}.md"
            write_if_changed(out_path, content, replace)
            output_files["md"] = str(out_path)

    # Create output info
    result: Dict[str, Any] = {
        "formats": format_list,
        "output_dir": str(out_dir),
        "files": output_files,
        "segments_count": len(segs),
    }

    # Save output info if requested
    if output:
        output.write_text(json.dumps(result, indent=2))

    # Always print to stdout
    print(json.dumps(result, indent=2))


def _scan_export_rows(scan_dir: Path) -> List[Dict[str, Any]]:
    """Scan for exportable deepcast/consensus JSONs across subdirectories.

    Returns list of rows with: show, date, title, dir, path, ai, asr, type, track
    and groups can be derived by episode directory and show.
    """
    def _format_date_ymd(s: Optional[str]) -> str:
        if not isinstance(s, str) or not s.strip():
            return "Unknown"
        try:
            from dateutil import parser as dtparse  # type: ignore

            return dtparse.parse(s).date().isoformat()
        except Exception:
            pass
        m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            return m.group(1)
        t = s.strip()
        return t[-10:] if len(t) >= 10 else t

    rows: List[Dict[str, Any]] = []

    # Deepcast analyses
    for analysis_file in scan_dir.rglob("deepcast-*.json"):
        try:
            data = json.loads(analysis_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = data.get("deepcast_metadata", {})
        ai = meta.get("model", "unknown")
        asr = meta.get("asr_model", "unknown")
        kind = meta.get("deepcast_type") or "general"
        stem = analysis_file.stem
        track = "S"
        if stem.endswith("-precision"):
            track = "P"
        elif stem.endswith("-recall"):
            track = "R"
        # Episode metadata for show/title/date
        episode_dir = analysis_file.parent
        em = episode_dir / "episode-meta.json"
        show = "Unknown"; title = "Unknown"; date = "Unknown"
        if em.exists():
            try:
                emd = json.loads(em.read_text(encoding="utf-8"))
                show = emd.get("show", show)
                title = emd.get("episode_title", title)
                dval = emd.get("episode_published") or emd.get("date")
                date = _format_date_ymd(dval)
            except Exception:
                pass
        rows.append({
            "path": analysis_file,
            "dir": episode_dir,
            "show": show,
            "date": date,
            "title": title,
            "ai": ai,
            "asr": asr,
            "type": kind,
            "track": track,
        })

    # Consensus analyses
    for analysis_file in scan_dir.rglob("consensus-*.json"):
        try:
            data = json.loads(analysis_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = data.get("consensus_metadata", {})
        ai = meta.get("ai_model", "unknown")
        asr = meta.get("asr_model", "unknown")
        dc_type = meta.get("deepcast_type") or "general"
        episode_dir = analysis_file.parent
        em = episode_dir / "episode-meta.json"
        show = "Unknown"; title = "Unknown"; date = "Unknown"
        if em.exists():
            try:
                emd = json.loads(em.read_text(encoding="utf-8"))
                show = emd.get("show", show)
                title = emd.get("episode_title", title)
                dval = emd.get("episode_published") or emd.get("date")
                date = _format_date_ymd(dval)
            except Exception:
                pass
        rows.append({
            "path": analysis_file,
            "dir": episode_dir,
            "show": show,
            "date": date,
            "title": title,
            "ai": ai,
            "asr": asr,
            "type": dc_type,
            "track": "C",
        })

    # Newest first per date then by mtime
    rows.sort(key=lambda r: (r["date"], r["path"].stat().st_mtime), reverse=True)
    return rows


def _group_shows(rows: List[Dict[str, Any]]) -> List[Tuple[str, int]]:
    """Return [(show, episode_count)] sorted by count desc then show name."""
    per_show: Dict[str, set] = {}
    for r in rows:
        per_show.setdefault(r["show"], set()).add(r["dir"])  # unique episodes by dir
    items = [(show, len(dirs)) for show, dirs in per_show.items()]
    items.sort(key=lambda x: (-x[1], x[0].lower()))
    return items


def _select_show(console, rows: List[Dict[str, Any]]) -> Optional[str]:
    shows = _group_shows(rows)
    if not shows:
        console.print("[red]No exportable deepcasts found.[/red]")
        return None
    table = Table(show_header=True, header_style=TABLE_HEADER_STYLE, title="📻 Choose a show", expand=False, border_style=TABLE_BORDER_STYLE)
    table.add_column("#", style=TABLE_NUM_STYLE, width=4, justify="right", no_wrap=True)
    table.add_column("Show", style=TABLE_SHOW_STYLE, width=36, no_wrap=True, overflow="ellipsis")
    table.add_column("Episodes", style="white", width=10, no_wrap=True)
    for idx, (show, count) in enumerate(shows, start=1):
        table.add_row(str(idx), show, str(count))
    console.print(table)
    console.print("\n[dim]Enter selection number, or Q to cancel.[/dim]")
    ans = input(f"👉 1-{len(shows)}: ").strip().upper()
    if ans in ["Q", "QUIT", "EXIT"]:
        return None
    try:
        num = int(ans)
        if 1 <= num <= len(shows):
            return shows[num - 1][0]
    except Exception:
        pass
    return None


def _select_episode(console, rows: List[Dict[str, Any]], show: str) -> Optional[Path]:
    eps = {}
    for r in rows:
        if r["show"] != show:
            continue
        key = (r["dir"], r["date"], r["title"])  # episode identity
        entry = eps.setdefault(key, {"dir": r["dir"], "date": r["date"], "title": r["title"], "has_consensus": False, "count": 0})
        entry["count"] += 1
        if r.get("track") == "C":
            entry["has_consensus"] = True
    if not eps:
        console.print(f"[red]No episodes found for show: {show}[/red]")
        return None
    ep_list = sorted(eps.values(), key=lambda e: (e["date"], e["has_consensus"], e["count"]), reverse=True)
    term_width = console.size.width
    fixed = {"num": 4, "date": 12, "trk": 6}
    borders = 16
    title_w = max(30, term_width - sum(fixed.values()) - borders)
    table = Table(show_header=True, header_style=TABLE_HEADER_STYLE, title=f"🎙 Episodes • {show}", expand=False, border_style=TABLE_BORDER_STYLE)
    table.add_column("#", style=TABLE_NUM_STYLE, width=fixed["num"], justify="right", no_wrap=True)
    table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed["date"], no_wrap=True)
    table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_w, no_wrap=True, overflow="ellipsis")
    table.add_column("Trk", style="white", width=fixed["trk"], no_wrap=True)
    for idx, e in enumerate(ep_list, start=1):
        trk = "C" if e["has_consensus"] else "-"
        table.add_row(str(idx), e["date"], e["title"], trk)
    console.print(table)
    console.print("\n[dim]Enter selection number, or Q to cancel.[/dim]")
    ans = input(f"👉 1-{len(ep_list)}: ").strip().upper()
    if ans in ["Q", "QUIT", "EXIT"]:
        return None
    try:
        num = int(ans)
        if 1 <= num <= len(ep_list):
            return ep_list[num - 1]["dir"]
    except Exception:
        pass
    return None


def _select_source(console, episode_dir: Path) -> str:
    # Detect availability
    has_c = any(episode_dir.glob("consensus-*.json"))
    has_p = any(p.name.endswith("-precision.json") for p in episode_dir.glob("deepcast-*.json"))
    has_r = any(p.name.endswith("-recall.json") for p in episode_dir.glob("deepcast-*.json"))
    has_s = any((not p.name.endswith("-precision.json") and not p.name.endswith("-recall.json")) for p in episode_dir.glob("deepcast-*.json"))
    options = ["auto"]
    if has_c:
        options.append("consensus")
    if has_r:
        options.append("recall")
    if has_p:
        options.append("precision")
    if has_s:
        options.append("balanced")
        options.append("single")
    table = Table(show_header=True, header_style=TABLE_HEADER_STYLE, title="Source", expand=False, border_style=TABLE_BORDER_STYLE)
    table.add_column("#", style=TABLE_NUM_STYLE, width=4, justify="right", no_wrap=True)
    table.add_column("Choice", style="white")
    for idx, opt in enumerate(options, start=1):
        table.add_row(str(idx), opt)
    console.print(table)
    ans = input(f"👉 1-{len(options)} (Enter=1): ").strip()
    if not ans:
        return options[0]
    try:
        num = int(ans)
        if 1 <= num <= len(options):
            return options[num - 1]
    except Exception:
        pass
    return options[0]


def _pick_json_for_source(episode_dir: Path, source: str) -> Optional[Path]:
    # Helper to choose newest matching file
    def newest(patterns: List[str]) -> Optional[Path]:
        cands: List[Path] = []
        for pat in patterns:
            cands.extend(episode_dir.glob(pat))
        if not cands:
            return None
        return sorted(cands, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    if source == "consensus" or (source == "auto" and newest(["consensus-*.json"])):
        return newest(["consensus-*.json"])
    if source in {"precision", "recall"}:
        return newest([f"deepcast-*-*-{source}.json"])  # our dual naming
    # balanced/single/auto fallback → any non-dual deepcast
    return newest(["deepcast-*.json"])  # includes dual; we'll filter suffix below


def export_from_deepcast_json(dc: Dict[str, Any], out_dir: Path, pdf: bool) -> Tuple[Path, Optional[Path]]:
    md = dc.get("markdown", "")
    meta = dc.get("deepcast_metadata", {})
    lines: List[str] = []
    lines.append("\n\n---\n\n")
    lines.append("### Processing metadata\n")
    track_guess = "consensus" if dc.get("consensus") else None
    lines.append(f"- Track: {track_guess or meta.get('track') or 'single'}")
    lines.append(f"- Deepcast type: {meta.get('deepcast_type')}")
    if meta.get("deepcast_alias"):
        lines.append(f"- Alias: {meta.get('deepcast_alias')}")
    lines.append(f"- ASR model: {meta.get('asr_model')}")
    lines.append(f"- AI model: {meta.get('model')}")
    lines.append(f"- Transcript: {meta.get('transcript_variant')}")
    lines.append(f"- Exported at: {datetime.now(timezone.utc).isoformat()}")
    md_final = (md or "").rstrip() + "\n" + "\n".join(lines) + "\n"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"exported-{ts}.md"
    md_path.write_text(md_final, encoding="utf-8")
    pdf_path: Optional[Path] = None
    if pdf:
        pandoc = shutil.which("pandoc")
        if pandoc:
            pdf_path = out_dir / f"exported-{ts}.pdf"
            try:
                subprocess.run([pandoc, "-f", "markdown", "-t", "pdf", "-o", str(pdf_path)], input=md_final, text=True, check=True)
            except Exception:
                pdf_path = None
        # If pandoc not found, do not fail; proceed with MD only
    return md_path, pdf_path


def run_interactive_export(scan_dir: Path, pdf: bool, output: Optional[Path]) -> None:
    if not RICH_AVAILABLE:
        raise SystemExit("Interactive mode requires rich. pip install rich")
    console = make_console()
    rows = _scan_export_rows(scan_dir)
    if not rows:
        console.print(f"[red]No deepcast files found in {scan_dir}[/red]")
        raise SystemExit(1)
    show = _select_show(console, rows)
    if not show:
        console.print("[dim]Cancelled[/dim]")
        raise SystemExit(0)
    episode_dir = _select_episode(console, rows, show)
    if not episode_dir:
        console.print("[dim]Cancelled[/dim]")
        raise SystemExit(0)
    src = _select_source(console, episode_dir)
    chosen = _pick_json_for_source(episode_dir, src)
    if not chosen or not chosen.exists():
        console.print("[red]No matching analysis file found for that source.[/red]")
        raise SystemExit(1)
    dc = json.loads(chosen.read_text(encoding="utf-8"))
    md_path, pdf_path = export_from_deepcast_json(dc, episode_dir, pdf)
    summary: Dict[str, Any] = {"exported_md": str(md_path)}
    if pdf_path is not None:
        summary["exported_pdf"] = str(pdf_path)
    if output:
        output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    console.print(f"[green]✅ Exported: {md_path}[/green]")
    if pdf_path:
        console.print(f"[green]✅ Exported: {pdf_path}[/green]")


if __name__ == "__main__":
    main()
