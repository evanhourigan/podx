from typing import List, Literal, Optional, TypedDict


class EpisodeMeta(TypedDict, total=False):
    show: str
    feed: str
    episode_title: str
    episode_published: str
    audio_path: str
    image_url: str


class AudioMeta(TypedDict, total=False):
    audio_path: str
    sample_rate: int
    channels: int
    format: Literal["wav16", "mp3", "aac"]


class Segment(TypedDict):
    start: float
    end: float
    text: str


class Word(TypedDict, total=False):
    start: float
    end: float
    word: str


class AlignedSegment(Segment, total=False):
    words: List[Word]


class DiarizedSegment(AlignedSegment, total=False):
    speaker: str


class Transcript(TypedDict, total=False):
    audio_path: str
    language: str
    text: str
    segments: List[Segment]


class DeepcastQuote(TypedDict, total=False):
    quote: str
    time: str
    speaker: str


class DeepcastOutlineItem(TypedDict, total=False):
    label: str
    time: str


class DeepcastBrief(TypedDict, total=False):
    markdown: str
    summary: str
    key_points: List[str]
    gold_nuggets: List[str]
    quotes: List[DeepcastQuote]
    actions: List[str]
    outline: List[DeepcastOutlineItem]
    metadata: Transcript
