"""Pipeline configuration building from CLI arguments.

Transforms Click command-line arguments into structured configuration
dictionaries for pipeline execution, applying presets and defaults.
"""

from pathlib import Path
from typing import Any, Dict, Optional


def build_pipeline_config(
    show: Optional[str],
    rss_url: Optional[str],
    youtube_url: Optional[str],
    date: Optional[str],
    title_contains: Optional[str],
    workdir: Optional[Path],
    fmt: str,
    model: str,
    compute: str,
    asr_provider: str,
    preprocess: bool,
    restore: bool,
    diarize: bool,
    deepcast: bool,
    deepcast_model: str,
    deepcast_temp: float,
    extract_markdown: bool,
    deepcast_pdf: bool,
    notion: bool,
    notion_db: Optional[str],
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    model_prop: str,
    asr_prop: str,
    append_content: bool,
    full: bool,
    verbose: bool,
    clean: bool,
    no_keep_audio: bool,
) -> Dict[str, Any]:
    """Build pipeline configuration from CLI arguments.

    Applies preset transformations (--full) to CLI flags
    and returns a configuration dictionary ready for pipeline execution.

    Args:
        show: Podcast show name (iTunes search)
        rss_url: Direct RSS feed URL
        youtube_url: YouTube video URL
        date: Episode date filter (YYYY-MM-DD)
        title_contains: Substring to match in episode title
        workdir: Working directory path
        fmt: Audio format (wav16/mp3/aac)
        model: ASR model name
        compute: ASR compute type
        asr_provider: ASR provider (auto/local/openai/hf)
        preprocess: Enable transcript preprocessing
        restore: Enable semantic restore
        diarize: Enable speaker diarization
        deepcast: Enable AI analysis
        deepcast_model: AI model for deepcast
        deepcast_temp: Temperature for deepcast LLM calls
        extract_markdown: Extract markdown from deepcast
        deepcast_pdf: Generate PDF from deepcast
        notion: Upload to Notion
        notion_db: Notion database ID
        podcast_prop: Notion property for podcast name
        date_prop: Notion property for date
        episode_prop: Notion property for episode title
        model_prop: Notion property for AI model
        asr_prop: Notion property for ASR model
        append_content: Append to Notion page instead of replacing
        full: Convenience flag (enables deepcast + markdown + notion)
        verbose: Enable verbose logging
        clean: Clean intermediate files after completion
        no_keep_audio: Don't keep audio files after transcription

    Returns:
        Configuration dictionary with processed flags
    """
    # Start with all arguments in a dict (will be modified by presets)
    config = {
        "show": show,
        "rss_url": rss_url,
        "youtube_url": youtube_url,
        "date": date,
        "title_contains": title_contains,
        "workdir": workdir,
        "fmt": fmt,
        "model": model,
        "compute": compute,
        "asr_provider": asr_provider,
        "preprocess": preprocess,
        "restore": restore,
        "diarize": diarize,
        "deepcast": deepcast,
        "deepcast_model": deepcast_model,
        "deepcast_temp": deepcast_temp,
        "extract_markdown": extract_markdown,
        "deepcast_pdf": deepcast_pdf,
        "notion": notion,
        "notion_db": notion_db,
        "podcast_prop": podcast_prop,
        "date_prop": date_prop,
        "episode_prop": episode_prop,
        "model_prop": model_prop,
        "asr_prop": asr_prop,
        "append_content": append_content,
        "verbose": verbose,
        "clean": clean,
        "no_keep_audio": no_keep_audio,
        "yaml_analysis_type": None,  # Will be set by interactive mode or workflow
    }

    # Handle convenience --full flag
    if full:
        config["deepcast"] = True
        config["extract_markdown"] = True
        config["notion"] = True

    return config
