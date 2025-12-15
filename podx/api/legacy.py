from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from ..errors import PodxError


def _run_cli(
    command: list[str],
    stdin_payload: Optional[Dict[str, Any]] = None,
    env_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Run a podx CLI command that prints JSON to stdout and return parsed JSON.
    Raises PodxError on failure with stderr/stdout included for diagnostics.
    """
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    proc = subprocess.run(
        command,
        input=json.dumps(stdin_payload) if stdin_payload is not None else None,
        text=True,
        capture_output=True,
        env=env,
    )

    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "podx command failed"
        raise PodxError(f"{command[0]} failed (exit {proc.returncode}): {message}")

    stdout = proc.stdout.strip()
    try:
        return json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        # Some commands may print non-JSON when not configured for JSON output
        return {"stdout": stdout}


def _download_to_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return dest


def _infer_filename_from_url(url: str) -> str:
    name = url.split("?")[0].rstrip("/").split("/")[-1] or "audio"
    if not re.search(r"\.(mp3|m4a|aac|wav|flac)$", name, re.IGNORECASE):
        name += ".mp3"
    return name


def transcribe(audio_url: str, asr_model: str, out_dir: str) -> Dict[str, Any]:
    """
    High-level transcription that ensures an audio file exists, runs transcode + transcribe,
    writes transcript.json in out_dir, and returns metadata including transcript_path.

    Returns: {
      "transcript_path": str,
      "duration_seconds": int,
    }
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Prepare local audio path (download if URL, or copy if local path)
    if re.match(r"^https?://", audio_url):
        local_audio = out_path / _infer_filename_from_url(audio_url)
        _download_to_file(audio_url, local_audio)
    else:
        src = Path(audio_url)
        if not src.exists():
            raise PodxError(f"Audio source not found: {audio_url}")
        local_audio = out_path / src.name
        if src.resolve() != local_audio.resolve():
            shutil.copy2(src, local_audio)

    # Transcode → AudioMeta JSON
    meta = {"audio_path": str(local_audio)}
    audio_meta = _run_cli(
        ["podx", "transcode", "--to", "wav16", "--outdir", str(out_path)],
        stdin_payload=meta,
    )

    # Transcribe → Transcript JSON (also write to file for consistency)
    transcript = _run_cli(["podx", "transcribe", "--model", asr_model], stdin_payload=audio_meta)
    transcript_path = out_path / "transcript.json"
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")

    # Best-effort duration: last segment end
    duration_seconds = 0
    try:
        segs = transcript.get("segments", [])
        if segs:
            duration_seconds = int(max(s.get("end", 0) for s in segs))
    except Exception:
        pass

    return {
        "transcript_path": str(transcript_path),
        "duration_seconds": duration_seconds,
    }


def analyze(
    transcript_path: str,
    llm_model: str,
    out_dir: str,
    provider_keys: Optional[Dict[str, str]] = None,
    prompt: Optional[str] = None,
    prompt_name: str = "default",
) -> Dict[str, Any]:
    """
    Run analysis for a given transcript JSON. Writes unified JSON and markdown.

    Note: the current CLI does not accept a free-form prompt; if provided, it is ignored
    until CLI support is added. The adapter sets provider API keys via environment.

    Returns: {
      "markdown_path": str,
      "usage": Optional[Dict[str, int]],
      "prompt_used": Optional[str],
    }
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    def _slugify(text: str) -> str:
        s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
        return s[:60] if len(s) > 60 else s

    def _slug_with_hash(name: str) -> str:
        import hashlib

        base = _slugify(name or "default")
        short = hashlib.sha1((name or "").encode("utf-8")).hexdigest()[:8]
        return f"{base}-{short}" if base else short

    model_suffix = re.sub(r"[^a-zA-Z0-9_]+", "_", llm_model)
    prompt_slug = _slug_with_hash(prompt_name)

    # Nested prompt-scoped layout: analysis/llm-<MODEL>/prompt-<PROMPT_SLUG>/analysis.*
    prompt_dir = out_path / "analysis" / f"llm-{model_suffix}" / f"prompt-{prompt_slug}"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    json_out = prompt_dir / "analysis.json"
    md_out = prompt_dir / "analysis.md"

    env = {}
    if provider_keys:
        for provider, key in provider_keys.items():
            if provider.lower() == "openai":
                env["OPENAI_API_KEY"] = key
            else:
                # Allow custom providers to be surfaced later if CLI supports them
                env[f"{provider.upper()}_API_KEY"] = key

    # Run CLI; always request markdown extraction so we have a file to point to
    _run_cli(
        [
            "podx",
            "analyze",
            "--input",
            str(transcript_path),
            "--output",
            str(json_out),
            "--model",
            llm_model,
            "--extract-markdown",
        ],
        env_overrides=env,
    )

    # Unified JSON contains the markdown and metadata; read for optional usage fields
    unified = {}
    try:
        unified = json.loads(json_out.read_text(encoding="utf-8"))
    except Exception:
        pass

    usage: Optional[Dict[str, int]] = None
    prompt_used: Optional[str] = None

    # Reserve keys for future when CLI outputs usage/prompt fields
    if isinstance(unified, dict):
        if "usage" in unified and isinstance(unified["usage"], dict):
            usage = {k: int(v) for k, v in unified["usage"].items() if isinstance(v, (int, float))}
        if "prompt_used" in unified and isinstance(unified["prompt_used"], str):
            prompt_used = unified["prompt_used"]

    # Write metadata.json alongside outputs for discovery/indexing
    try:
        metadata = {
            "llm_model": llm_model,
            "prompt_name": prompt_name,
            "prompt_text": prompt or None,
            "usage": usage or None,
            "prompt_used": prompt_used or None,
        }
        (prompt_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass

    return {
        "markdown_path": str(md_out),
        "usage": usage,
        "prompt_used": prompt_used,
    }


# Backwards compatibility alias
deepcast = analyze


def has_transcript(episode_id: int | str, asr_model: str, out_dir: str) -> Optional[str]:
    """
    Minimal check for an existing transcript in out_dir.
    This will evolve once a centralized outputs layout helper is available.
    """
    p = Path(out_dir) / "transcript.json"
    return str(p) if p.exists() else None


def has_markdown(
    episode_id: int | str,
    asr_model: str,
    llm_model: str,
    prompt_name: str,
    out_dir: str,
) -> Optional[str]:
    """
    Check for an existing deepcast markdown file scoped by model and prompt.
    Falls back to legacy root-level naming if not found.
    """
    out_path = Path(out_dir)
    model_suffix = re.sub(r"[^a-zA-Z0-9_]+", "_", llm_model)

    def _slugify(text: str) -> str:
        s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
        return s[:60] if len(s) > 60 else s

    def _slug_with_hash(name: str) -> str:
        import hashlib

        base = _slugify(name or "default")
        short = hashlib.sha1((name or "").encode("utf-8")).hexdigest()[:8]
        return f"{base}-{short}" if base else short

    prompt_slug = _slug_with_hash(prompt_name)

    # New layout check
    p = out_path / "analysis" / f"llm-{model_suffix}" / f"prompt-{prompt_slug}" / "analysis.md"
    if p.exists():
        return str(p)

    # Legacy layout check (deprecated)
    legacy_p = (
        out_path / "deepcast" / f"llm-{model_suffix}" / f"prompt-{prompt_slug}" / "analysis.md"
    )
    if legacy_p.exists():
        return str(legacy_p)

    # Legacy fallback - check for any analysis/deepcast markdown files
    analysis_files = list(out_path.glob("analysis-*.md"))
    if analysis_files:
        latest = max(analysis_files, key=lambda p: p.stat().st_mtime)
        return str(latest)

    # Legacy fallback - check for any deepcast markdown files (deprecated)
    deepcast_files = list(out_path.glob("deepcast-*.md"))
    if deepcast_files:
        # Return most recent one
        latest = max(deepcast_files, key=lambda p: p.stat().st_mtime)
        return str(latest)
    return None
