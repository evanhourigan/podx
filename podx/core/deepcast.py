"""Core deepcast engine - pure business logic.

No UI dependencies, no CLI concerns. Just podcast transcript analysis using LLM map-reduce.
Handles chunking, parallel API calls, and structured output generation.
"""

import asyncio
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..llm import LLMMessage, LLMProvider, get_provider
from ..logging import get_logger
from ..progress import ProgressReporter, SilentProgressReporter

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

    Can be used by CLI, web API, or any other interface.
    """

    def __init__(
        self,
        model: str = "gpt-4",
        temperature: float = 0.2,
        max_chars_per_chunk: int = 24000,
        llm_provider: Optional[LLMProvider] = None,
        provider_name: str = "openai",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        progress: Optional[Union[ProgressReporter, Callable[[str], None]]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,  # Deprecated
    ):
        """Initialize deepcast engine.

        Args:
            model: Model name (e.g., 'gpt-4', 'claude-3-opus', 'llama2')
            temperature: Model temperature for generation
            max_chars_per_chunk: Maximum characters per chunk for map phase
            llm_provider: Optional pre-configured LLM provider instance
            provider_name: Provider to use if llm_provider not provided (default: openai)
            api_key: API key (defaults to provider-specific env var)
            base_url: Optional base URL override
            progress: Optional ProgressReporter or legacy callback function
            progress_callback: Deprecated - use progress parameter instead
        """
        self.model = model
        self.temperature = temperature
        self.max_chars_per_chunk = max_chars_per_chunk

        # Backward compatibility: expose api_key and base_url attributes
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url

        # Handle progress reporting (support both new and legacy APIs)
        if progress is not None:
            if isinstance(progress, ProgressReporter):
                self.progress = progress
                self.progress_callback = None
            else:
                # Legacy callback function
                self.progress = None
                self.progress_callback = progress
        elif progress_callback is not None:
            # Deprecated parameter
            self.progress = None
            self.progress_callback = progress_callback
        else:
            # No progress reporting
            self.progress = SilentProgressReporter()
            self.progress_callback = None

        # Use provided provider or create one
        if llm_provider:
            self.llm_provider = llm_provider
        else:
            try:
                self.llm_provider = get_provider(
                    provider_name, api_key=api_key, base_url=base_url
                )
            except Exception as e:
                raise DeepcastError(f"Failed to initialize LLM provider: {e}") from e

    def _report_progress(self, message: str):
        """Report progress via ProgressReporter or legacy callback."""
        # New API: ProgressReporter
        if self.progress and not isinstance(self.progress, SilentProgressReporter):
            self.progress.update_step(message)
        # Legacy API: callback function
        elif self.progress_callback:
            self.progress_callback(message)

    def _get_client(self):
        """Get OpenAI client instance (backward compatibility).

        This method exists for backward compatibility with tests.
        New code should use self.llm_provider directly.
        """
        # Return a mock-friendly object that works with old tests
        if hasattr(self.llm_provider, "_sync_client"):
            return self.llm_provider._sync_client
        # For non-OpenAI providers or mocks, return the provider itself
        return self.llm_provider

    def _chat_once(self, system: str, user: str) -> str:
        """Make a single chat completion call (synchronous)."""
        messages = [LLMMessage.system(system), LLMMessage.user(user)]
        response = self.llm_provider.complete(
            messages=messages, model=self.model, temperature=self.temperature
        )
        return response.content

    async def _chat_once_async(self, system: str, user: str) -> str:
        """Make a single chat completion call (asynchronous)."""
        messages = [LLMMessage.system(system), LLMMessage.user(user)]
        response = await self.llm_provider.complete_async(
            messages=messages, model=self.model, temperature=self.temperature
        )
        return response.content

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

        # Map phase: process chunks in parallel
        self._report_progress(f"Processing {len(chunks)} chunks")

        async def process_chunks_parallel():
            """Process all chunks concurrently with rate limiting."""
            semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests

            async def process_chunk(i: int, chunk: str) -> str:
                async with semaphore:
                    prompt = (
                        f"{map_instructions}\n\nChunk {i+1}/{len(chunks)}:\n\n{chunk}"
                    )
                    self._report_progress(f"Processing chunk {i+1}/{len(chunks)}")
                    note = await self._chat_once_async(system_prompt, prompt)
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
            f"{reduce_instructions}\n\nChunk notes:\n\n" + "\n\n---\n\n".join(map_notes)
        )
        if want_json and json_schema:
            reduce_prompt += f"\n\n{json_schema}"

        try:
            final = self._chat_once(system_prompt, reduce_prompt)
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
