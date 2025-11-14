"""Pipeline execution steps for podcast processing orchestration.

DEPRECATED: These functions are legacy wrappers for backward compatibility.
New code should use the focused step executors in podx.services.steps instead.

The step executors follow the Strategy pattern, enabling:
- Single Responsibility: Each step has one job
- Open/Closed: Easy to add new steps without modifying existing ones
- Testability: Each step can be tested in isolation
- Resumability: Steps can detect existing artifacts and skip execution
"""

from pathlib import Path
from typing import Optional

# Import new focused implementations
from podx.services.interactive import handle_interactive_mode
from podx.services.orchestration import (
    build_episode_metadata_display,
    display_pipeline_config,
    print_results_summary,
)
from podx.services.steps import (
    CleanupStep,
    DeepcastStep,
    EnhancementStep,
    ExportStep,
    FetchStep,
    NotionStep,
    StepContext,
    TranscribeStep,
)

# Re-export for backward compatibility
__all__ = [
    "execute_fetch",
    "execute_transcribe",
    "execute_enhancement",
    "execute_deepcast",
    "execute_notion_upload",
    "execute_cleanup",
    "execute_export_formats",
    "execute_export_final",
    "print_results_summary",
    "display_pipeline_config",
    "build_episode_metadata_display",
    "handle_interactive_mode",
]


def execute_fetch(
    config: dict,
    interactive_mode_meta: dict | None,
    interactive_mode_wd: Path | None,
    progress,
    verbose: bool,
) -> tuple[dict, Path]:
    """Execute fetch step (legacy wrapper).

    DEPRECATED: Use FetchStep directly for new code.
    """
    # Create step executor
    step = FetchStep(
        interactive_mode_meta=interactive_mode_meta,
        interactive_mode_wd=interactive_mode_wd,
    )

    # Create context
    context = StepContext(
        config=config,
        working_dir=config.get("workdir", Path(".")),
    )

    # Execute step
    result = step.execute(context, progress, verbose)

    if not result.success:
        from podx.errors import ValidationError
        raise ValidationError(result.error or "Fetch failed")

    return context.metadata, context.working_dir


def execute_transcribe(
    model: str,
    compute: str,
    asr_provider: str,
    audio: dict,
    wd: Path,
    progress,
    verbose: bool,
) -> tuple[dict, str]:
    """Execute transcription step (legacy wrapper).

    DEPRECATED: Use TranscribeStep directly for new code.
    """
    # Create step executor
    step = TranscribeStep(
        model=model,
        compute=compute,
        asr_provider=asr_provider,
    )

    # Create context
    context = StepContext(
        config={},
        working_dir=wd,
        audio_metadata=audio,
    )

    # Execute step
    result = step.execute(context, progress, verbose)

    if not result.success:
        raise RuntimeError(result.error or "Transcription failed")

    return context.latest_transcript, context.latest_transcript_name


def execute_enhancement(
    preprocess: bool,
    restore: bool,
    align: bool,
    diarize: bool,
    model: str,
    latest: dict,
    latest_name: str,
    wd: Path,
    progress,
    verbose: bool,
) -> tuple[dict, str]:
    """Execute transcript enhancement pipeline (legacy wrapper).

    DEPRECATED: Use EnhancementStep directly for new code.
    """
    # Note: align parameter is ignored in new implementation
    # (alignment is now internal to diarization)

    # Create step executor
    step = EnhancementStep(
        preprocess=preprocess,
        restore=restore,
        diarize=diarize,
        model=model,
    )

    # Create context
    context = StepContext(
        config={},
        working_dir=wd,
        latest_transcript=latest,
        latest_transcript_name=latest_name,
    )

    # Execute step
    result = step.execute(context, progress, verbose)

    if not result.success:
        raise RuntimeError(result.error or "Enhancement failed")

    return context.latest_transcript, context.latest_transcript_name


