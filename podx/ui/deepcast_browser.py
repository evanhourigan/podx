"""Interactive browser for selecting episodes to deepcast."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

try:
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..logging import get_logger
from ..ui_styles import (
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    TABLE_SHOW_STYLE,
    TABLE_DATE_STYLE,
    TABLE_TITLE_COL_STYLE,
)
from .interactive_browser import InteractiveBrowser

logger = get_logger(__name__)


def _truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def parse_deepcast_metadata(deepcast_file: Path) -> Dict[str, str]:
    """
    Parse metadata from deepcast file (JSON first, then filename).
    Returns dict with 'asr_model', 'ai_model', 'deepcast_type', 'transcript_variant'.
    """
    metadata = {
        "asr_model": "unknown",
        "ai_model": "unknown",
        "deepcast_type": "unknown",
        "transcript_variant": "unknown"
    }

    # Try to read from JSON file first
    try:
        data = json.loads(deepcast_file.read_text(encoding="utf-8"))
        deepcast_meta = data.get("deepcast_metadata", {})
        if deepcast_meta:
            metadata["asr_model"] = deepcast_meta.get("asr_model", "unknown")
            metadata["ai_model"] = deepcast_meta.get("model", "unknown")
            metadata["deepcast_type"] = deepcast_meta.get("deepcast_type", "unknown")
            metadata["transcript_variant"] = deepcast_meta.get("transcript_variant", "unknown")
            return metadata
    except Exception:
        pass

    # Fall back to filename parsing
    # New format: deepcast-{asr}-{ai}-{type}.json
    # Legacy format: deepcast-{ai}.json
    filename = deepcast_file.stem

    if filename.count("-") >= 3:  # New format
        parts = filename.split("-", 3)  # Split into at most 4 parts: "deepcast", asr, ai, type
        if len(parts) == 4:
            metadata["asr_model"] = parts[1].replace("_", "-")
            metadata["ai_model"] = parts[2].replace("_", ".")
            metadata["deepcast_type"] = parts[3].replace("_", "-")
    elif filename.startswith("deepcast-"):  # Legacy format
        ai_model = filename[len("deepcast-"):].replace("_", ".")
        metadata["ai_model"] = ai_model

    return metadata


def scan_deepcastable_episodes(scan_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan directory for episodes that can be deepcast (have transcripts).
    Returns grouped data structure for complex table display.
    """
    episodes_dict = {}  # Key: (show, date, episode_dir)

    # Find all transcript files (diarized, aligned, base)
    transcript_patterns = [
        "transcript-diarized-*.json",
        "diarized-transcript-*.json",
        "transcript-aligned-*.json",
        "aligned-transcript-*.json",
        "transcript-*.json"
    ]

    for pattern in transcript_patterns:
        for transcript_file in scan_dir.rglob(pattern):
            try:
                # Skip if it's not a valid ASR transcript file
                filename = transcript_file.stem

                # Extract ASR model
                asr_model = None
                transcript_variant = "base"

                if filename.startswith("transcript-diarized-"):
                    asr_model = filename[len("transcript-diarized-"):]
                    transcript_variant = "diarized"
                elif filename.startswith("diarized-transcript-"):
                    asr_model = filename[len("diarized-transcript-"):]
                    transcript_variant = "diarized"
                elif filename.startswith("transcript-aligned-"):
                    asr_model = filename[len("transcript-aligned-"):]
                    transcript_variant = "aligned"
                elif filename.startswith("aligned-transcript-"):
                    asr_model = filename[len("aligned-transcript-"):]
                    transcript_variant = "aligned"
                elif filename.startswith("transcript-") and not filename.startswith("transcript-diarized-") and not filename.startswith("transcript-aligned-"):
                    asr_model = filename[len("transcript-"):]
                    transcript_variant = "base"
                else:
                    continue

                if not asr_model:
                    continue

                # Load transcript for metadata
                transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))

                # Get episode directory and metadata
                episode_dir = transcript_file.parent
                episode_meta_file = episode_dir / "episode-meta.json"
                episode_meta = {}
                if episode_meta_file.exists():
                    try:
                        episode_meta = json.loads(episode_meta_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass

                # Extract show and date
                show = episode_meta.get("show") or transcript_data.get("show") or "Unknown"
                date = episode_meta.get("episode_published", "")
                if date:
                    try:
                        from dateutil import parser as dtparse
                        parsed = dtparse.parse(date)
                        date = parsed.strftime("%Y-%m-%d")
                    except Exception:
                        date = date[:10] if len(date) >= 10 else "Unknown"
                else:
                    # Try to extract from directory name
                    date = episode_dir.name if re.match(r"^\d{4}-\d{2}-\d{2}$", episode_dir.name) else "Unknown"

                title = episode_meta.get("episode_title") or transcript_data.get("episode_title") or "Unknown"

                # Create episode key
                episode_key = (show, date, str(episode_dir))

                # Initialize episode entry if not exists
                if episode_key not in episodes_dict:
                    episodes_dict[episode_key] = {
                        "show": show,
                        "date": date,
                        "title": title,
                        "directory": episode_dir,
                        "episode_meta": episode_meta,
                        "asr_models": {},  # Key: asr_model, Value: {variant, file, deepcasts}
                    }

                # Add ASR model entry (prefer diarized > aligned > base)
                if asr_model not in episodes_dict[episode_key]["asr_models"]:
                    episodes_dict[episode_key]["asr_models"][asr_model] = {
                        "variant": transcript_variant,
                        "file": transcript_file,
                        "deepcasts": {},  # Key: ai_model, Value: {types: [list of types]}
                    }
                else:
                    # Update if this is a better variant
                    priority = {"diarized": 3, "aligned": 2, "base": 1}
                    current = episodes_dict[episode_key]["asr_models"][asr_model]["variant"]
                    if priority.get(transcript_variant, 0) > priority.get(current, 0):
                        episodes_dict[episode_key]["asr_models"][asr_model]["variant"] = transcript_variant
                        episodes_dict[episode_key]["asr_models"][asr_model]["file"] = transcript_file

            except Exception:
                continue

    # Now scan for existing deepcast files
    for deepcast_file in scan_dir.rglob("deepcast-*.json"):
        try:
            metadata = parse_deepcast_metadata(deepcast_file)
            episode_dir = deepcast_file.parent

            # Find matching episode
            for episode_key, episode_data in episodes_dict.items():
                if str(episode_data["directory"]) == str(episode_dir):
                    asr_model = metadata["asr_model"]
                    ai_model = metadata["ai_model"]
                    deepcast_type = metadata["deepcast_type"]

                    # If ASR model doesn't exist, add it
                    if asr_model not in episode_data["asr_models"] and asr_model != "unknown":
                        episode_data["asr_models"][asr_model] = {
                            "variant": metadata.get("transcript_variant", "unknown"),
                            "file": None,
                            "deepcasts": {},
                        }

                    # Add deepcast to the ASR model entry
                    if asr_model in episode_data["asr_models"] or asr_model == "unknown":
                        # For unknown ASR, try to match with any existing ASR model
                        if asr_model == "unknown" and episode_data["asr_models"]:
                            asr_model = list(episode_data["asr_models"].keys())[0]

                        if asr_model in episode_data["asr_models"]:
                            if ai_model not in episode_data["asr_models"][asr_model]["deepcasts"]:
                                episode_data["asr_models"][asr_model]["deepcasts"][ai_model] = []
                            if deepcast_type not in episode_data["asr_models"][asr_model]["deepcasts"][ai_model]:
                                episode_data["asr_models"][asr_model]["deepcasts"][ai_model].append(deepcast_type)
                    break
        except Exception:
            continue

    # Convert to list and sort
    episodes_list = list(episodes_dict.values())
    episodes_list.sort(key=lambda e: (e["show"], e["date"]), reverse=False)
    episodes_list.sort(key=lambda e: e["date"], reverse=True)  # Most recent first

    return episodes_list


def flatten_episodes_to_rows(episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flatten episodes structure into rows for table display.
    Each row represents one (Episode, ASR Model, AI Model) combination.
    """
    rows = []

    for episode in episodes:
        # If no ASR models, create one row with blanks
        if not episode["asr_models"]:
            rows.append({
                "episode": episode,
                "asr_model": "",
                "asr_variant": "",
                "ai_model": "",
                "deepcast_types": [],
                "transcript_file": None,
            })
            continue

        # For each ASR model
        for asr_model, asr_data in episode["asr_models"].items():
            variant_suffix = ""
            if asr_data["variant"] == "diarized":
                variant_suffix = ", D"
            elif asr_data["variant"] == "aligned":
                variant_suffix = ", A"

            # If no deepcasts, create one row
            if not asr_data["deepcasts"]:
                rows.append({
                    "episode": episode,
                    "asr_model": asr_model + variant_suffix,
                    "asr_model_raw": asr_model,
                    "asr_variant": asr_data["variant"],
                    "ai_model": "",
                    "deepcast_types": [],
                    "transcript_file": asr_data["file"],
                })
            else:
                # For each AI model with deepcasts
                for ai_model, types in asr_data["deepcasts"].items():
                    rows.append({
                        "episode": episode,
                        "asr_model": asr_model + variant_suffix,
                        "asr_model_raw": asr_model,
                        "asr_variant": asr_data["variant"],
                        "ai_model": ai_model,
                        "deepcast_types": types,
                        "transcript_file": asr_data["file"],
                    })

    return rows


class DeepcastBrowser(InteractiveBrowser):
    """Interactive browser for selecting episodes to deepcast."""

    def __init__(self, rows: List[Dict[str, Any]], items_per_page: int = 10):
        super().__init__(rows, items_per_page, item_name="row")
        # Keep rows as alias for backward compatibility
        self.rows = self.items

    def _get_item_title(self, item: Dict[str, Any]) -> str:
        """Get title of episode for selection confirmation."""
        episode = item.get("episode", {})
        return episode.get("title", "Unknown")

    def display_page(self) -> None:
        """Display current page with table and navigation options."""
        if not self.console:
            return

        # Calculate page bounds
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.items))
        page_items = self.items[start_idx:end_idx]

        # Create title with emoji
        title = f"🎙️ Episodes Available for Deepcast (Page {self.current_page + 1}/{self.total_pages})"

        # Compute dynamic Title width - standardize status width to 24
        term_width = self.console.size.width
        fixed_widths = {"num": 4, "asr": 12, "ai": 15, "type": 24, "show": 18, "date": 12}
        borders_allowance = 16
        title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)

        # Create table with shared styling
        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            border_style=TABLE_BORDER_STYLE,
            title=title,
            expand=False,
        )
        table.add_column("#", style=TABLE_NUM_STYLE, width=fixed_widths["num"], justify="right", no_wrap=True)
        table.add_column("ASR Model", style="yellow", width=fixed_widths["asr"], no_wrap=True, overflow="ellipsis")
        table.add_column("AI Model", style="green", width=fixed_widths["ai"], no_wrap=True, overflow="ellipsis")
        table.add_column("Type", style="white", width=fixed_widths["type"], no_wrap=True, overflow="ellipsis")
        table.add_column("Show", style=TABLE_SHOW_STYLE, width=fixed_widths["show"], no_wrap=True, overflow="ellipsis")
        table.add_column("Date", style=TABLE_DATE_STYLE, width=fixed_widths["date"], no_wrap=True)
        table.add_column("Title", style=TABLE_TITLE_COL_STYLE, width=title_width, no_wrap=True, overflow="ellipsis")

        # Add rows to table
        for idx, row in enumerate(page_items, start=start_idx + 1):
            episode = row["episode"]

            # Format type column
            types_str = ", ".join(row["deepcast_types"]) if row["deepcast_types"] else ""
            show = _truncate_text(episode["show"], fixed_widths["show"])
            date = episode["date"]
            title_text = _truncate_text(episode["title"], title_width)

            table.add_row(
                str(idx),
                row["asr_model"] or "",
                row["ai_model"] or "",
                types_str,
                show,
                date,
                title_text
            )

        self.console.print(table)

        # Show navigation options in Panel
        options = []
        options.append(
            f"[cyan]1-{len(self.items)}[/cyan]: Select episode to deepcast"
        )

        if self.current_page < self.total_pages - 1:
            options.append("[yellow]N[/yellow]: Next page")

        if self.current_page > 0:
            options.append("[yellow]P[/yellow]: Previous page")

        options.append("[red]Q[/red]: Quit")

        options_text = " • ".join(options)
        panel = Panel(
            options_text, title="Options", border_style="blue", padding=(0, 1)
        )
        self.console.print(panel)
