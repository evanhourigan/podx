from podx.schemas import Segment, Transcript


def test_segment_typing():
    seg: Segment = {"start": 0.0, "end": 1.0, "text": "hi"}
    assert seg["end"] >= seg["start"]
