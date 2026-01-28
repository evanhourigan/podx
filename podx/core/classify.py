"""Heuristic-based episode classification.

Classifies podcast episodes by format (interview, panel, solo, etc.)
using transcript structure analysis. No LLM calls — purely heuristic.
"""

from typing import Any, Dict, List


def classify_episode(transcript: Dict[str, Any], episode_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Classify episode format using transcript heuristics.

    Args:
        transcript: Transcript dict with 'segments' array.
        episode_meta: Episode metadata dict.

    Returns:
        Classification result with format, confidence, and evidence.
    """
    segments = transcript.get("segments", [])
    if not segments:
        return _result("general", 0.0, _empty_evidence())

    # Gather evidence
    speakers = set()
    question_segments = 0
    total_segments = len(segments)
    turn_lengths: List[float] = []
    current_speaker = None
    current_turn_chars = 0

    for seg in segments:
        speaker = seg.get("speaker")
        text = seg.get("text", "")

        if speaker:
            speakers.add(speaker)

        # Track question segments
        if text.strip().endswith("?"):
            question_segments += 1

        # Track turn lengths (character count per speaker turn)
        if speaker != current_speaker:
            if current_turn_chars > 0:
                turn_lengths.append(current_turn_chars)
            current_speaker = speaker
            current_turn_chars = len(text)
        else:
            current_turn_chars += len(text)

    # Flush last turn
    if current_turn_chars > 0:
        turn_lengths.append(current_turn_chars)

    speaker_count = len(speakers)
    qa_ratio = question_segments / total_segments if total_segments > 0 else 0.0
    avg_turn_length = sum(turn_lengths) / len(turn_lengths) if turn_lengths else 0.0
    turn_count = len(turn_lengths)

    evidence = {
        "speaker_count": speaker_count,
        "qa_ratio": round(qa_ratio, 3),
        "avg_turn_length": round(avg_turn_length, 1),
        "turn_count": turn_count,
        "markers": [],
    }

    # Classification logic
    if speaker_count == 0:
        # No speaker labels — can't classify reliably
        return _result("general", 0.2, evidence)

    if speaker_count == 1:
        evidence["markers"].append("single-speaker")
        return _result("solo-commentary", 0.85, evidence)

    if speaker_count == 2:
        evidence["markers"].append("two-speaker")
        if qa_ratio > 0.15:
            evidence["markers"].append("question-heavy")
            return _result("interview-1on1", 0.85, evidence)
        elif qa_ratio > 0.08:
            evidence["markers"].append("moderate-questions")
            return _result("interview-1on1", 0.65, evidence)
        else:
            evidence["markers"].append("low-questions")
            # Two speakers but not many questions — could be co-hosted or conversational
            return _result("general", 0.5, evidence)

    # 3+ speakers
    evidence["markers"].append("multi-speaker")
    if speaker_count >= 3:
        if qa_ratio > 0.12:
            evidence["markers"].append("question-heavy")
            # Could be a panel with active moderator
            return _result("panel-discussion", 0.75, evidence)
        else:
            return _result("panel-discussion", 0.7, evidence)

    return _result("general", 0.4, evidence)


def _result(format_name: str, confidence: float, evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Build classification result."""
    return {
        "format": format_name,
        "confidence": round(confidence, 2),
        "evidence": evidence,
    }


def _empty_evidence() -> Dict[str, Any]:
    """Return empty evidence structure."""
    return {
        "speaker_count": 0,
        "qa_ratio": 0.0,
        "avg_turn_length": 0.0,
        "turn_count": 0,
        "markers": [],
    }
