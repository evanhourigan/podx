"""Export step executor for transcript format conversion."""

import json
import time
from pathlib import Path
from typing import Any, Optional

from podx.cli.services.command_runner import run_command
from podx.constants import DEFAULT_ENCODING
from podx.services.command_builder import CommandBuilder

from .base import PipelineStep, StepContext, StepResult


class ExportStep(PipelineStep):
    """Execute transcript export to TXT/SRT formats and optional final markdown/PDF.

    Handles both intermediate export (TXT/SRT) and final export (timestamped markdown/PDF).
    """

    def __init__(self, deepcast_pdf: bool = False, preset: Optional[str] = None):
        """Initialize export step.

        Args:
            deepcast_pdf: Generate PDF from deepcast output
            preset: ASR preset used (for track naming in final export)
        """
        self.deepcast_pdf = deepcast_pdf
        self.preset = preset

    @property
    def name(self) -> str:
        return "Export Transcript Files"

    def execute(
        self, context: StepContext, progress: Any, verbose: bool = False
    ) -> StepResult:
        """Execute export step."""
        step_start = time.time()

        # Export to TXT/SRT formats
        progress.start_step("Exporting transcript files")

        wd = context.working_dir
        latest_name = context.latest_transcript_name

        export_cmd = (
            CommandBuilder("podx-export")
            .add_option("--formats", "txt,srt")
            .add_option("--output-dir", str(wd))
            .add_option("--input", str(wd / f"{latest_name}.json"))
            .add_flag("--replace")
        )
        export_result = run_command(
            export_cmd.build(),
            stdin_payload=context.latest_transcript,
            verbose=verbose,
            label=None,
        )

        step_duration = time.time() - step_start
        progress.complete_step("Transcript files exported (TXT, SRT)", step_duration)

        # Build results using export output paths when available
        exported_files = (
            export_result.get("files", {}) if isinstance(export_result, dict) else {}
        )
        results = {
            "meta": str(wd / "episode-meta.json"),
            "audio": str(wd / "audio-meta.json"),
            "transcript": str(wd / f"{latest_name}.json"),
            "latest_json": str(wd / "latest.json"),
        }
        if "txt" in exported_files:
            results["latest_txt"] = exported_files["txt"]
        else:
            results["latest_txt"] = str(wd / f"{latest_name}.txt")
        if "srt" in exported_files:
            results["latest_srt"] = exported_files["srt"]
        else:
            results["latest_srt"] = str(wd / f"{latest_name}.srt")

        # Update context results
        context.results.update(results)

        # Final export (deepcast markdown/PDF)
        self._execute_final_export(context)

        return StepResult.ok(
            "Transcript files exported", duration=step_duration, data=results
        )

    def _execute_final_export(self, context: StepContext) -> None:
        """Execute final export of deepcast analysis to markdown/PDF."""
        from podx.cli.services.export import export_from_deepcast_json

        wd = context.working_dir

        try:
            single = context.results.get("deepcast_json")
            if single and Path(single).exists():
                export_source_path = Path(single)
                export_track = (self.preset or "balanced") if self.preset else "single"

                data = json.loads(
                    export_source_path.read_text(encoding=DEFAULT_ENCODING)
                )
                # Use unified exporter (handles deepcast JSON, and PDF auto-install)
                try:
                    md_path, pdf_path = export_from_deepcast_json(
                        data, wd, self.deepcast_pdf, track_hint=export_track
                    )
                    context.results["exported_md"] = str(md_path)
                    if pdf_path is not None:
                        context.results["exported_pdf"] = str(pdf_path)
                except Exception:
                    pass
        except Exception:
            pass
