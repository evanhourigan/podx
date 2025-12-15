"""Block utilities for Notion API - splitting and rich text helpers."""

from typing import Any, Dict, List


def rt(s: str) -> List[Dict[str, Any]]:
    return [{"type": "text", "text": {"content": s}}]


def _split_blocks_for_notion(
    blocks: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Split blocks into chunks that respect content boundaries and stay under 100 blocks."""
    if len(blocks) <= 100:
        return [blocks]

    chunks = []
    current_chunk = []

    for i, block in enumerate(blocks):
        current_chunk.append(block)

        # Check if we need to split
        if len(current_chunk) >= 100:
            # Find optimal split point
            optimal_split = _find_optimal_split_point(blocks, i - len(current_chunk) + 1, i + 1)

            # Split at the optimal point
            if optimal_split < len(current_chunk):
                # Create chunk up to optimal split point
                chunk = current_chunk[:optimal_split]
                chunks.append(chunk)

                # Start new chunk from optimal split point
                current_chunk = current_chunk[optimal_split:]
            else:
                # No good split point found, use current chunk
                chunks.append(current_chunk)
                current_chunk = []

    # Add any remaining blocks
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _find_optimal_split_point(blocks: List[Dict[str, Any]], start_pos: int, target_end: int) -> int:
    """Find the optimal split point that keeps content together."""
    # Start from the target end and work backwards to find the best split
    best_split_pos = min(target_end, len(blocks))

    # Look within a reasonable range around the target
    search_start = max(start_pos, target_end - 50)  # Look back up to 50 blocks
    search_end = min(len(blocks), target_end + 10)  # Look forward up to 10 blocks

    for pos in range(search_start, search_end):
        if pos <= start_pos:
            continue

        # Check if this is a good split point
        if _is_optimal_split_point(blocks, pos):
            # Update best_split_pos only if this position is closer to target_end
            if abs(pos - target_end) < abs(best_split_pos - target_end):
                best_split_pos = pos

    return best_split_pos


def _is_optimal_split_point(blocks: List[Dict[str, Any]], pos: int) -> bool:
    """Check if a position is an optimal split point."""
    if pos >= len(blocks):
        return False

    current_block = blocks[pos]

    # If this is a heading, it's a great split point
    if current_block.get("type", "").startswith("heading"):
        return True

    # If this is a paragraph, analyze the content
    if current_block.get("type") == "paragraph":
        rich_text = current_block.get("paragraph", {}).get("rich_text", [])
        if rich_text and len(rich_text) > 0:
            content = rich_text[0].get("text", {}).get("content", "")

            # Check if this looks like a speaker label or section break
            is_section_break = any(
                marker in content.upper() for marker in ["##", "###", "SPEAKER", ":", "---"]
            )

            if is_section_break:
                return True

    return False
