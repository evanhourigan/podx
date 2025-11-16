#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click

from podx.domain.exit_codes import ExitCode

# Optional rich UI (similar feel to podx-browse)
try:
    from rich.console import Console

    _HAS_RICH = True
    _console = Console()
except Exception:  # pragma: no cover
    _HAS_RICH = False
    _console = None  # type: ignore

from podx.cli.cli_shared import read_stdin_json
from podx.cli.info import get_episode_workdir
from podx.cli.notion_services import (
    _interactive_table_flow,
    upsert_page,
)
from podx.core.notion import NotionEngine, md_to_blocks
from podx.yaml_config import NotionDatabase, get_yaml_config_manager

try:
    from notion_client import Client
except ImportError:
    Client = None  # type: ignore


# utils
def notion_client_from_env(token: Optional[str] = None) -> Client:
    if Client is None:
        raise SystemExit("Install notion-client: pip install notion-client")

    auth_token = token or os.getenv("NOTION_TOKEN")
    if not auth_token:
        raise SystemExit(
            "Set NOTION_TOKEN environment variable or configure a token via podx config."
        )

    return Client(auth=auth_token)


@click.command()
@click.option(
    "--db",
    "db_id",
    default=lambda: os.getenv("NOTION_DB_ID"),
    help="Target Notion database ID",
)
@click.option(
    "--config-db",
    "config_db_name",
    help="Named Notion database from podx config to use (overrides env defaults)",
)
@click.option(
    "--show", help="Podcast show name (auto-detect workdir, files, and models)"
)
@click.option(
    "--episode-date",
    help="Episode date YYYY-MM-DD (auto-detect workdir, files, and models)",
)
@click.option(
    "--select-model",
    help="If multiple deepcast models exist, specify which to use (e.g., 'gpt-4.1')",
)
@click.option("--title", help="Page title (or derive from --meta)")
@click.option(
    "--date", "date_iso", help="ISO date (YYYY-MM-DD) (or derive from --meta)"
)
@click.option(
    "--input",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Read DeepcastBrief JSON from file instead of stdin",
)
@click.option(
    "--markdown",
    "md_path",
    type=click.Path(exists=True, path_type=Path),
    help="Markdown file (alternative to --input)",
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(exists=True, path_type=Path),
    help="Structured JSON for extra Notion properties",
)
@click.option(
    "--meta",
    "meta_path",
    type=click.Path(exists=True, path_type=Path),
    help="Episode metadata JSON (to derive title/date)",
)
@click.option(
    "--podcast-prop",
    default=lambda: os.getenv("NOTION_PODCAST_PROP", "Podcast"),
    help="Notion property name for podcast name",
)
@click.option(
    "--date-prop",
    default=lambda: os.getenv("NOTION_DATE_PROP", "Date"),
    help="Notion property name for date",
)
@click.option(
    "--episode-prop",
    default=lambda: os.getenv("NOTION_EPISODE_PROP", "Episode"),
    help="Notion property name for episode title",
)
@click.option(
    "--model-prop",
    default="Model",
    help="Notion property name for deepcast model",
)
@click.option(
    "--asr-prop",
    default="ASR Model",
    help="Notion property name for ASR model",
)
@click.option(
    "--deepcast-model",
    help="Deepcast model name to store in Notion",
)
@click.option(
    "--asr-model",
    help="ASR model name to store in Notion",
)
@click.option(
    "--append-content",
    is_flag=True,
    help="Append to page body in Notion instead of replacing (default: replace)",
)
@click.option(
    "--cover-image",
    is_flag=True,
    help="Set podcast artwork as page cover (requires image_url in meta)",
)
@click.option(
    "--dry-run", is_flag=True, help="Parse and print Notion payload (don't write)"
)
@click.option(
    "--output",
    "-o",
    "output",
    type=click.Path(path_type=Path),
    help="Save summary JSON (page_id, url, properties) to file",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Interactive selection flow (show → date → model → run)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output structured JSON (suppresses Rich formatting)",
)
def main(
    db_id: Optional[str],
    config_db_name: Optional[str],
    show: Optional[str],
    episode_date: Optional[str],
    select_model: Optional[str],
    title: Optional[str],
    date_iso: Optional[str],
    input: Optional[Path],
    md_path: Optional[Path],
    json_path: Optional[Path],
    meta_path: Optional[Path],
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    model_prop: str,
    asr_prop: str,
    deepcast_model: Optional[str],
    asr_model: Optional[str],
    append_content: bool,
    cover_image: bool,
    dry_run: bool,
    output: Optional[Path],
    interactive: bool,
    json_output: bool,
):
    """
    Create or update a Notion page from Markdown (+ optional JSON props).
    Upsert by Title (+ Date if provided).
    """

    # Interactive table flow
    if interactive:
        params = _interactive_table_flow(
            db_id,
            config_db_name,
            Path.cwd(),
            dry_run=dry_run,
            cover_image=cover_image,
            notion_client_from_env=notion_client_from_env,
        )
        if not params:
            return

        # Inject selected parameters
        db_id = params["db_id"]
        config_db_name = params.get("db_name", config_db_name)
        if params.get("token"):
            selected_token = params["token"]
        input = params["input_path"]
        meta_path = params.get("meta_path")
        dry_run = params["dry_run"]
        cover_image = params.get("cover", cover_image)

    # Auto-detect workdir and files if --show and --episode-date provided
    if show and episode_date:
        workdir = get_episode_workdir(show, episode_date)
        if not workdir.exists():
            raise SystemExit(f"Episode directory not found: {workdir}")

        # Auto-detect the most recent deepcast analysis if not specified
        if not input and not md_path:
            # Check for both new and legacy deepcast formats
            deepcast_files = list(workdir.glob("deepcast-*.json"))
            if deepcast_files:
                if select_model:
                    # Filter for specific model
                    model_suffix = select_model.replace(".", "_").replace("-", "_")
                    matching_files = [
                        f for f in deepcast_files if f.stem.endswith(f"-{model_suffix}")
                    ]
                    if matching_files:
                        # Sort by modification time, newest first
                        input = max(matching_files, key=lambda p: p.stat().st_mtime)
                        click.echo(
                            f"📄 Selected deepcast file for {select_model}: {input.name}"
                        )
                    else:
                        available_models = [
                            f.stem.split("-")[-1].replace("_", ".")
                            for f in deepcast_files
                        ]
                        raise SystemExit(
                            f"No deepcast analysis found for model '{select_model}'. Available: {', '.join(set(available_models))}"
                        )
                else:
                    # Sort by modification time, newest first
                    input = max(deepcast_files, key=lambda p: p.stat().st_mtime)
                    model_from_filename = input.stem.split("-")[-1].replace("_", ".")
                    click.echo(
                        f"📄 Auto-detected deepcast file: {input.name} (model: {model_from_filename})"
                    )
                    if len(deepcast_files) > 1:
                        available_models = [
                            f.stem.split("-")[-1].replace("_", ".")
                            for f in deepcast_files
                        ]
                        click.echo(
                            f"💡 Multiple models available: {', '.join(set(available_models))}. Use --select-model to choose."
                        )
            else:
                raise SystemExit(f"No deepcast analysis found in {workdir}")

        # Auto-detect meta file if not specified
        if not meta_path:
            episode_meta = workdir / "episode-meta.json"
            if episode_meta.exists():
                meta_path = episode_meta
                click.echo(f"📋 Auto-detected metadata: {episode_meta.name}")

        # Auto-detect models from files if not specified
        if input and not deepcast_model:
            try:
                deepcast_data = json.loads(input.read_text())
                auto_deepcast_model = deepcast_data.get("deepcast_metadata", {}).get(
                    "model"
                )
                if auto_deepcast_model:
                    deepcast_model = auto_deepcast_model
                    click.echo(f"🤖 Auto-detected deepcast model: {deepcast_model}")
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        if not asr_model:
            transcript_file = workdir / "transcript.json"
            if transcript_file.exists():
                try:
                    transcript_data = json.loads(transcript_file.read_text())
                    auto_asr_model = transcript_data.get("asr_model")
                    if auto_asr_model:
                        asr_model = auto_asr_model
                        click.echo(f"🎤 Auto-detected ASR model: {asr_model}")
                except (json.JSONDecodeError, FileNotFoundError):
                    pass

    selected_db: Optional[NotionDatabase] = None
    selected_token: Optional[str] = None
    if config_db_name:
        try:
            mgr = get_yaml_config_manager()
            selected_db = mgr.get_notion_database(config_db_name)
            if not selected_db:
                raise SystemExit(
                    f"No Notion database named '{config_db_name}' found in podx config."
                )
        except Exception as exc:
            raise SystemExit(f"Failed to load podx config: {exc}")

    if selected_db:
        db_id = db_id or selected_db.database_id
        podcast_prop = podcast_prop or selected_db.podcast_property
        date_prop = date_prop or selected_db.date_property
        episode_prop = episode_prop or selected_db.episode_property
        selected_token = selected_db.token

    if not db_id:
        raise SystemExit(
            "Please pass --db, use --config-db, or set NOTION_DB_ID environment variable"
        )

    # Handle input modes: --input (from stdin/file) vs separate files
    if input:
        # Read DeepcastBrief JSON from file
        deepcast_data = json.loads(input.read_text(encoding="utf-8"))
    elif not md_path:
        # Read DeepcastBrief JSON from stdin
        deepcast_data = read_stdin_json()
    else:
        # Traditional separate files mode
        deepcast_data = None

    if deepcast_data:
        # Extract data from DeepcastBrief JSON
        md = deepcast_data.get("markdown", "")
        if not md:
            raise SystemExit("DeepcastBrief JSON must contain 'markdown' field")

        # Extract metadata if available
        meta = deepcast_data.get("metadata", {})

        # Merge episode metadata if available (from smart detection)
        if meta_path and meta_path.exists():
            episode_meta = json.loads(meta_path.read_text())
            # Merge episode metadata with transcript metadata, episode takes priority
            meta = {**meta, **episode_meta}

        # Extract structured data for Notion properties
        js = deepcast_data  # The whole deepcast output
    else:
        # Traditional mode: separate files
        if not md_path:
            raise SystemExit(
                "Either provide --input (for DeepcastBrief JSON) or --markdown (for separate files)"
            )

        # Prefer explicit CLI title/date, else derive from meta JSON
        meta = {}
        if meta_path:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        md = md_path.read_text(encoding="utf-8")

        # Extra Notion properties from JSON
        js = {}
        if json_path:
            js = json.loads(json_path.read_text(encoding="utf-8"))

    # Derive podcast name, episode title and date
    podcast_name = meta.get("show") or "Unknown Podcast"
    if not title:
        title = meta.get("episode_title") or meta.get("title") or "Podcast Notes"
    episode_title = title

    # Auto-detect deepcast model from available data if not provided via CLI
    if not deepcast_model:
        # Try to extract from deepcast metadata in meta (from unified JSON)
        if hasattr(meta, "get") and meta.get("deepcast_metadata"):
            auto_deepcast_model = meta["deepcast_metadata"].get("model")
            if auto_deepcast_model:
                deepcast_model = auto_deepcast_model
                click.echo(f"🤖 Auto-detected deepcast model: {deepcast_model}")
        # Try to extract from separate JSON properties file
        elif hasattr(js, "get") and js.get("deepcast_metadata"):
            auto_deepcast_model = js["deepcast_metadata"].get("model")
            if auto_deepcast_model:
                deepcast_model = auto_deepcast_model
                click.echo(f"🤖 Auto-detected deepcast model: {deepcast_model}")

    # Extract ASR model if not provided via CLI
    if not asr_model:
        # First try deepcast metadata (preferred source)
        if hasattr(js, "get") and js.get("deepcast_metadata"):
            auto_asr_model = js["deepcast_metadata"].get("asr_model")
            if auto_asr_model:
                asr_model = auto_asr_model
                click.echo(f"🎤 Auto-detected ASR model from deepcast: {asr_model}")

        # Fallback to original transcript metadata
        if not asr_model and hasattr(meta, "get"):
            asr_model = meta.get("asr_model")

        # Last resort: try loading transcript.json from same directory
        if not asr_model and meta_path:
            transcript_path = meta_path.parent / "transcript.json"
            if transcript_path.exists():
                try:
                    transcript_data = json.loads(transcript_path.read_text())
                    asr_model = transcript_data.get("asr_model")
                    if asr_model:
                        click.echo(
                            f"🎤 Auto-detected ASR model from transcript: {asr_model}"
                        )
                except (json.JSONDecodeError, FileNotFoundError):
                    pass

    if not date_iso:
        d = meta.get("episode_published") or meta.get("date")
        if isinstance(d, str):
            # Handle different date formats
            try:
                from datetime import datetime

                # Try parsing RFC 2822 format (e.g., "Wed, 11 Jun 2025 14:18:45 +0000")
                if "," in d and len(d) > 20:
                    # Try with UTC offset format first
                    try:
                        dt = datetime.strptime(d, "%a, %d %b %Y %H:%M:%S %z")
                        date_iso = dt.strftime("%Y-%m-%d")
                    except ValueError:
                        # Fallback to timezone name format (e.g., GMT)
                        dt = datetime.strptime(d, "%a, %d %b %Y %H:%M:%S %Z")
                        date_iso = dt.strftime("%Y-%m-%d")
                # Try ISO format
                elif len(d) >= 10:
                    date_iso = d[:10]  # YYYY-MM-DD from ISO datetime
            except ValueError:
                # Fallback: try to extract YYYY-MM-DD pattern
                if len(d) >= 10:
                    date_iso = d[:10]

    blocks = md_to_blocks(md)

    # Extra Notion properties from JSON
    props_extra: Dict[str, Any] = {}
    if js:
        # Generate meaningful tags from episode metadata and analysis
        tags = []

        # Add model information as tags
        deepcast_meta = js.get("deepcast_metadata", {})
        if deepcast_meta.get("model"):
            tags.append(f"AI-{deepcast_meta['model']}")
        if deepcast_meta.get("asr_model"):
            tags.append(f"ASR-{deepcast_meta['asr_model']}")

        # Add podcast type if available
        podcast_type = deepcast_meta.get("podcast_type")
        if podcast_type and podcast_type != "general":
            tags.append(f"Type-{podcast_type}")

        # Extract technology/topic keywords from key points (limit to avoid clutter)
        key_points = (js.get("key_points") or [])[:5]
        tech_keywords = set()

        # Common technology terms to extract as tags
        tech_terms = [
            "AI",
            "machine learning",
            "ChatGPT",
            "Claude",
            "OpenAI",
            "agents",
            "automation",
            "engineering",
            "coding",
            "development",
            "API",
            "workflow",
            "productivity",
            "software",
            "platform",
            "tool",
            "framework",
            "algorithm",
            "model",
            "data",
            "Python",
            "JavaScript",
            "React",
            "Node",
            "Docker",
            "cloud",
            "AWS",
            "database",
        ]

        for kp in key_points:
            for term in tech_terms:
                if term.lower() in kp.lower() and len(tech_keywords) < 3:
                    tech_keywords.add(term)

        # Add technology tags
        for tech in tech_keywords:
            tags.append(tech)

        # Convert to Notion format
        if tags:
            cleaned_tags = []
            for tag in tags[:6]:  # Limit to 6 tags total
                clean_tag = (
                    tag.replace(",", "").replace(".", "").replace(";", "")[:50].strip()
                )
                if clean_tag:
                    cleaned_tags.append({"name": clean_tag})

            if cleaned_tags:
                props_extra["Tags"] = {"multi_select": cleaned_tags}

    # Handle cover image
    cover_url = None
    if cover_image and meta:
        cover_url = (
            meta.get("image_url") or meta.get("artwork_url") or meta.get("cover_url")
        )

    if dry_run:
        payload = {
            "db_id": db_id,
            "podcast_prop": podcast_prop,
            "episode_prop": episode_prop,
            "date_prop": date_prop,
            "podcast_name": podcast_name,
            "episode_title": episode_title,
            "date_iso": date_iso,
            "replace_content": not append_content,
            "cover_image": cover_url is not None,
            "cover_url": cover_url,
            "props_extra_keys": list(props_extra.keys()) if props_extra else [],
            "blocks_count": len(blocks),
        }
        print(json.dumps(payload, indent=2))
        print("\n✅ Dry run prepared. Payload summarized above.")
        return

    client = notion_client_from_env(selected_token)
    page_id = upsert_page(
        client=client,
        db_id=db_id,
        podcast_name=podcast_name,
        episode_title=episode_title,
        date_iso=date_iso,
        podcast_prop=podcast_prop,
        episode_prop=episode_prop,
        date_prop=date_prop,
        model_prop=model_prop,
        asr_prop=asr_prop,
        deepcast_model=deepcast_model,
        asr_model=asr_model,
        props_extra=props_extra,
        blocks=blocks,
        replace_content=not append_content,
    )

    # Set cover image if requested and available
    if cover_url:
        engine = NotionEngine(api_token=selected_token)
        engine.set_page_cover(page_id, cover_url)

    # Build result summary
    result = {
        "ok": True,
        "page_id": page_id,
        "url": f"https://notion.so/{page_id.replace('-', '')}",
    }

    # Save to output file if requested
    if output:
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if interactive:
            print("\n✅ Notion upload complete")
            print(f"   Episode: {episode_title}")
            print(
                f"   Database: {config_db_name if config_db_name else db_id[:8] + '...'}"
            )
            print(f"   Page URL: {result['url']}")
            if output:
                print(f"   Summary saved: {output}")

    # Print result (interactive: detailed message, non-interactive: JSON)
    if interactive:
        if not output:
            print("\n✅ Notion upload complete")
            print(f"   Episode: {episode_title}")
            print(
                f"   Database: {config_db_name if config_db_name else db_id[:8] + '...'}"
            )
            print(f"   Page URL: {result['url']}")
    else:
        if json_output:
            # Structured JSON output with success wrapper
            output_data = {
                "success": True,
                "notion": result,
                "episode": {
                    "title": episode_title,
                    "podcast": podcast_name,
                    "date": date_iso,
                },
            }
            print(json.dumps(output_data, indent=2))
        else:
            # Original behavior - simple result JSON
            print(json.dumps(result, indent=2))

    # Exit with success
    sys.exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    main()
