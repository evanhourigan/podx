"""Page operations for Notion API - CRUD operations for pages and blocks."""
from typing import Any, Dict, List, Optional

import click

try:
    from notion_client import Client
except ImportError:
    Client = None  # type: ignore

from .block_utils import _split_blocks_for_notion


def _list_children_all(client: Client, page_id: str) -> List[Dict[str, Any]]:
    """List all children of a page, handling pagination."""
    all_children = []
    start_cursor = None

    while True:
        resp = client.blocks.children.list(
            block_id=page_id, start_cursor=start_cursor, page_size=100
        )
        all_children.extend(resp.get("results", []))

        if not resp.get("has_more"):
            break
        start_cursor = resp.get("next_cursor")

    return all_children


def _clear_children(client: Client, page_id: str) -> None:
    """Archive all existing children of a page."""
    children = _list_children_all(client, page_id)

    for child in children:
        try:
            client.blocks.update(block_id=child["id"], archived=True)
        except Exception:
            # Continue on non-fatal errors
            pass


def upsert_page(
    client: Client,
    db_id: str,
    podcast_name: str,
    episode_title: str,
    date_iso: Optional[str],
    podcast_prop: str = "Podcast",
    episode_prop: str = "Episode",
    date_prop: str = "Date",
    model_prop: str = "Model",
    asr_prop: str = "ASR Model",
    deepcast_model: Optional[str] = None,
    asr_model: Optional[str] = None,
    props_extra: Optional[Dict[str, Any]] = None,
    blocks: Optional[List[Dict[str, Any]]] = None,
    replace_content: bool = False,
) -> str:
    """
    Try to find an existing page (by podcast name, episode title and optionally date), else create.
    Returns the page ID.
    """
    db_schema = client.databases.retrieve(db_id)
    db_props: Dict[str, Any] = db_schema.get("properties", {})

    def _prop_exists(name: Optional[str]) -> bool:
        return bool(name) and name in db_props

    def _first_property_of_type(types: List[str]) -> Optional[str]:
        for pname, meta in db_props.items():
            if meta.get("type") in types:
                return pname
        return None

    # Ensure we have a valid title property for the page name
    if not _prop_exists(podcast_prop):
        fallback_title = _first_property_of_type(["title"])
        if not fallback_title:
            raise SystemExit(
                f"Notion database '{db_id}' is missing a title property; cannot create page"
            )
        click.echo(
            f"[yellow]Podcast property '{podcast_prop}' not found; using '{fallback_title}'.[/yellow]",
            err=True,
        )
        podcast_prop = fallback_title

    # Episode property fallback (rich_text/title/select/multi_select)
    if not _prop_exists(episode_prop):
        fallback_episode = _first_property_of_type(
            ["rich_text", "title", "select", "multi_select"]
        )
        if fallback_episode and fallback_episode != podcast_prop:
            click.echo(
                f"[yellow]Episode property '{episode_prop}' not found; using '{fallback_episode}'.[/yellow]",
                err=True,
            )
            episode_prop = fallback_episode
        else:
            click.echo(
                "[yellow]No suitable Notion property for episode titles; property will be skipped.[/yellow]",
                err=True,
            )
            episode_prop = None

    if episode_prop == podcast_prop:
        episode_prop = None

    if date_prop and not _prop_exists(date_prop):
        fallback_date = _first_property_of_type(["date"])
        if fallback_date:
            click.echo(
                f"[yellow]Date property '{date_prop}' not found; using '{fallback_date}'.[/yellow]",
                err=True,
            )
            date_prop = fallback_date
        else:
            click.echo(
                "[yellow]No date property in Notion database; date will be omitted.[/yellow]",
                err=True,
            )
            date_prop = None

    if model_prop and not _prop_exists(model_prop):
        click.echo(
            f"[yellow]Model property '{model_prop}' not found; skipping.[/yellow]",
            err=True,
        )
        model_prop = None

    if asr_prop and not _prop_exists(asr_prop):
        click.echo(
            f"[yellow]ASR property '{asr_prop}' not found; skipping.[/yellow]",
            err=True,
        )
        asr_prop = None

    filtered_props_extra: Dict[str, Any] = {}
    if props_extra:
        for key, value in props_extra.items():
            if _prop_exists(key):
                filtered_props_extra[key] = value
            else:
                click.echo(
                    f"[yellow]Extra property '{key}' not found; skipping.[/yellow]",
                    err=True,
                )
    props_extra = filtered_props_extra

    def _text_payload(prop_name: str, content: str) -> Dict[str, Any]:
        meta = db_props.get(prop_name, {})
        ptype = meta.get("type")
        if ptype == "title":
            return {"title": [{"type": "text", "text": {"content": content}}]}
        if ptype == "rich_text":
            return {"rich_text": [{"type": "text", "text": {"content": content}}]}
        if ptype == "select":
            return {"select": {"name": content}}
        if ptype == "multi_select":
            return {"multi_select": [{"name": content}]}
        return {"rich_text": [{"type": "text", "text": {"content": content}}]}

    props: Dict[str, Any] = {}
    props[podcast_prop] = _text_payload(podcast_prop, podcast_name)

    if episode_prop:
        props[episode_prop] = _text_payload(episode_prop, episode_title)

    if date_iso and date_prop:
        props[date_prop] = {"date": {"start": date_iso}}

    if deepcast_model and model_prop:
        props[model_prop] = _text_payload(model_prop, deepcast_model)

    if asr_model and asr_prop:
        props[asr_prop] = _text_payload(asr_prop, asr_model)

    if props_extra:
        props.update(props_extra)

    filters: List[Dict[str, Any]] = []
    if episode_prop:
        episode_type = db_props.get(episode_prop, {}).get("type")
        if episode_type == "title":
            filters.append(
                {"property": episode_prop, "title": {"equals": episode_title}}
            )
        elif episode_type == "rich_text":
            filters.append(
                {"property": episode_prop, "rich_text": {"equals": episode_title}}
            )
        elif episode_type == "select":
            filters.append(
                {"property": episode_prop, "select": {"equals": episode_title}}
            )
        elif episode_type == "multi_select":
            filters.append(
                {"property": episode_prop, "multi_select": {"contains": episode_title}}
            )

    if date_iso and date_prop:
        filters.append({"property": date_prop, "date": {"equals": date_iso}})

    if deepcast_model and model_prop:
        model_type = db_props.get(model_prop, {}).get("type")
        if model_type == "title":
            filters.append(
                {"property": model_prop, "title": {"equals": deepcast_model}}
            )
        elif model_type == "rich_text":
            filters.append(
                {"property": model_prop, "rich_text": {"equals": deepcast_model}}
            )
        elif model_type == "select":
            filters.append(
                {"property": model_prop, "select": {"equals": deepcast_model}}
            )
        elif model_type == "multi_select":
            filters.append(
                {"property": model_prop, "multi_select": {"contains": deepcast_model}}
            )

    if filters:
        q = client.databases.query(database_id=db_id, filter={"and": filters})
    else:
        q = client.databases.query(database_id=db_id)

    if q.get("results"):
        # Update existing page
        page_id = q["results"][0]["id"]
        client.pages.update(page_id=page_id, properties=props)

        if blocks is not None:
            if replace_content:
                _clear_children(client, page_id)

            # Handle chunking for large block lists
            if len(blocks) > 100:
                chunks = _split_blocks_for_notion(blocks)
                for chunk in chunks:
                    client.blocks.children.append(block_id=page_id, children=chunk)
            else:
                client.blocks.children.append(block_id=page_id, children=blocks)

        return page_id
    else:
        # Create new page
        if blocks and len(blocks) > 100:
            # Handle chunking for large block lists
            chunks = _split_blocks_for_notion(blocks)

            # Create page with first chunk
            resp = client.pages.create(
                parent={"database_id": db_id}, properties=props, children=chunks[0]
            )
            page_id = resp["id"]

            # Append remaining chunks
            for chunk in chunks[1:]:
                client.blocks.children.append(block_id=page_id, children=chunk)

            return page_id
        else:
            # Small content, create normally
            resp = client.pages.create(
                parent={"database_id": db_id}, properties=props, children=blocks or []
            )
            return resp["id"]
