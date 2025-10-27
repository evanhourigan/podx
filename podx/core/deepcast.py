"""Core deepcast engine - pure business logic.

No UI dependencies, no CLI concerns. Just podcast transcript analysis using LLM map-reduce.
Handles chunking, parallel API calls, and structured output generation.
"""
import asyncio
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..logging import get_logger

logger = get_logger(__name__)


class DeepcastError(Exception):
    """Raised when deepcast processing fails."""

    pass


def hhmmss(sec: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    h, remainder = divmod(sec, 3600)
    m, s = divmod(remainder, 60)
    return f"{int(h):02}:{int(m):02}:{int(s):02}"


def segments_to_plain_text(
    segs: List[Dict[str, Any]], with_time: bool, with_speaker: bool
) -> str:
    """Convert segments to plain text with optional timecodes and speaker labels."""
    lines = []
    for s in segs:
        t = f"[{hhmmss(s['start'])}] " if with_time and "start" in s else ""
        spk = f"{s.get('speaker', '')}: " if with_speaker and s.get("speaker") else ""
        txt = s.get("text", "").strip()
        if txt:
            lines.append(f"{t}{spk}{txt}")
    return "\n".join(lines)


def split_into_chunks(text: str, approx_chars: int) -> List[str]:
    """Split text into chunks, trying to keep paragraphs together."""
    if len(text) <= approx_chars:
        return [text]

    paras = text.split("\n")
    chunks = []
    cur = []
    cur_len = 0

    for p in paras:
        L = len(p) + 1  # +1 for newline
        if cur_len + L > approx_chars and cur:
            chunks.append("\n".join(cur))
            cur = []
            cur_len = 0
        cur.append(p)
        cur_len += L

    if cur:
        chunks.append("\n".join(cur))

    return chunks


class DeepcastEngine:
    """Pure deepcast logic with no UI dependencies.

    Implements map-reduce pattern for LLM-based podcast analysis:
    1. Split transcript into chunks
    2. Process chunks in parallel (map phase)
    3. Synthesize results (reduce phase)
    4. Extract structured JSON if requested

    Can be used by CLI, TUI studio, web API, or any other interface.
    """

    def __init__(
        self,
        model: str = "gpt-4.1",
        temperature: float = 0.2,
        max_chars_per_chunk: int = 24000,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize deepcast engine.

        Args:
            model: OpenAI model name (e.g., 'gpt-4.1', 'gpt-4.1-mini')
            temperature: Model temperature for generation
            max_chars_per_chunk: Maximum characters per chunk for map phase
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Optional OpenAI base URL override
            progress_callback: Optional callback for progress updates
        """
        self.model = model
        self.temperature = temperature
        self.max_chars_per_chunk = max_chars_per_chunk
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.progress_callback = progress_callback

        if not self.api_key:
            raise DeepcastError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

    def _report_progress(self, message: str):
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(message)

    def _get_client(self):
        """Get OpenAI client instance."""
        try:
            from openai import OpenAI
        except ImportError:
            raise DeepcastError(
                "openai library not installed. Install with: pip install openai"
            )

        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _chat_once(self, client, system: str, user: str) -> str:
        """Make a single chat completion call."""
        resp = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    async def _chat_once_async(self, client, system: str, user: str) -> str:
        """Async wrapper for chat_once to enable concurrent API calls."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._chat_once, client, system, user
        )

    def deepcast(
        self,
        transcript: Dict[str, Any],
        system_prompt: str,
        map_instructions: str,
        reduce_instructions: str,
        want_json: bool = False,
        json_schema: Optional[str] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Run deepcast analysis on transcript.

        Args:
            transcript: Transcript data with segments
            system_prompt: System prompt for all API calls
            map_instructions: Instructions for map phase (chunk processing)
            reduce_instructions: Instructions for reduce phase (synthesis)
            want_json: Whether to request structured JSON output
            json_schema: Optional JSON schema hint to include in reduce phase

        Returns:
            Tuple of (markdown_output, json_data)

        Raises:
            DeepcastError: If processing fails
        """
        segs = transcript.get("segments") or []
        if not segs:
            # Fallback to text field if no segments
            text = transcript.get("text", "")
            if not text.strip():
                raise DeepcastError("No transcript text found in input")
        else:
            # Convert segments to plain text
            has_time = any("start" in s and "end" in s for s in segs)
            has_spk = any("speaker" in s for s in segs)
            text = segments_to_plain_text(segs, has_time, has_spk)

        if not text.strip():
            raise DeepcastError("No transcript text found in input")

        logger.info(
            "Starting deepcast analysis",
            model=self.model,
            text_length=len(text),
            max_chunk_chars=self.max_chars_per_chunk,
        )

        # Split into chunks for map phase
        chunks = split_into_chunks(text, self.max_chars_per_chunk)
        logger.info("Split transcript into chunks", chunk_count=len(chunks))

        # Get OpenAI client
        client = self._get_client()

        # Map phase: process chunks in parallel
        self._report_progress(f"Processing {len(chunks)} chunks")

        async def process_chunks_parallel():
            """Process all chunks concurrently with rate limiting."""
            semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests

            async def process_chunk(i: int, chunk: str) -> str:
                async with semaphore:
                    prompt = f"{map_instructions}\n\nChunk {i+1}/{len(chunks)}:\n\n{chunk}"
                    self._report_progress(f"Processing chunk {i+1}/{len(chunks)}")
                    note = await self._chat_once_async(client, system_prompt, prompt)
                    return note

            tasks = [process_chunk(i, chunk) for i, chunk in enumerate(chunks)]
            return await asyncio.gather(*tasks)

        # Run parallel processing
        try:
            map_notes = asyncio.run(process_chunks_parallel())
        except Exception as e:
            raise DeepcastError(f"Map phase failed: {e}") from e

        logger.info("Map phase completed", notes_count=len(map_notes))

        # Reduce phase: synthesize results
        self._report_progress("Synthesizing results")

        reduce_prompt = (
            f"{reduce_instructions}\n\nChunk notes:\n\n"
            + "\n\n---\n\n".join(map_notes)
        )
        if want_json and json_schema:
            reduce_prompt += f"\n\n{json_schema}"

        try:
            final = self._chat_once(client, system_prompt, reduce_prompt)
        except Exception as e:
            raise DeepcastError(f"Reduce phase failed: {e}") from e

        logger.info("Reduce phase completed", output_length=len(final))

        # Extract JSON if present
        if want_json and "---JSON---" in final:
            md, js = final.split("---JSON---", 1)
            js = js.strip()

            # Handle fenced code blocks
            if js.startswith("```json"):
                js = js[7:]
            if js.startswith("```"):
                js = js[3:]
            if js.endswith("```"):
                js = js[:-3]
            js = js.strip()

            try:
                parsed = json.loads(js)
                logger.info("JSON extraction successful")
                return md.strip(), parsed
            except json.JSONDecodeError as e:
                logger.warning("JSON extraction failed", error=str(e))
                return md.strip(), None

        return final.strip(), None


# Convenience function for direct use
def deepcast_transcript(
    transcript: Dict[str, Any],
    system_prompt: str,
    map_instructions: str,
    reduce_instructions: str,
    model: str = "gpt-4.1",
    temperature: float = 0.2,
    max_chars_per_chunk: int = 24000,
    want_json: bool = False,
    json_schema: Optional[str] = None,
    api_key: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Run deepcast analysis on transcript.

    Args:
        transcript: Transcript data
        system_prompt: System prompt for all API calls
        map_instructions: Map phase instructions
        reduce_instructions: Reduce phase instructions
        model: OpenAI model name
        temperature: Model temperature
        max_chars_per_chunk: Max characters per chunk
        want_json: Request JSON output
        json_schema: Optional JSON schema hint
        api_key: OpenAI API key (optional)
        progress_callback: Optional progress callback

    Returns:
        Tuple of (markdown_output, json_data)
    """
    engine = DeepcastEngine(
        model=model,
        temperature=temperature,
        max_chars_per_chunk=max_chars_per_chunk,
        api_key=api_key,
        progress_callback=progress_callback,
    )
    return engine.deepcast(
        transcript,
        system_prompt,
        map_instructions,
        reduce_instructions,
        want_json,
        json_schema,
    )
