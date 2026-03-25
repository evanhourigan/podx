"""Post-analysis Q&A engine.

Send questions about a transcript to an LLM and get answers.
Optionally log Q&A to Notion pages.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..llm import LLMMessage, get_provider
from ..logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a podcast research assistant. You have access to a full transcript "
    "of a podcast episode. Answer the user's question based on what was discussed "
    "in the episode. Be specific — cite speakers, timestamps, and direct quotes "
    "when relevant. If the transcript doesn't contain information to answer the "
    "question, say so clearly."
)


def ask_transcript(
    transcript: Dict[str, Any],
    question: str,
    model: str = "gpt-5.2",
    episode_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Send a question about a transcript to an LLM.

    Uses a single LLM call with the full transcript. For very long
    transcripts that exceed context, falls back to using only the
    analysis if available.

    Args:
        transcript: Transcript dict with segments
        question: The question to answer
        model: LLM model string (provider:model_name)
        episode_meta: Optional episode metadata for context

    Returns:
        Answer text
    """
    # Build transcript text
    segments = transcript.get("segments", [])
    lines = []
    for s in segments:
        speaker = s.get("speaker", "")
        text = s.get("text", "").strip()
        start = s.get("start", 0)
        minutes = int(start // 60)
        seconds = int(start % 60)
        ts = f"[{minutes}:{seconds:02d}]"

        if speaker:
            lines.append(f"{ts} {speaker}: {text}")
        else:
            lines.append(f"{ts} {text}")

    transcript_text = "\n".join(lines)

    # Build context header
    context_parts = []
    if episode_meta:
        if episode_meta.get("show"):
            context_parts.append(f"Show: {episode_meta['show']}")
        if episode_meta.get("episode_title"):
            context_parts.append(f"Episode: {episode_meta['episode_title']}")
        if episode_meta.get("episode_published"):
            context_parts.append(f"Date: {episode_meta['episode_published']}")

    context_header = "\n".join(context_parts) + "\n\n" if context_parts else ""

    user_prompt = (
        f"{context_header}"
        f"TRANSCRIPT:\n{transcript_text}\n\n"
        f"QUESTION: {question}"
    )

    # Parse model string
    provider_name = "openai"
    model_name = model
    if ":" in model:
        provider_name, model_name = model.split(":", 1)

    provider = get_provider(provider_name)
    messages = [
        LLMMessage.system(SYSTEM_PROMPT),
        LLMMessage.user(user_prompt),
    ]

    response = provider.complete(messages=messages, model=model_name, temperature=0.3)
    return response.content


def append_qa_to_notion(
    episode_title: str,
    question: str,
    answer: str,
    db_id: str,
    token: Optional[str] = None,
) -> None:
    """Append a Q&A entry to an episode's Notion page.

    Finds the episode page by title and appends a toggle block
    with the question as header and the answer as body.

    Args:
        episode_title: Episode title to find in Notion
        question: The question asked
        answer: The LLM's answer
        db_id: Notion database ID
        token: Notion API token (defaults to NOTION_TOKEN env var)
    """
    try:
        from notion_client import Client
    except ImportError:
        raise RuntimeError("notion-client not installed. Run: pip install notion-client")

    token = token or os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN not set")

    client = Client(auth=token)

    # Find the page by title
    db_schema = client.databases.retrieve(db_id)
    title_prop = None
    for pname, pinfo in db_schema.get("properties", {}).items():
        if pinfo.get("type") == "title":
            title_prop = pname
            break

    if not title_prop:
        raise RuntimeError("No title property found in Notion database")

    resp = client.databases.query(
        database_id=db_id,
        filter={"property": title_prop, "title": {"equals": episode_title}},
    )

    results = resp.get("results", [])
    if not results:
        raise RuntimeError(f"Episode '{episode_title}' not found in Notion")

    page_id = results[0]["id"]
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Build toggle block with Q&A
    # Truncate to Notion's 2000-char limit per rich_text element
    q_text = f"Q: {question} ({date_str})"
    a_text = f"A: {answer}"

    # Split answer into 2000-char chunks if needed
    answer_blocks: List[Dict[str, Any]] = []
    for i in range(0, len(a_text), 2000):
        chunk = a_text[i : i + 2000]
        answer_blocks.append(
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                },
            }
        )

    toggle_block = {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": q_text[:2000]}}],
            "children": answer_blocks,
        },
    }

    # Append to page
    client.blocks.children.append(block_id=page_id, children=[toggle_block])

    logger.info("Appended Q&A to Notion page", page_id=page_id, question=question[:50])
