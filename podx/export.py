import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import sys
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


def _run_quiet(cmd: List[str]) -> int:
    """Run a command quietly; return exit code."""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc.returncode
    except Exception:
        return 1


def _ensure_pandoc_and_engine() -> Tuple[Optional[str], Optional[str]]:
    """Ensure pandoc is available; try to install via Homebrew if missing.

    Also try to install a PDF engine (tectonic) and return its name if available.
    Returns (pandoc_path, pdf_engine_name_or_none).
    """
    pandoc_path = shutil.which("pandoc")
    engine: Optional[str] = None
    if not pandoc_path and sys.platform == "darwin":
        # Attempt Homebrew install
        _run_quiet(["brew", "install", "pandoc"])  # best-effort
        pandoc_path = shutil.which("pandoc")

    # Prefer tectonic as lightweight LaTeX engine
    if shutil.which("tectonic") is None and sys.platform == "darwin":
        _run_quiet(["brew", "install", "tectonic"])  # best-effort
    if shutil.which("tectonic") is not None:
        engine = "tectonic"

    return pandoc_path, engine


def _ensure_html_pdf_tools() -> List[str]:
    """Return a list of available browser binaries for headless HTML→PDF.

    Attempts to install Chromium on macOS if none found. Order indicates
    preference; the renderer will try each in sequence.
    """
    # Env override first
    env_bin = os.environ.get("PODX_CHROME_BIN") or None
    chrome_candidates = [
        env_bin if env_bin else None,
        # CLI names
        "chromium",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "msedge",
        "brave",
        # Common macOS app paths
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
        "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    found: List[str] = []
    for c in chrome_candidates:
        if not c:
            continue
        p = shutil.which(c) if os.path.sep not in c else (c if Path(c).exists() else None)
        if p:
            found.append(p)
    if not found and sys.platform == "darwin":
        # Try to install Chromium via Homebrew cask
        _run_quiet(["brew", "install", "--cask", "chromium"])  # best-effort
        # Re-check
        for c in chrome_candidates:
            if not c:
                continue
            p = shutil.which(c) if os.path.sep not in c else (c if Path(c).exists() else None)
            if p:
                found.append(p)
    # Deduplicate while preserving order
    uniq: List[str] = []
    seen = set()
    for p in found:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _render_pdf_pretty(md_final: str, out_pdf: Path) -> bool:
    """Render a pretty PDF using HTML pipeline to preserve emoji/styling.

    Returns True on success, False otherwise.
    """
    pandoc = shutil.which("pandoc")
    if not pandoc:
        pandoc, _ = _ensure_pandoc_and_engine()  # try to install pandoc
    if not pandoc:
        return False

    browsers = _ensure_html_pdf_tools()
    if not browsers:
        # No HTML-to-PDF tool available
        return False

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        html = tmpdir / "export.html"
        css = tmpdir / "style.css"
        css.write_text(
            """
            :root { --fg: #222; --muted: #666; }
            html { font-size: 16px; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif; color: var(--fg); line-height: 1.55; padding: 2rem; }
            h1, h2, h3 { font-weight: 800; }
            h1 { font-size: 2.1rem; margin: 0 0 0.8rem; }
            h2 { font-size: 1.6rem; margin: 1.6rem 0 0.6rem; }
            h3 { font-size: 1.25rem; margin: 1.2rem 0 0.4rem; }
            hr { border: none; border-top: 1px solid #ddd; margin: 1.6rem 0; }
            blockquote { color: var(--muted); border-left: 4px solid #ddd; margin: 0.8rem 0; padding: 0.4rem 0.9rem; }
            ul { margin: 0.3rem 0 0.9rem 1.1rem; }
            li { margin: 0.25rem 0; }
            code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
            table { border-collapse: collapse; }
            th, td { border: 1px solid #ddd; padding: 6px 8px; }
            .meta hr { margin-top: 1.2rem; }
            """.strip(),
            encoding="utf-8",
        )

        # Convert markdown to HTML with embedded CSS
        cmd = [
            pandoc,
            "-f",
            "markdown",
            "-t",
            "html5",
            "-s",
            "--css",
            str(css),
    "-o",
            str(html),
        ]
        try:
            subprocess.run(cmd, input=md_final, text=True, check=True)
        except Exception:
            return False

        for chrome in browsers:
            try:
                cmd = [
                    chrome,
                    "--headless",
                    "--disable-gpu",
                    # Suppress header/footer across Chrome variants
                    "--print-to-pdf-no-header",
                    "--no-pdf-header-footer",
                    "--disable-print-header-footer",
                    f"--print-to-pdf={out_pdf}",
                    str(html),
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                continue
    return False


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
    # Interactive deepcast export flow
    if interactive:
        run_interactive_export(scan_dir, pdf, output)
        return

    # Read input (non-interactive modes only)
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
        show = "Unknown"
        title = "Unknown"
        date = "Unknown"
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
        show = "Unknown"
        title = "Unknown"
        date = "Unknown"
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


def _read_precision_header_from_sources(dc: Dict[str, Any], out_dir: Path) -> Optional[str]:
    """Try to read the nice episode header from the precision deepcast markdown."""
    try:
        sources = dc.get("sources") or {}
        pth = sources.get("precision") or sources.get("recall")
        if not pth:
            return None
        p = Path(pth)
        if not p.exists():
            p = out_dir / Path(pth)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        md = (data.get("markdown") or "").strip()
        if not md:
            return None
        # Keep everything before the first H2 section
        idx = md.find("\n## ")
        return md[: idx if idx != -1 else len(md)].rstrip() + "\n\n"
    except Exception:
        return None


def _build_header_from_episode_meta(out_dir: Path) -> Optional[str]:
    try:
        em = out_dir / "episode-meta.json"
        if not em.exists():
            return None
        meta = json.loads(em.read_text(encoding="utf-8"))
        show = meta.get("show") or meta.get("show_name") or "Unknown Show"
        title = meta.get("episode_title") or meta.get("title") or "Unknown Episode"
        date = meta.get("episode_published") or meta.get("release_date") or "Unknown Date"
        return f"# {show}\n## {title}\n**Released:** {date}\n\n---\n\n"
    except Exception:
        return None


def _markdown_from_consensus(dc: Dict[str, Any], out_dir: Path) -> str:
    """Build a readable markdown from a consensus JSON structure."""
    cons = dc.get("consensus", {})
    header = _read_precision_header_from_sources(dc, out_dir) or _build_header_from_episode_meta(out_dir) or ""

    lines: List[str] = []
    # Executive Summary (choose best of precision/recall)
    summary = cons.get("summary", {})
    text_p = (summary.get("precision") or "").strip() if isinstance(summary, dict) else ""
    text_r = (summary.get("recall") or "").strip() if isinstance(summary, dict) else ""
    summary_text = text_p if len(text_p) >= len(text_r) else text_r
    if summary_text:
        lines.append("## 📋 Executive Summary\n\n" + summary_text + "\n")
        lines.append("\n---\n")

    def collect_texts(key: str) -> List[str]:
        items = cons.get(key) or []
        out: List[str] = []
        for it in items:
            if isinstance(it, dict):
                txt = (it.get("text") or "").strip()
            else:
                txt = str(it).strip()
            if txt:
                out.append(txt)
        # Deduplicate preserving order
        seen = set()
        uniq: List[str] = []
        for t in out:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        return uniq

    # Format a bullet: bold lead phrase, keep remainder, keep trailing timecode
    _time_re = re.compile(r"\s*(\[[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{2})?\])\s*$")
    def format_bullet(text: str) -> str:
        t = text.strip()
        # Extract trailing timecode
        time_match = _time_re.search(t)
        timecode = ""
        if time_match:
            timecode = " " + time_match.group(1)
            t = _time_re.sub("", t)
        # Split on colon/em dash/period for lead
        lead, rest = t, ""
        for sep in [": ", " — ", " - ", ". "]:
            if sep in t and len(t.split(sep, 1)[0]) <= 80:
                lead, rest = t.split(sep, 1)
                break
        if rest:
            return f"- **{lead.strip()}**: {rest.strip()}{timecode}"
        return f"- {t}{timecode}"

    def bullet_section(title: str, key: str):
        arr = collect_texts(key)
        if not arr:
            return
        lines.append(f"\n## {title}\n")
        for t in arr:
            lines.append(format_bullet(t))
        lines.append("\n---\n")

    bullet_section("🎯 Key Insights", "key_points")
    bullet_section("💎 Gold Nuggets", "gold_nuggets")

    # Quotes: merge both lists
    quotes = (dc.get("consensus", {}).get("quotes") or {})
    merged_quotes: List[Dict[str, str]] = []
    for bucket in ("precision", "recall"):
        for q in (quotes.get(bucket) or []):
            rec: Dict[str, str] = {"quote": "", "context": "", "time": "", "speaker": ""}
            if isinstance(q, str):
                # Try to parse JSON, else treat as plain quote
                try:
                    obj = json.loads(q)
                except Exception:
                    obj = {"quote": q}
            else:
                obj = q
            if isinstance(obj, dict):
                rec["quote"] = str(obj.get("quote") or obj.get("text") or obj.get("q") or "").strip(' \n"')
                rec["context"] = str(obj.get("context") or obj.get("explanation") or "").strip()
                rec["time"] = str(obj.get("time") or obj.get("ts") or "").strip()
                rec["speaker"] = str(obj.get("speaker") or "").strip()
            else:
                rec["quote"] = str(obj)
            merged_quotes.append(rec)
    if merged_quotes:
        lines.append("\n## 💬 Notable Quotes\n")
        for i, q in enumerate(merged_quotes, 1):
            time_str = f" [{q['time']}]" if q.get("time") else ""
            expl = q.get("context") or ""
            if expl:
                lines.append(f"{i}. \"**{q['quote']}**\"{time_str}\n   — {expl}")
            else:
                lines.append(f"{i}. \"**{q['quote']}**\"{time_str}")
        lines.append("\n---\n")

    bullet_section("⚡ Action Items", "actions")

    # Outline: parse JSON strings back to dicts when possible
    outline_items = cons.get("outline") or []
    formatted_outline: List[str] = []
    for it in outline_items:
        rec = it
        if isinstance(it, str):
            try:
                rec = json.loads(it)
            except Exception:
                rec = {"label": it}
        if isinstance(rec, dict):
            label = rec.get("label") or rec.get("text") or ""
            time = rec.get("time") or rec.get("ts") or ""
            desc = rec.get("description") or rec.get("desc") or ""
            text = label
            if time:
                text += f" [{time}]"
            if desc:
                text += f" — {desc}"
            formatted_outline.append(text.strip())
        else:
            formatted_outline.append(str(rec))
    if formatted_outline:
        lines.append("\n## 🕒 Timestamp Outline\n")
        for t in formatted_outline:
            lines.append(f"- {t}")
        lines.append("\n---\n")

    body = header + "\n".join(lines).strip() + "\n"
    return body


def _safe_meta_line(label: str, value: Optional[str]) -> Optional[str]:
    val = (value or "").strip()
    return f"- {label}: {val}" if val else None


def export_from_deepcast_json(dc: Dict[str, Any], out_dir: Path, pdf: bool, track_hint: Optional[str] = None) -> Tuple[Path, Optional[Path]]:
    # 1) Build body markdown from either unified deepcast JSON or consensus JSON
    if isinstance(dc.get("markdown"), str) and dc.get("markdown").strip():
        body_md = dc.get("markdown", "")
        meta = dc.get("deepcast_metadata", {})
        track_label = (track_hint or meta.get("track") or meta.get("transcript_variant") or "single")
        dc_type = meta.get("deepcast_type")
        asr = meta.get("asr_model")
        ai = meta.get("model")
        transcript_var = meta.get("transcript_variant")
    elif "consensus" in dc:
        body_md = _markdown_from_consensus(dc, out_dir)
        meta = dc.get("consensus_metadata", {})
        track_label = track_hint or "consensus"
        dc_type = meta.get("deepcast_type")
        asr = meta.get("asr_model")
        ai = meta.get("ai_model")
        transcript_var = None
    else:
        # Unknown structure; fallback to dumping JSON
        body_md = "```json\n" + json.dumps(dc, indent=2, ensure_ascii=False) + "\n```\n"
        meta = {}
        track_label = "single"
        dc_type = None
        asr = None
        ai = None
        transcript_var = None

    # 2) Footer metadata
    footer: List[str] = []
    footer.append("\n\n---\n\n")
    footer.append("### Processing metadata\n")
    for line in [
        _safe_meta_line("Track", track_label),
        _safe_meta_line("Deepcast type", dc_type),
        _safe_meta_line("Alias", meta.get("deepcast_alias")),
        _safe_meta_line("ASR model", asr),
        _safe_meta_line("AI model", ai),
        _safe_meta_line("Transcript", transcript_var),
        f"- Exported at: {datetime.now(timezone.utc).isoformat()}",
    ]:
        if line:
            footer.append(line)

    md_final = (body_md or "").rstrip() + "\n" + "\n".join(footer) + "\n"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    label_for_name = (track_label or "").lower()
    name_core = (
        f"exported-{label_for_name}-{ts}" if label_for_name in {"precision", "recall", "consensus"} else f"exported-{ts}"
    )
    md_path = out_dir / f"{name_core}.md"
    md_path.write_text(md_final, encoding="utf-8")
    pdf_path: Optional[Path] = None
    if pdf:
        pdf_path = out_dir / f"{name_core}.pdf"
        # Prefer pretty HTML → PDF path first
        if not _render_pdf_pretty(md_final, pdf_path):
            # Fallback to pandoc+LaTeX
            pandoc, engine = _ensure_pandoc_and_engine()
            if pandoc:
                cmd = [pandoc, "-f", "markdown", "-t", "pdf"]
                if engine:
                    cmd += ["--pdf-engine", engine]
                cmd += ["-o", str(pdf_path)]
                try:
                    subprocess.run(cmd, input=md_final, text=True, check=True)
                except Exception:
                    pdf_path = None
            else:
                pdf_path = None
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
    # Offer PDF prompt in interactive mode if flag not provided
    if not pdf:
        try:
            ans = input("Also render a PDF? [y/N]: ").strip().lower()
            pdf = ans in {"y", "yes"}
        except EOFError:
            pdf = False
    # Determine track hint for naming
    track_hint = None
    if src in {"precision", "recall", "consensus"}:
        track_hint = src
    elif chosen.name.startswith("consensus-"):
        track_hint = "consensus"
    elif chosen.name.endswith("-precision.json"):
        track_hint = "precision"
    elif chosen.name.endswith("-recall.json"):
        track_hint = "recall"
    md_path, pdf_path = export_from_deepcast_json(dc, episode_dir, pdf, track_hint=track_hint)
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
