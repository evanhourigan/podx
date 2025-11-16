"""Audio quality analysis for optimal transcription settings.

Analyzes audio files to detect quality issues and recommend optimal
processing settings for transcription.
"""

from pathlib import Path
from typing import Any, Dict, List

import librosa
import numpy as np

from podx.logging import get_logger

logger = get_logger(__name__)


class AudioQualityAnalyzer:
    """Analyze audio quality and suggest optimal processing settings."""

    def analyze(self, audio_path: Path) -> Dict[str, Any]:
        """Analyze audio file and return quality metrics.

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with quality metrics and recommendations
        """
        logger.info(f"Analyzing audio quality: {audio_path}")

        # Load audio
        y, sr = librosa.load(audio_path, sr=None, mono=True)

        # Basic metrics
        duration = librosa.get_duration(y=y, sr=sr)

        # Quality metrics
        snr = self._calculate_snr(y)
        dynamic_range = self._calculate_dynamic_range(y)
        clipping_ratio = self._detect_clipping(y)
        silence_ratio = self._detect_silence(y, sr)

        # Content analysis
        speech_ratio = self._estimate_speech_ratio(y, sr)

        # Generate suggestions
        suggestions = self._generate_suggestions(
            snr, dynamic_range, clipping_ratio, silence_ratio, speech_ratio
        )

        # Recommend model
        recommended_model = self._recommend_model(snr, clipping_ratio)

        return {
            "audio_path": str(audio_path),
            "duration_seconds": duration,
            "sample_rate": sr,
            "quality": {
                "snr_db": round(snr, 2),
                "dynamic_range_db": round(dynamic_range, 2),
                "clipping_ratio": round(clipping_ratio, 4),
                "silence_ratio": round(silence_ratio, 4),
                "speech_ratio": round(speech_ratio, 4),
            },
            "recommendations": {
                "model": recommended_model,
                "vad_filter": silence_ratio > 0.15,  # Use VAD if >15% silence
                "suggestions": suggestions,
            },
        }

    def _calculate_snr(self, y: np.ndarray) -> float:
        """Calculate signal-to-noise ratio.

        Uses a combination of time-domain and frequency-domain analysis
        to estimate SNR. For clean synthetic signals, returns high SNR.
        For noisy signals, estimates noise from high-frequency content.

        Args:
            y: Audio signal

        Returns:
            SNR in dB
        """
        # Signal power (total energy)
        signal_power = np.mean(y**2)

        if signal_power < 1e-10:
            return 0.0

        # High-pass filter to isolate noise
        # Most speech/music content is below 8kHz, noise is often broadband
        from scipy import signal as scipy_signal

        # Design high-pass filter at 8 kHz (assuming 16 kHz sample rate)
        # This isolates high-frequency noise
        nyquist = 8000  # Assuming 16kHz sampling rate
        highpass_freq = 6000  # Hz
        b, a = scipy_signal.butter(4, highpass_freq / nyquist, btype="high")

        # Apply filter to get high-frequency content (mostly noise)
        y_highfreq = scipy_signal.filtfilt(b, a, y)
        noise_power = np.mean(y_highfreq**2)

        # For very clean signals (e.g., pure sine waves), high-freq content is minimal
        if noise_power < 1e-10:
            # Excellent quality - no noise detected
            return 40.0

        # Calculate SNR
        snr = 10 * np.log10(signal_power / noise_power)

        # Cap at 40 dB for excellent quality
        snr = min(snr, 40.0)

        return float(snr)

    def _calculate_dynamic_range(self, y: np.ndarray) -> float:
        """Calculate dynamic range in dB.

        Args:
            y: Audio signal

        Returns:
            Dynamic range in dB
        """
        y_abs = np.abs(y)
        peak = np.max(y_abs)
        rms = np.sqrt(np.mean(y**2))

        if rms < 1e-10:
            return 0.0

        dynamic_range = 20 * np.log10(peak / rms)
        return float(dynamic_range)

    def _detect_clipping(self, y: np.ndarray, threshold: float = 0.99) -> float:
        """Detect clipping (samples near max amplitude).

        Args:
            y: Audio signal
            threshold: Clipping threshold (default: 0.99)

        Returns:
            Ratio of clipped samples (0.0 to 1.0)
        """
        clipped = np.abs(y) > threshold
        clipping_ratio = np.sum(clipped) / len(y)
        return float(clipping_ratio)

    def _detect_silence(
        self, y: np.ndarray, sr: int, threshold_db: float = -40
    ) -> float:
        """Detect silence ratio.

        Args:
            y: Audio signal
            sr: Sample rate
            threshold_db: Silence threshold in dB

        Returns:
            Ratio of silent frames (0.0 to 1.0)
        """
        # RMS energy per frame
        frame_length = int(sr * 0.025)  # 25ms frames
        hop_length = int(sr * 0.010)  # 10ms hop

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[
            0
        ]
        rms_db = librosa.amplitude_to_db(rms, ref=np.max)

        silent_frames = rms_db < threshold_db
        silence_ratio = np.sum(silent_frames) / len(rms_db)

        return float(silence_ratio)

    def _estimate_speech_ratio(self, y: np.ndarray, sr: int) -> float:
        """Estimate ratio of speech vs music/noise.

        Args:
            y: Audio signal
            sr: Sample rate

        Returns:
            Estimated speech ratio (0.0 to 1.0)
        """
        # Use spectral features to distinguish speech
        # Speech typically has:
        # - Spectral centroid in 1-4 kHz range
        # - Higher zero-crossing rate
        # - Lower spectral rolloff

        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        zcr = librosa.feature.zero_crossing_rate(y)[0]

        # Simple heuristic: speech if centroid in 1-4 kHz and high ZCR
        speech_like = (spectral_centroids > 1000) & (spectral_centroids < 4000) & (zcr > 0.1)

        speech_ratio = np.sum(speech_like) / len(spectral_centroids)
        return float(speech_ratio)

    def _recommend_model(self, snr: float, clipping_ratio: float) -> str:
        """Recommend ASR model based on audio quality.

        Args:
            snr: Signal-to-noise ratio in dB
            clipping_ratio: Ratio of clipped samples

        Returns:
            Recommended model name
        """
        # Excellent quality: can use faster models
        if snr > 30 and clipping_ratio < 0.001:
            return "small"  # Fast and accurate enough

        # Good quality: medium model is optimal
        if snr > 20 and clipping_ratio < 0.01:
            return "medium"

        # Moderate quality: use larger model
        if snr > 15:
            return "large-v3"

        # Poor quality: use most robust model
        return "large-v3"

    def _generate_suggestions(
        self,
        snr: float,
        dynamic_range: float,
        clipping_ratio: float,
        silence_ratio: float,
        speech_ratio: float,
    ) -> List[Dict[str, str]]:
        """Generate suggestions based on quality metrics.

        Args:
            snr: Signal-to-noise ratio
            dynamic_range: Dynamic range
            clipping_ratio: Clipping ratio
            silence_ratio: Silence ratio
            speech_ratio: Speech content ratio

        Returns:
            List of suggestion dictionaries
        """
        suggestions = []

        # SNR-based suggestions
        if snr < 10:
            suggestions.append(
                {
                    "type": "warning",
                    "message": "Very low signal-to-noise ratio detected",
                    "recommendation": "Consider noise reduction preprocessing or use large-v3 model for better accuracy",
                }
            )
        elif snr < 20:
            suggestions.append(
                {
                    "type": "info",
                    "message": "Moderate background noise detected",
                    "recommendation": "Consider using medium or large model for better accuracy",
                }
            )

        # Clipping detection
        if clipping_ratio > 0.01:  # >1% clipped
            suggestions.append(
                {
                    "type": "warning",
                    "message": f"Audio clipping detected ({clipping_ratio*100:.1f}% of samples)",
                    "recommendation": "Audio may be distorted. Consider re-recording or using audio repair tools",
                }
            )

        # Silence detection
        if silence_ratio > 0.5:  # >50% silence
            suggestions.append(
                {
                    "type": "info",
                    "message": "Significant silence detected",
                    "recommendation": "Consider using --vad-filter to skip silent sections",
                }
            )

        # Speech content
        if speech_ratio < 0.3:  # <30% speech-like
            suggestions.append(
                {
                    "type": "warning",
                    "message": "Low speech content detected",
                    "recommendation": "Audio may contain mostly music or noise. Verify audio file or consider using specialized models",
                }
            )

        # Model recommendations based on overall quality
        if snr > 30 and clipping_ratio < 0.001:
            suggestions.append(
                {
                    "type": "success",
                    "message": "Excellent audio quality detected",
                    "recommendation": "small or medium model should provide good results",
                }
            )
        elif snr > 20:
            suggestions.append(
                {
                    "type": "success",
                    "message": "Good audio quality",
                    "recommendation": "medium model recommended for optimal accuracy/speed balance",
                }
            )
        else:
            suggestions.append(
                {
                    "type": "info",
                    "message": "Challenging audio quality",
                    "recommendation": "large-v3 model recommended for best accuracy",
                }
            )

        return suggestions
