from typing import List, Literal, Optional, TypedDict


class EpisodeMeta(TypedDict, total=False):
    show: str
    feed: str
    episode_title: str
    episode_published: str
    audio_path: str


class AudioMeta(TypedDict, total=False):
    audio_path: str
    sample_rate: int
    channels: int
    format: Literal["wav16", "mp3", "aac"]


class Segment(TypedDict):
    start: float
    end: float
    text: str


class Transcript(TypedDict, total=False):
    audio_path: str
    language: str
    text: str
    segments: List[Segment]
