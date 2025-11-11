"""Step executor for running individual pipeline commands."""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import ValidationError
from ..logging import get_logger
from .command_builder import CommandBuilder

logger = get_logger(__name__)


class StepExecutor:
    """Executes individual pipeline steps via subprocess commands.

    This class encapsulates the logic for constructing and running CLI commands
    for each pipeline step (fetch, transcode, transcribe, align, diarize, etc.).

    Examples:
        >>> executor = StepExecutor(verbose=True)
        >>> result = executor.fetch(show="My Podcast", date="2024-10-01")
        >>> audio = executor.transcode(meta=result, fmt="wav16", outdir=Path("./output"))
    """

    def __init__(self, verbose: bool = False):
        """Initialize step executor.

        Args:
            verbose: Enable verbose output (shows JSON preview)
        """
        self.verbose = verbose

    def _run(
        self,
        cmd: List[str],
        stdin_payload: Optional[Dict[str, Any]] = None,
        save_to: Optional[Path] = None,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a CLI command that outputs JSON to stdout.

        Args:
            cmd: Command list (e.g., ["podx-fetch", "--show", "Podcast"])
            stdin_payload: Optional JSON payload to pass via stdin
            save_to: Optional path to save raw JSON output
            label: Optional label for logging

        Returns:
            Parsed JSON dictionary from command output

        Raises:
            ValidationError: If command fails or returns invalid JSON
        """
        if label:
            logger.debug("Running command", command=" ".join(cmd), label=label)

        proc = subprocess.run(
            cmd,
            input=json.dumps(stdin_payload) if stdin_payload else None,
            text=True,
            capture_output=True,
        )

        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            logger.error(
                "Command failed",
                command=" ".join(cmd),
                return_code=proc.returncode,
                error=err,
            )
            raise ValidationError(f"Command failed: {' '.join(cmd)}\n{err}")

        # Parse JSON output
        out = proc.stdout

        if self.verbose:
            # Show compact preview of JSON output
            preview = out[:400] + "..." if len(out) > 400 else out
            print(f"[JSON Output Preview]\n{preview}\n")

        try:
            data = json.loads(out)
            logger.debug("Command completed successfully", command=cmd[0])
        except json.JSONDecodeError:
            # Some commands (deepcast, notion) print plain text instead of JSON
            data = {"stdout": out.strip()}
            logger.debug("Command returned non-JSON output", command=cmd[0])

        if save_to:
            save_to.write_text(out, encoding="utf-8")
            logger.debug("Output saved", file=str(save_to))

        return data

    def _run_passthrough(self, cmd: List[str]) -> int:
        """Run a CLI command in passthrough mode (inherit stdio).

        Use this for interactive child processes so the user sees the UI.

        Args:
            cmd: Command list

        Returns:
            Command return code
        """
        proc = subprocess.run(cmd)
        return proc.returncode

    # ========== Pipeline Step Methods ==========

    def fetch(
        self,
        show: Optional[str] = None,
        rss_url: Optional[str] = None,
        youtube_url: Optional[str] = None,
        date: Optional[str] = None,
        title_contains: Optional[str] = None,
        save_to: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute fetch step to retrieve episode metadata.

        Args:
            show: Podcast show name (iTunes search)
            rss_url: Direct RSS feed URL
            youtube_url: YouTube video URL
            date: Episode date filter (YYYY-MM-DD)
            title_contains: Episode title substring filter
            save_to: Optional path to save output

        Returns:
            Episode metadata dictionary (EpisodeMeta schema)

        Raises:
            ValidationError: If no source specified or fetch fails
        """
        cmd = (
            CommandBuilder("podx-fetch")
            .add_option("--show", show)
            .add_option("--rss-url", rss_url)
            .add_option("--youtube-url", youtube_url)
            .add_option("--date", date)
            .add_option("--title-contains", title_contains)
            .build()
        )

        if len(cmd) == 1:  # Only base command, no options
            raise ValidationError("Must specify --show, --rss-url, or --youtube-url")

        return self._run(cmd, save_to=save_to, label="fetch")

    def transcode(
        self,
        meta: Dict[str, Any],
        fmt: str = "wav16",
        outdir: Optional[Path] = None,
        save_to: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute transcode step to convert audio format.

        Args:
            meta: Episode metadata (from fetch step)
            fmt: Target audio format (wav16/mp3/aac)
            outdir: Output directory path
            save_to: Optional path to save output

        Returns:
            Audio metadata dictionary (AudioMeta schema)
        """
        cmd = (
            CommandBuilder("podx-transcode")
            .add_option("--to", fmt)
            .add_option("--outdir", str(outdir) if outdir else None)
            .build()
        )

        return self._run(cmd, stdin_payload=meta, save_to=save_to, label="transcode")

    def transcribe(
        self,
        audio: Dict[str, Any],
        model: str = "base",
        compute: str = "int8",
        asr_provider: Optional[str] = None,
        preset: Optional[str] = None,
        save_to: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute transcribe step to generate transcript.

        Args:
            audio: Audio metadata (from transcode step)
            model: ASR model name (tiny/base/small/medium/large/large-v3)
            compute: Compute type (int8/float16/float32)
            asr_provider: ASR provider (auto/local/openai/hf)
            preset: ASR preset (balanced/precision/recall)
            save_to: Optional path to save output

        Returns:
            Transcript dictionary (Transcript schema)
        """
        cmd = (
            CommandBuilder("podx-transcribe")
            .add_option("--model", model)
            .add_option("--compute", compute)
            .add_option("--asr-provider", asr_provider)
            .add_option("--preset", preset)
            .build()
        )

        return self._run(cmd, stdin_payload=audio, save_to=save_to, label="transcribe")

    def align(
        self,
        transcript: Dict[str, Any],
        save_to: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute align step for word-level alignment.

        Args:
            transcript: Transcript data (from transcribe step)
            save_to: Optional path to save output

        Returns:
            Aligned transcript dictionary (AlignedTranscript schema)
        """
        cmd = CommandBuilder("podx-align").build()

        return self._run(cmd, stdin_payload=transcript, save_to=save_to, label="align")

    def diarize(
        self,
        transcript: Dict[str, Any],
        save_to: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute diarize step for speaker identification.

        Args:
            transcript: Transcript data (aligned or base)
            save_to: Optional path to save output

        Returns:
            Diarized transcript dictionary (DiarizedTranscript schema)
        """
        cmd = CommandBuilder("podx-diarize").build()

        return self._run(
            cmd, stdin_payload=transcript, save_to=save_to, label="diarize"
        )

    def preprocess(
        self,
        transcript: Dict[str, Any],
        restore: bool = False,
        save_to: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute preprocess step to clean transcript.

        Args:
            transcript: Transcript data
            restore: Enable semantic restore (LLM-based)
            save_to: Optional path to save output

        Returns:
            Preprocessed transcript dictionary
        """
        cmd = CommandBuilder("podx-preprocess")
        if restore:
            cmd.add_flag("--restore")

        return self._run(
            cmd.build(), stdin_payload=transcript, save_to=save_to, label="preprocess"
        )

    def deepcast(
        self,
        input_path: Path,
        output_path: Path,
        model: str = "gpt-4",
        temperature: float = 0.7,
        meta_path: Optional[Path] = None,
        analysis_type: Optional[str] = None,
        extract_markdown: bool = False,
        pdf: bool = False,
    ) -> Dict[str, Any]:
        """Execute deepcast step for AI analysis.

        Args:
            input_path: Path to transcript JSON
            output_path: Path to save deepcast JSON
            model: AI model name (gpt-4, claude-3-opus-20240229, etc.)
            temperature: LLM temperature (0.0-1.0)
            meta_path: Optional episode metadata path
            analysis_type: Analysis type (interview_guest_focused, panel_discussion, etc.)
            extract_markdown: Extract markdown from analysis
            pdf: Generate PDF output (requires pandoc)

        Returns:
            Deepcast analysis dictionary
        """
        cmd = (
            CommandBuilder("podx-deepcast")
            .add_option("--input", str(input_path))
            .add_option("--output", str(output_path))
            .add_option("--model", model)
            .add_option("--temperature", str(temperature))
            .add_option("--meta", str(meta_path) if meta_path else None)
            .add_option("--type", analysis_type)
        )

        if extract_markdown:
            cmd.add_flag("--extract-markdown")
        if pdf:
            cmd.add_flag("--pdf")

        return self._run(cmd.build(), save_to=None, label="deepcast")

    def export(
        self,
        transcript: Dict[str, Any],
        formats: str = "txt,srt",
        output_dir: Optional[Path] = None,
        input_path: Optional[Path] = None,
        replace: bool = False,
        save_to: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute export step to convert transcript to other formats.

        Args:
            transcript: Transcript data
            formats: Comma-separated export formats (txt,srt,vtt,md)
            output_dir: Output directory path
            input_path: Input file path (for naming)
            replace: Replace existing files
            save_to: Optional path to save export metadata

        Returns:
            Export metadata with file paths
        """
        cmd = (
            CommandBuilder("podx-export")
            .add_option("--formats", formats)
            .add_option("--output-dir", str(output_dir) if output_dir else None)
            .add_option("--input", str(input_path) if input_path else None)
        )

        if replace:
            cmd.add_flag("--replace")

        return self._run(
            cmd.build(), stdin_payload=transcript, save_to=save_to, label="export"
        )

    def notion(
        self,
        deepcast_path: Path,
        database_id: Optional[str] = None,
        podcast_prop: str = "Podcast",
        date_prop: str = "Date",
        episode_prop: str = "Episode",
        model_prop: str = "Model",
        asr_prop: str = "ASR",
        append_content: bool = False,
    ) -> Dict[str, Any]:
        """Execute notion step to upload to Notion.

        Args:
            deepcast_path: Path to deepcast markdown file
            database_id: Notion database ID
            podcast_prop: Notion property name for podcast
            date_prop: Notion property name for date
            episode_prop: Notion property name for episode
            model_prop: Notion property name for model
            asr_prop: Notion property name for ASR
            append_content: Append to existing page instead of replacing

        Returns:
            Notion upload result dictionary
        """
        cmd = (
            CommandBuilder("podx-notion")
            .add_option("--input", str(deepcast_path))
            .add_option("--database-id", database_id)
            .add_option("--podcast-prop", podcast_prop)
            .add_option("--date-prop", date_prop)
            .add_option("--episode-prop", episode_prop)
            .add_option("--model-prop", model_prop)
            .add_option("--asr-prop", asr_prop)
        )

        if append_content:
            cmd.add_flag("--append")

        return self._run(cmd.build(), save_to=None, label="notion")
