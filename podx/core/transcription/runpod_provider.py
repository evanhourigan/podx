"""RunPod cloud ASR provider.

Provides cloud-accelerated transcription via RunPod serverless GPUs,
with Cloudflare R2 storage for audio uploads and optional fallback
to local processing on failure.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ...cloud import CloudConfig, CloudError, CloudStorage, RunPodClient
from ...logging import get_logger
from .base import ASRProvider, ProviderConfig, TranscriptionError, TranscriptionResult
from .local_provider import LocalProvider

logger = get_logger(__name__)

# Model aliases for RunPod provider
# Maps user-friendly names to faster-whisper model names
RUNPOD_MODEL_ALIASES: Dict[str, str] = {
    "large-v3-turbo": "turbo",
    "turbo": "turbo",
    "large-v3": "large-v3",
    "large-v2": "large-v2",
    "large": "large-v3",
    "medium": "medium",
    "small": "small",
    "base": "base",
    "tiny": "tiny",
}


class RunPodProvider(ASRProvider):
    """ASR provider using RunPod serverless GPUs.

    Transcribes audio ~20-30x faster than local processing by offloading
    to cloud GPUs. Automatically falls back to local processing on failure
    (unless disabled).

    Features:
    - Cloud-accelerated faster-whisper models
    - Automatic retry with local fallback
    - Progress callbacks for status updates
    - Support for all Whisper model sizes

    Environment Variables:
        RUNPOD_API_KEY: Required API key
        RUNPOD_ENDPOINT_ID: Required endpoint ID
    """

    def __init__(
        self,
        config: ProviderConfig,
        cloud_config: Optional[CloudConfig] = None,
        enable_fallback: Optional[bool] = None,
    ):
        """Initialize RunPod provider.

        Args:
            config: Provider configuration with model and options
            cloud_config: Optional cloud config (defaults to from_env)
            enable_fallback: Override fallback setting from cloud config
        """
        super().__init__(config)

        # Load cloud config from environment if not provided
        self.cloud_config = cloud_config or CloudConfig.from_env()

        # Override fallback if specified
        if enable_fallback is not None:
            self.cloud_config.enable_fallback = enable_fallback

        # Validate configuration (raises CloudError if missing)
        self.cloud_config.validate()

        # Create RunPod client and R2 storage
        self.client = RunPodClient(self.cloud_config)
        self.storage = CloudStorage(self.cloud_config)

        # Lazy-init fallback provider
        self._fallback_provider: Optional[LocalProvider] = None

        # Normalize model identifier
        self.normalized_model = self.normalize_model(self.config.model)

    @property
    def name(self) -> str:
        """Get provider name."""
        return "runpod"

    @property
    def supported_models(self) -> List[str]:
        """Get list of supported model identifiers."""
        return list(RUNPOD_MODEL_ALIASES.keys())

    @property
    def fallback_provider(self) -> Optional[LocalProvider]:
        """Get fallback provider, creating if needed."""
        if not self.cloud_config.enable_fallback:
            return None
        if self._fallback_provider is None:
            # Create local provider with same config but local-compatible model
            local_model = self._get_local_model_equivalent()
            local_config = ProviderConfig(
                model=local_model,
                device=self.config.device,
                compute_type=self.config.compute_type,
                language=self.config.language,
                vad_filter=self.config.vad_filter,
                condition_on_previous_text=self.config.condition_on_previous_text,
                progress_callback=self.config.progress_callback,
                extra_options=self.config.extra_options,
            )
            self._fallback_provider = LocalProvider(local_config)
        return self._fallback_provider

    def normalize_model(self, model: str) -> str:
        """Normalize model identifier to faster-whisper format."""
        return RUNPOD_MODEL_ALIASES.get(model, model)

    def _get_local_model_equivalent(self) -> str:
        """Get local model name for fallback."""
        # Map to the same model for local
        return self.normalized_model

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """Transcribe audio using RunPod cloud GPU.

        Uploads audio to RunPod, starts transcription job, polls for
        completion, and returns results. Falls back to local processing
        on failure if enabled.

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptionResult with transcript data

        Raises:
            TranscriptionError: If transcription fails and no fallback
            FileNotFoundError: If audio file doesn't exist
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(
            "Starting RunPod cloud transcription",
            model=self.normalized_model,
            audio=str(audio_path),
            fallback_enabled=self.cloud_config.enable_fallback,
        )

        try:
            return self._transcribe_cloud(audio_path)
        except CloudError as e:
            return self._handle_cloud_error(e, audio_path)
        except Exception as e:
            logger.error("Unexpected error during cloud transcription", error=str(e))
            if self.fallback_provider:
                self._report_progress(f"Cloud error: {e}. Falling back to local...")
                return self.fallback_provider.transcribe(audio_path)
            raise TranscriptionError(f"Cloud transcription failed: {e}") from e

    def _transcribe_cloud(self, audio_path: Path) -> TranscriptionResult:
        """Perform cloud transcription via R2 upload."""
        r2_key: Optional[str] = None

        try:
            # Step 1: Upload audio to R2
            self._report_progress("Uploading audio to R2...")
            audio_url, r2_key = self.storage.upload_and_presign(audio_path)

            # Step 2: Submit job with presigned URL
            self._report_progress("Submitting transcription job...")
            job_id = self.client.submit_job(
                audio_url=audio_url,
                model=self.normalized_model,
                language=self.config.language if self.config.language != "en" else "auto",
            )

            # Step 3: Wait for completion
            self._report_progress("Transcribing on cloud GPU...")
            result = self.client.wait_for_completion(
                job_id=job_id,
                progress_callback=self._report_progress,
            )

            # Convert result to TranscriptionResult
            return self._convert_result(result, audio_path)

        finally:
            # Always clean up R2 upload
            if r2_key:
                self.storage.delete(r2_key)

    def _convert_result(
        self, cloud_result: Dict[str, Any], audio_path: Path
    ) -> TranscriptionResult:
        """Convert RunPod result to TranscriptionResult.

        Args:
            cloud_result: Raw result from RunPod API
            audio_path: Original audio path

        Returns:
            TranscriptionResult in standard format
        """
        # Extract segments from result
        segments_raw = cloud_result.get("segments", [])
        segments: List[Dict[str, Any]] = []
        text_lines: List[str] = []

        for seg in segments_raw:
            segment = {
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", "").strip(),
            }
            segments.append(segment)
            if segment["text"]:
                text_lines.append(segment["text"])

        # Get detected language
        language = cloud_result.get("language", self.config.language)

        logger.info(
            "RunPod transcription completed",
            segments_count=len(segments),
            language=language,
        )

        self._report_progress(f"Transcription complete ({len(segments)} segments)")

        return TranscriptionResult(
            audio_path=str(audio_path.resolve()),
            language=language,
            asr_model=self.normalized_model,
            asr_provider=self.name,
            segments=segments,
            text="\n".join(text_lines).strip(),
            decoder_options={"vad_filter": self.config.vad_filter},
        )

    def _handle_cloud_error(self, error: CloudError, audio_path: Path) -> TranscriptionResult:
        """Handle cloud error with optional fallback.

        Args:
            error: The cloud error that occurred
            audio_path: Audio file for fallback transcription

        Returns:
            TranscriptionResult from fallback if enabled

        Raises:
            TranscriptionError: If no fallback and error is not recoverable
        """
        logger.warning(
            "Cloud transcription failed",
            error=str(error),
            recoverable=error.recoverable,
            fallback_enabled=self.cloud_config.enable_fallback,
        )

        if error.recoverable and self.fallback_provider:
            self._report_progress(f"Cloud failed: {error}. Falling back to local...")
            return self.fallback_provider.transcribe(audio_path)

        raise TranscriptionError(str(error)) from error

    def close(self) -> None:
        """Close the RunPod client."""
        self.client.close()

    def __enter__(self) -> "RunPodProvider":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
