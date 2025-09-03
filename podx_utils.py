import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import feedparser
import requests
from dateutil import parser as dtparse

USER_AGENT = "podx/1.0 (+mac cli)"


def http_get(url, **kw):
    headers = kw.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)
    r = requests.get(url, headers=headers, timeout=kw.pop("timeout", 30))
    r.raise_for_status()
    return r


def sanitize_filename(s: str) -> str:
    s = re.sub(r"[^\w\-.]+", "_", s.strip())
    return re.sub(r"_{2,}", "_", s)


# --------------------------
# Discover podcast feed (iTunes Search API → RSS feed)
# --------------------------
def find_feed_for_show(show_name: str) -> str:
    q = {"media": "podcast", "term": show_name}
    url = "https://itunes.apple.com/search?" + urlencode(q)
    data = http_get(url).json()
    if not data.get("results"):
        raise SystemExit(f"No podcasts found matching: {show_name}")
    # pick top result (simple & usually right). You can add smarter scoring later.
    feed_url = data["results"][0].get("feedUrl")
    if not feed_url:
        raise SystemExit("Found podcast but no feedUrl in iTunes result.")
    return feed_url


def parse_rss(feed_url: str):
    f = feedparser.parse(feed_url)
    if f.bozo:
        raise SystemExit(f"Failed to parse feed: {feed_url}")
    return f


def _entry_pubdate(entry):
    # feedparser normalizes published / updated; fallbacks if missing
    for key in ("published", "updated", "pubDate"):
        if key in entry:
            try:
                return dtparse.parse(entry[key])
            except Exception:
                pass
    # try parsed tuple
    for key in ("published_parsed", "updated_parsed"):
        if key in entry and entry[key]:
            return datetime(*entry[key][:6], tzinfo=timezone.utc)
    return None


def choose_episode(entries, date_str=None, title_contains=None):
    if title_contains:
        cand = [
            e for e in entries if title_contains.lower() in (e.get("title", "").lower())
        ]
        if cand:
            return cand[0]
    if date_str:
        want = dtparse.parse(date_str)
        best = None
        best_delta = None
        for e in entries:
            d = _entry_pubdate(e)
            if not d:
                continue
            delta = abs((d - want).total_seconds())
            if best is None or delta < best_delta:
                best, best_delta = e, delta
        if best:
            return best
    # default to most recent
    return entries[0] if entries else None


def download_enclosure(entry, out_dir: Path) -> Path:
    # find audio enclosure
    links = entry.get("links", []) or []
    audio = None
    for ln in links:
        if ln.get("rel") == "enclosure" and "audio" in ln.get("type", ""):
            audio = ln.get("href")
            break
    if not audio:
        # try content:encoded or link
        audio = entry.get("link")
    if not audio:
        raise SystemExit("No audio enclosure found in this episode.")

    title = entry.get("title", "episode")
    fname = sanitize_filename(title) + Path(audio).suffix
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / fname

    with requests.get(audio, stream=True, headers={"User-Agent": USER_AGENT}) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
    return out_path


# --------------------------
# ffmpeg helpers
# --------------------------
def ffmpeg(cmd: list):
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error"] + cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip())
    return proc


def to_wav_16k_mono(src: Path, dst: Path) -> Path:
    dst = dst.with_suffix(".wav")
    ffmpeg(["-y", "-i", str(src), "-ac", "1", "-ar", "16000", "-vn", str(dst)])
    return dst


def to_best_mp3(src: Path, dst: Path, bitrate="128k") -> Path:
    dst = dst.with_suffix(".mp3")
    ffmpeg(["-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", bitrate, str(dst)])
    return dst


def to_aac(src: Path, dst: Path, bitrate="96k") -> Path:
    dst = dst.with_suffix(".m4a")
    ffmpeg(["-y", "-i", str(src), "-c:a", "aac", "-b:a", bitrate, str(dst)])
    return dst


# --------------------------
# IO helpers
# --------------------------
def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
