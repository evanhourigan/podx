"""Interactive selection flows for Notion uploads."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _HAS_RICH = True
    _console = Console()
except Exception:
    _HAS_RICH = False
    _console = None  # type: ignore

from podx.yaml_config import NotionDatabase, get_yaml_config_manager

try:
    from notion_client import Client
except ImportError:
    Client = None  # type: ignore


def _detect_shows(root: Path) -> List[str]:
    """Detect shows that already have deepcast analyses (actionable for Notion)."""
    shows: List[str] = []
    try:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            actionable = False
            for p in entry.iterdir():
                if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name):
                    # Check for both new and legacy deepcast formats
                    if list((entry / p.name).glob("deepcast-*.json")):
                        actionable = True
                        break
            if actionable:
                shows.append(entry.name)
    except FileNotFoundError:
        pass
    return sorted(shows, key=lambda s: s.lower())


def _list_episode_dates(root: Path, show: str) -> List[str]:
    """List episode dates for a show that have deepcast analyses, sorted desc."""
    dates: List[str] = []
    show_dir = root / show
    if not show_dir.exists():
        return dates
    for entry in show_dir.iterdir():
        if entry.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", entry.name):
            # Check for both new and legacy deepcast formats
            if list(entry.glob("deepcast-*.json")):
                dates.append(entry.name)
    # Newest first
    return sorted(dates, reverse=True)


def _list_deepcast_models(workdir: Path) -> List[str]:
    """List available deepcast models for an episode workdir based on filenames."""
    models: List[str] = []
    # Check for both new and legacy deepcast formats
    files = list(workdir.glob("deepcast-*.json"))
    for f in files:
        # Try to extract AI model from filename
        # Complex format: deepcast-{asr}-{ai}-{type}.json -> extract {ai}
        # Simple format: deepcast-{ai}.json -> extract {ai}
        # Legacy format: deepcast-brief-{ai}.json -> extract {ai} (backward compatibility)
        stem = f.stem
        if stem.startswith("deepcast-brief-"):
            # Legacy: deepcast-brief-{ai} (backward compatibility)
            suffix = stem[len("deepcast-brief-") :].replace("_", ".")
            models.append(suffix)
        elif stem.startswith("deepcast-"):
            if stem.count("-") == 1:
                # Simple format: deepcast-{ai}
                suffix = stem[len("deepcast-") :].replace("_", ".")
                models.append(suffix)
            elif stem.count("-") >= 3:
                # Complex format: deepcast-{asr}-{ai}-{type}
                parts = stem.split("-")
                if len(parts) >= 3:
                    ai_model = parts[2].replace("_", ".")
                    if ai_model not in models:
                        models.append(ai_model)
    # Deduplicate and return unique models
    return list(dict.fromkeys(models))  # Preserve order while deduplicating


def _prompt_numbered_choice(title: str, items: List[str]) -> Optional[str]:
    """Prompt user to choose one item by number; supports q to quit and /filter.

    Uses Rich tables if available for a nicer UI similar to podx-browse.
    """
    current = list(items)
    filter_note = ""
    while True:
        # Clear screen before re-render to keep UI anchored
        try:
            if _HAS_RICH and _console is not None:
                _console.clear()
            else:
                click.clear()
        except Exception:
            pass

        if _HAS_RICH and _console is not None:
            tbl = Table(show_header=True, header_style="bold cyan", box=None)
            tbl.add_column("#", style="cyan dim", width=4)
            tbl.add_column(title + (f" {filter_note}" if filter_note else ""), style="white")
            for idx, item in enumerate(current, start=1):
                tbl.add_row(str(idx), item)
            _console.print(tbl)
            _console.print(Panel.fit("1-9 select  •  /text filter  •  q quit", style="dim"))
        else:
            click.echo("")
            click.echo(title + (f" {filter_note}" if filter_note else ""))
            for idx, item in enumerate(current, start=1):
                click.echo(f"  {idx}. {item}")
            click.echo("\nHelp: 1-9 select • /text filter • q quit")

        choice = click.prompt("Select", default="q", show_default=False)
        if isinstance(choice, str):
            s = choice.strip()
            if s.lower() == "q":
                return None
            if s.startswith("/"):
                term = s[1:].strip()
                if not term:
                    term = click.prompt("Filter contains", default="", show_default=False)
                term_l = term.lower()
                current = [it for it in items if term_l in it.lower()]
                filter_note = f"(filtered: '{term}')" if term else ""
                if not current:
                    click.echo("No matches. Clearing filter.")
                    current = list(items)
                    filter_note = ""
                continue
        try:
            num = int(choice)
            if 1 <= num <= len(current):
                return current[num - 1]
        except (ValueError, TypeError):
            pass
        click.echo("Invalid selection. Try again.")


def _scan_notion_rows(scan_dir: Path) -> List[Dict[str, Any]]:
    """Scan for deepcast/consensus JSONs and build table rows: one per analysis file.

    Adds a 'type' field indicating consensus, precision, recall, or deepcast type.
    """

    def _format_date_ymd(s: Optional[str]) -> str:
        if not isinstance(s, str) or not s.strip():
            return "Unknown"
        # Try robust parsing first
        try:
            from dateutil import parser as dtparse

            return dtparse.parse(s).date().isoformat()
        except Exception:
            pass
        # Fallback: extract first YYYY-MM-DD pattern
        m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            return m.group(1)
        # Last resort: take last 10 chars if they look like a date-ish token
        t = s.strip()
        return t[-10:] if len(t) >= 10 else t

    rows: List[Dict[str, Any]] = []

    # Helper to push a row from paths and metadata
    def add_row(episode_dir: Path, analysis_path: Path, ai: str, asr: str, kind: str, track: str):
        show = "Unknown"
        title = "Unknown"
        date = "Unknown"
        em = episode_dir / "episode-meta.json"
        if em.exists():
            try:
                emd = json.loads(em.read_text(encoding="utf-8"))
                show = emd.get("show", show)
                title = emd.get("episode_title", title)
                dval = emd.get("episode_published") or emd.get("date")
                date = _format_date_ymd(dval)
            except Exception:
                pass
        notion_done = (episode_dir / "notion.out.json").exists()
        rows.append(
            {
                "path": analysis_path,
                "dir": episode_dir,
                "show": show,
                "date": date,
                "title": title,
                "ai": ai,
                "asr": asr,
                "type": kind,
                "track": track,
                "notion": notion_done,
            }
        )

    # Deepcast analyses
    for analysis_file in scan_dir.rglob("deepcast-*.json"):
        try:
            data = json.loads(analysis_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = data.get("deepcast_metadata", {})
        ai = meta.get("model", "unknown")
        asr = meta.get("asr_model", "unknown")
        # Determine kind: deepcast type or precision/recall from filename suffix
        kind = meta.get("deepcast_type") or ""
        stem = analysis_file.stem
        track = "S"  # Single by default
        if stem.endswith("-precision"):
            track = "P"
        elif stem.endswith("-recall"):
            track = "R"
        if not kind:
            kind = "general"
        add_row(analysis_file.parent, analysis_file, ai, asr, kind, track)

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
        add_row(analysis_file.parent, analysis_file, ai, asr, dc_type, "C")

    # Sort newest first by directory date and file mtime
    rows.sort(key=lambda r: (r["date"], r["path"].stat().st_mtime), reverse=True)
    return rows


def _interactive_table_flow(
    db_id: Optional[str],
    db_name: Optional[str],
    scan_dir: Path,
    dry_run: bool = False,
    cover_image: bool = False,
    notion_client_from_env=None,  # Pass as parameter to avoid circular import
) -> Optional[Dict[str, Any]]:
    rows = _scan_notion_rows(scan_dir)
    # Promote consensus rows to the top order within same episode (show+date+title)
    rows.sort(
        key=lambda r: (
            r["show"],
            r["date"],
            r["title"],
            0 if r.get("type") == "consensus" else 1,
            r["path"].stat().st_mtime,
        ),
        reverse=True,
    )
    if not rows:
        print(f"❌ No deepcast files found in {scan_dir}")
        return None

    # Display table of available analyses
    print("\n🪄 Select an analysis to upload to Notion\n")
    print(
        f"{'#':>3}  {'Show':<20}  {'Date':<12}  {'Title':<30}  {'AI':<14}  {'ASR':<14}  {'Type':<18}  {'Trk':<4}  {'Rec':<3}  {'Notion':<6}"
    )
    print("-" * 140)

    # Sort to prefer consensus at top for the same episode
    for idx, r in enumerate(rows, start=1):
        show_trunc = r["show"][:20]
        title_trunc = r["title"][:30]
        ai_trunc = r["ai"][:14]
        asr_trunc = r["asr"][:14]
        type_trunc = r.get("type", "")[:18]
        track = r.get("track", "")
        rec_mark = "✓" if track == "C" else "-"
        notion_mark = "✓" if r["notion"] else "-"

        print(
            f"{idx:>3}  {show_trunc:<20}  {r['date']:<12}  {title_trunc:<30}  {ai_trunc:<14}  {asr_trunc:<14}  {type_trunc:<18}  {track:<4}  {rec_mark:<3}  {notion_mark:<6}"
        )

    # Prefer consensus row as default selection if available
    default_idx = None
    for i2, r in enumerate(rows, start=1):
        if r.get("track") == "C":
            default_idx = i2
            break

    print("\nEnter selection number, or Q to cancel.")
    default_hint = f" (Enter={default_idx})" if default_idx else ""
    ans = input(f"👉 1-{len(rows)}{default_hint}: ").strip().upper()
    if not ans and default_idx:
        ans = str(default_idx)
    if ans in {"Q", "QUIT", "EXIT"}:
        print("❌ Notion upload cancelled")
        return None
    try:
        i = int(ans)
        if not (1 <= i <= len(rows)):
            raise ValueError
    except Exception:
        print("❌ Invalid selection")
        return None

    chosen = rows[i - 1]

    # DB prompt with YAML presets if available
    default_db = db_id or os.getenv("NOTION_DB_ID", "")
    selected_db_name = db_name
    try:
        mgr = get_yaml_config_manager()
        dbs = mgr.list_notion_databases()
    except Exception:
        dbs = {}
    if dbs:
        names = list(dbs.keys())
        preset: Optional[NotionDatabase] = None
        if selected_db_name and selected_db_name in dbs:
            preset = dbs[selected_db_name]
        print("\nSelect Notion database:")
        for i3, name in enumerate(names, start=1):
            mark = "*" if preset and selected_db_name == name else ""
            print(f"  {i3}. {name} {mark}")
        print(f"  0. Enter ID manually{' (default)' if default_db else ''}")
        sel = input("Choice [0-{}]: ".format(len(names))).strip()
        if sel.isdigit() and int(sel) in range(1, len(names) + 1):
            selected_db_name = names[int(sel) - 1]
            preset = dbs[selected_db_name]
        elif preset is None and selected_db_name and selected_db_name in dbs:
            preset = dbs[selected_db_name]

        if preset is not None:
            db_val = preset.database_id
            selected_db_name = selected_db_name or preset.name
            preset_token = preset.token
        else:
            manual = input(f"Notion DB ID [{default_db}]: ").strip()
            db_val = manual or default_db  # type: ignore[assignment]
            preset_token = None
    else:
        db_val = (
            input(f"Notion DB ID [{default_db}]: ").strip()
            if _HAS_RICH
            else click.prompt("Notion DB ID", default=default_db, show_default=bool(default_db))
        )
        if not db_val:
            db_val = default_db  # type: ignore[assignment]
        preset_token = None

    # Determine effective dry-run setting for interactive mode:
    # - Respect CLI flag; do not auto-enable based on environment
    # - If Rich isn't available (fallback TTY UI), offer a prompt to toggle it
    effective_dry_run = dry_run
    if not _HAS_RICH:
        dry = click.prompt("Dry-run first? (y/N)", default="N")
        effective_dry_run = effective_dry_run or (str(dry).lower() in {"y", "yes"})

    # Cover image: always set if available in interactive mode; otherwise respect flag
    cover = True if _HAS_RICH else cover_image

    # If attempting a real publish, ensure NOTION_TOKEN is present; else exit early
    if not effective_dry_run and not os.getenv("NOTION_TOKEN"):
        raise SystemExit(
            f"Set NOTION_TOKEN environment variable to publish to Notion (database: {db_val})"
        )

    # Quick hint if a page already exists (best-effort)
    try:
        meta_for_hint = json.loads(
            (chosen["dir"] / "episode-meta.json").read_text(encoding="utf-8")
        )
        episode_title = meta_for_hint.get("episode_title") or meta_for_hint.get("title") or ""
        date_val = meta_for_hint.get("episode_published") or meta_for_hint.get("date") or ""
        if episode_title and db_val and not effective_dry_run and Client is not None:
            if notion_client_from_env:
                client = notion_client_from_env()
                filt = {"and": [{"property": "Episode", "rich_text": {"equals": episode_title}}]}
                if isinstance(date_val, str) and len(date_val) >= 10:
                    filt["and"].append({"property": "Date", "date": {"equals": date_val[:10]}})
                q = client.databases.query(database_id=db_val, filter=filt)
                if q.get("results"):
                    print("⚠️  Note: an existing Notion page with this title/date was found.")
    except Exception:
        pass

    return {
        "db_id": db_val,
        "db_name": selected_db_name,
        "token": preset_token,
        "input_path": chosen["path"],
        "meta_path": chosen["dir"] / "episode-meta.json",
        "dry_run": effective_dry_run,
        "cover": cover,
    }
