"""Quote extraction from transcripts.

Identifies and extracts notable quotes using heuristics and
optional semantic importance ranking.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from podx.domain.models.transcript import Transcript


class QuoteExtractor:
    """Extract notable quotes from transcripts."""

    def __init__(
        self,
        min_words: int = 10,
        max_words: int = 100,
        min_score: float = 0.3,
    ) -> None:
        """Initialize quote extractor.

        Args:
            min_words: Minimum quote length in words
            max_words: Maximum quote length in words
            min_score: Minimum quality score (0-1)
        """
        self.min_words = min_words
        self.max_words = max_words
        self.min_score = min_score

        # Patterns that indicate quotable content
        self.quotable_patterns = [
            r"\b(I think|I believe|In my opinion|My view is)\b",
            r"\b(The key is|The point is|What matters is)\b",
            r"\b(The truth is|The fact is|The reality is)\b",
            r"\b(Remember|Keep in mind|Don\'t forget)\b",
            r"\b(Always|Never|Must|Should)\b",
        ]

        # Patterns to exclude
        self.exclude_patterns = [
            r"\b(um|uh|like|you know|I mean)\b",
            r"\?\s*$",  # Questions
            r"\b(yeah|yes|no|okay|alright)\b",
        ]

    def extract_quotes(
        self,
        transcript: Transcript,
        max_quotes: int = 20,
        speaker_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract notable quotes from transcript.

        Args:
            transcript: Transcript to extract from
            max_quotes: Maximum number of quotes to return
            speaker_filter: Only extract from this speaker (optional)

        Returns:
            List of quote dicts with text, speaker, timestamp, score
        """
        candidates = []

        for segment in transcript.segments:
            # Apply speaker filter
            segment_speaker = getattr(segment, "speaker", None)
            if speaker_filter and segment_speaker != speaker_filter:
                continue

            text = segment.text.strip()
            if not text:
                continue

            # Check word count
            words = text.split()
            word_count = len(words)
            if word_count < self.min_words or word_count > self.max_words:
                continue

            # Calculate quote quality score
            score = self._score_quote(text)

            if score >= self.min_score:
                candidates.append(
                    {
                        "text": text,
                        "speaker": segment_speaker or "Unknown",
                        "timestamp": segment.start,
                        "score": score,
                        "word_count": word_count,
                    }
                )

        # Sort by score and return top quotes
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:max_quotes]

    def _score_quote(self, text: str) -> float:
        """Score quote quality (0-1, higher is better).

        Heuristics:
        - Contains quotable patterns (boost)
        - Contains filler words (penalty)
        - Ends with period (boost for complete sentences)
        - Contains specific numbers/data (boost)
        - Unique/uncommon words (boost)

        Args:
            text: Quote text

        Returns:
            Quality score between 0 and 1
        """
        score = 0.5  # Base score

        # Boost for quotable patterns
        for pattern in self.quotable_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.15
                break

        # Penalty for exclude patterns
        for pattern in self.exclude_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score -= 0.2
                break

        # Boost for complete sentence
        if text.endswith("."):
            score += 0.1

        # Boost for numbers/data
        if re.search(r"\d+", text):
            score += 0.05

        # Boost for uncommon words (simple heuristic: long words)
        words = text.split()
        long_words = [w for w in words if len(w) > 8]
        if len(long_words) >= 2:
            score += 0.1

        # Penalty for very short or very long
        word_count = len(words)
        if word_count < 15:
            score -= 0.05
        elif word_count > 60:
            score -= 0.1

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def extract_by_speaker(
        self, transcript: Transcript, top_n: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract top quotes for each speaker.

        Args:
            transcript: Transcript to extract from
            top_n: Number of quotes per speaker

        Returns:
            Dict mapping speaker name to list of quotes
        """
        # Get all speakers
        speakers: set[str] = set()
        for seg in transcript.segments:
            speaker = getattr(seg, "speaker", None)
            if speaker is not None:
                speakers.add(speaker)

        results: Dict[str, List[Dict[str, Any]]] = {}
        for speaker in speakers:
            quotes = self.extract_quotes(
                transcript, max_quotes=top_n, speaker_filter=speaker
            )
            if quotes:
                results[speaker] = quotes

        return results

    def find_highlights(
        self, transcript: Transcript, duration_threshold: float = 30.0
    ) -> List[Dict[str, Any]]:
        """Find highlight moments (clusters of high-quality quotes).

        Args:
            transcript: Transcript to analyze
            duration_threshold: Max time gap between quotes in a highlight (seconds)

        Returns:
            List of highlight dicts with start time, quotes, etc.
        """
        # Extract all quotes
        all_quotes = self.extract_quotes(transcript, max_quotes=100)

        if not all_quotes:
            return []

        # Sort by timestamp (not score) for temporal clustering
        all_quotes_sorted = sorted(all_quotes, key=lambda x: x["timestamp"])

        # Group into highlights based on temporal proximity
        highlights = []
        current_highlight: List[Dict[str, Any]] = []

        for quote in all_quotes_sorted:
            if not current_highlight:
                current_highlight = [quote]
            else:
                # Check time gap
                time_gap = quote["timestamp"] - current_highlight[-1]["timestamp"]
                if time_gap <= duration_threshold:
                    current_highlight.append(quote)
                else:
                    # Save current highlight if it has multiple quotes
                    if len(current_highlight) >= 2:
                        highlights.append(self._create_highlight(current_highlight))
                    current_highlight = [quote]

        # Add final highlight
        if len(current_highlight) >= 2:
            highlights.append(self._create_highlight(current_highlight))

        # Sort by quality (average score)
        highlights.sort(key=lambda x: x["avg_score"], reverse=True)

        return highlights

    def _create_highlight(self, quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create highlight dict from quote cluster.

        Args:
            quotes: List of quotes in the highlight

        Returns:
            Highlight dict
        """
        start_time = quotes[0]["timestamp"]
        end_time = quotes[-1]["timestamp"]
        avg_score = sum(q["score"] for q in quotes) / len(quotes)

        return {
            "start": start_time,
            "end": end_time,
            "duration": end_time - start_time,
            "quote_count": len(quotes),
            "avg_score": avg_score,
            "quotes": quotes,
        }