def execute_deepcast(
    deepcast: bool,
    model: str,
    deepcast_model: str,
    deepcast_temp: float,
    yaml_analysis_type: Optional[str],
    extract_markdown: bool,
    deepcast_pdf: bool,
    wd: Path,
    results: dict,
    progress,
    verbose: bool,
) -> None:
    """Execute deepcast analysis step (legacy wrapper).

    DEPRECATED: Use DeepcastStep directly for new code.
    """
    if not deepcast:
        return

    # Create step executor
    step = DeepcastStep(
        deepcast_model=deepcast_model,
        deepcast_temp=deepcast_temp,
        yaml_analysis_type=yaml_analysis_type,
        extract_markdown=extract_markdown,
        deepcast_pdf=deepcast_pdf,
    )

    # Create context
    context = StepContext(
        config={},
        working_dir=wd,
        results=results,
    )

    # Execute step
    result = step.execute(context, progress, verbose)

    if not result.success:
        raise RuntimeError(result.error or "Deepcast failed")

    # Update results dict (modified in place)
    results.update(context.results)


def execute_notion_upload(
    notion_db: str,
    wd: Path,
    results: dict,
    deepcast_model: str,
    model: str,
    podcast_prop: str,
    date_prop: str,
    episode_prop: str,
    model_prop: str,
    asr_prop: str,
    append_content: bool,
    progress,
    verbose: bool,
) -> None:
    """Execute Notion page creation/update (legacy wrapper).

    DEPRECATED: Use NotionStep directly for new code.
    """
    # Create step executor
    step = NotionStep(
        notion_db=notion_db,
        deepcast_model=deepcast_model,
        model=model,
        podcast_prop=podcast_prop,
        date_prop=date_prop,
        episode_prop=episode_prop,
        model_prop=model_prop,
        asr_prop=asr_prop,
        append_content=append_content,
    )

    # Create context
    context = StepContext(
        config={},
        working_dir=wd,
        results=results,
    )

    # Execute step
    result = step.execute(context, progress, verbose)

    if not result.success:
        raise RuntimeError(result.error or "Notion upload failed")

    # Update results dict (modified in place)
    results.update(context.results)


def execute_cleanup(
    clean: bool,
    no_keep_audio: bool,
    wd: Path,
    latest_name: str,
    transcoded_path: Path,
    original_audio_path: Path | None,
    progress,
) -> None:
    """Execute optional file cleanup (legacy wrapper).

    DEPRECATED: Use CleanupStep directly for new code.
    """
    # Create step executor
    step = CleanupStep(
        clean=clean,
        no_keep_audio=no_keep_audio,
    )

    # Create context
    context = StepContext(
        config={},
        working_dir=wd,
        latest_transcript_name=latest_name,
        transcoded_audio_path=transcoded_path,
        original_audio_path=original_audio_path,
    )

    # Execute step
    result = step.execute(context, progress, verbose=False)

    if not result.success:
        raise RuntimeError(result.error or "Cleanup failed")


def execute_export_formats(
    latest: dict,
    latest_name: str,
    wd: Path,
    progress,
    verbose: bool,
) -> dict:
    """Execute transcript export to TXT/SRT formats (legacy wrapper).

    DEPRECATED: Use ExportStep directly for new code.
    """
    # Create step executor
    step = ExportStep()

    # Create context
    context = StepContext(
        config={},
        working_dir=wd,
        latest_transcript=latest,
        latest_transcript_name=latest_name,
    )

    # Execute step
    result = step.execute(context, progress, verbose)

    if not result.success:
        raise RuntimeError(result.error or "Export failed")

    return context.results


def execute_export_final(
    preset: str | None,
    deepcast_pdf: bool,
    wd: Path,
    results: dict,
) -> None:
    """Execute final export of deepcast analysis (legacy wrapper).

    DEPRECATED: Use ExportStep directly for new code.
    """
    # Create step executor
    step = ExportStep(deepcast_pdf=deepcast_pdf, preset=preset)

    # Create context
    context = StepContext(
        config={},
        working_dir=wd,
        results=results,
    )

    # Execute final export only
    step._execute_final_export(context)

    # Update results dict (modified in place)
    results.update(context.results)
