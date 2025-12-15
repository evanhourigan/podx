#!/usr/bin/env python3
"""Tests for audio quality analysis."""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from podx.core.audio_quality import AudioQualityAnalyzer

# Skip file-based tests on Windows due to slow audio I/O
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Audio file tests timeout on Windows CI",
)


class TestAudioQualityAnalyzer:
    """Test audio quality analyzer."""

    def test_analyze_clean_audio(self):
        """Test analyzing clean audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = Path(tmpdir) / "clean.wav"

            # Generate clean audio (sine wave)
            sr = 16000
            duration = 2.0
            t = np.linspace(0, duration, int(sr * duration))
            y = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave

            sf.write(audio_file, y, sr)

            # Analyze
            analyzer = AudioQualityAnalyzer()
            analysis = analyzer.analyze(audio_file)

            # Check structure
            assert "audio_path" in analysis
            assert "duration_seconds" in analysis
            assert "sample_rate" in analysis
            assert "quality" in analysis
            assert "recommendations" in analysis

            # Check quality metrics
            quality = analysis["quality"]
            assert "snr_db" in quality
            assert "dynamic_range_db" in quality
            assert "clipping_ratio" in quality
            assert "silence_ratio" in quality
            assert "speech_ratio" in quality

            # Clean audio should have good SNR
            assert quality["snr_db"] > 20

            # Minimal clipping
            assert quality["clipping_ratio"] < 0.01

    def test_analyze_noisy_audio(self):
        """Test analyzing noisy audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = Path(tmpdir) / "noisy.wav"

            # Generate noisy audio
            sr = 16000
            duration = 2.0
            t = np.linspace(0, duration, int(sr * duration))
            signal = 0.5 * np.sin(2 * np.pi * 440 * t)
            noise = 0.3 * np.random.randn(len(signal))  # Add noise
            y = signal + noise

            sf.write(audio_file, y, sr)

            # Analyze
            analyzer = AudioQualityAnalyzer()
            analysis = analyzer.analyze(audio_file)

            # Noisy audio should have lower SNR
            quality = analysis["quality"]
            assert quality["snr_db"] < 30  # Not excellent

    def test_analyze_clipped_audio(self):
        """Test analyzing clipped audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = Path(tmpdir) / "clipped.wav"

            # Generate clipped audio
            sr = 16000
            duration = 2.0
            t = np.linspace(0, duration, int(sr * duration))
            y = 1.5 * np.sin(2 * np.pi * 440 * t)  # Exceeds [-1, 1]
            y = np.clip(y, -1.0, 1.0)  # Clip to valid range

            sf.write(audio_file, y, sr)

            # Analyze
            analyzer = AudioQualityAnalyzer()
            analysis = analyzer.analyze(audio_file)

            # Should detect clipping
            quality = analysis["quality"]
            assert quality["clipping_ratio"] > 0.01  # Significant clipping

    def test_analyze_silent_audio(self):
        """Test analyzing audio with silence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = Path(tmpdir) / "silent.wav"

            # Generate audio with silence
            sr = 16000
            duration = 4.0
            samples = int(sr * duration)

            # First half: signal, second half: silence
            signal = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, duration / 2, samples // 2))
            silence = np.zeros(samples // 2)
            y = np.concatenate([signal, silence])

            sf.write(audio_file, y, sr)

            # Analyze
            analyzer = AudioQualityAnalyzer()
            analysis = analyzer.analyze(audio_file)

            # Should detect significant silence
            quality = analysis["quality"]
            assert quality["silence_ratio"] > 0.3  # >30% silence

            # Should recommend VAD
            recommendations = analysis["recommendations"]
            assert recommendations["vad_filter"] is True

    def test_recommend_model_excellent_quality(self):
        """Test model recommendation for excellent quality."""
        analyzer = AudioQualityAnalyzer()

        # Excellent quality (high SNR, no clipping)
        model = analyzer._recommend_model(snr=35.0, clipping_ratio=0.0001)
        assert model in ["small", "medium"]  # Can use faster models

    def test_recommend_model_good_quality(self):
        """Test model recommendation for good quality."""
        analyzer = AudioQualityAnalyzer()

        # Good quality
        model = analyzer._recommend_model(snr=25.0, clipping_ratio=0.005)
        assert model == "medium"

    def test_recommend_model_poor_quality(self):
        """Test model recommendation for poor quality."""
        analyzer = AudioQualityAnalyzer()

        # Poor quality (low SNR)
        model = analyzer._recommend_model(snr=12.0, clipping_ratio=0.005)
        assert model == "large-v3"

    def test_recommendations_include_suggestions(self):
        """Test that recommendations include suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_file = Path(tmpdir) / "test.wav"

            # Generate test audio
            sr = 16000
            duration = 2.0
            t = np.linspace(0, duration, int(sr * duration))
            y = 0.5 * np.sin(2 * np.pi * 440 * t)

            sf.write(audio_file, y, sr)

            # Analyze
            analyzer = AudioQualityAnalyzer()
            analysis = analyzer.analyze(audio_file)

            # Should have suggestions
            recommendations = analysis["recommendations"]
            assert "suggestions" in recommendations
            assert isinstance(recommendations["suggestions"], list)
            assert len(recommendations["suggestions"]) > 0

            # Each suggestion should have required fields
            for suggestion in recommendations["suggestions"]:
                assert "type" in suggestion
                assert "message" in suggestion
                assert "recommendation" in suggestion

    def test_calculate_snr(self):
        """Test SNR calculation."""
        analyzer = AudioQualityAnalyzer()

        # Clean signal (high SNR)
        clean_signal = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000))
        snr_clean = analyzer._calculate_snr(clean_signal)
        assert snr_clean > 25

        # Noisy signal (lower SNR)
        noise = 0.3 * np.random.randn(16000)
        noisy_signal = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000)) + noise
        snr_noisy = analyzer._calculate_snr(noisy_signal)
        assert snr_noisy < snr_clean

    def test_calculate_dynamic_range(self):
        """Test dynamic range calculation."""
        analyzer = AudioQualityAnalyzer()

        # High dynamic range signal (peak vs RMS)
        signal = np.concatenate(
            [
                0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 8000)),  # Quiet
                0.9 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 8000)),  # Loud
            ]
        )
        dr = analyzer._calculate_dynamic_range(signal)
        assert dr > 5  # Should have reasonable dynamic range

    def test_detect_clipping(self):
        """Test clipping detection."""
        analyzer = AudioQualityAnalyzer()

        # No clipping
        clean = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000))
        clipping_clean = analyzer._detect_clipping(clean)
        assert clipping_clean < 0.001

        # With clipping
        clipped = np.clip(1.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000)), -1.0, 1.0)
        clipping_clipped = analyzer._detect_clipping(clipped)
        assert clipping_clipped > 0.01

    def test_detect_silence(self):
        """Test silence detection."""
        analyzer = AudioQualityAnalyzer()
        sr = 16000

        # Mostly silence
        mostly_silent = np.concatenate(
            [
                0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2))),
                np.zeros(int(sr * 0.8)),
            ]
        )
        silence_ratio = analyzer._detect_silence(mostly_silent, sr)
        assert silence_ratio > 0.5

        # Mostly signal
        mostly_signal = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, sr))
        silence_ratio_low = analyzer._detect_silence(mostly_signal, sr)
        assert silence_ratio_low < 0.3

    def test_generate_suggestions_excellent_quality(self):
        """Test suggestion generation for excellent quality."""
        analyzer = AudioQualityAnalyzer()

        suggestions = analyzer._generate_suggestions(
            snr=35.0,
            dynamic_range=20.0,
            clipping_ratio=0.0001,
            silence_ratio=0.05,
            speech_ratio=0.8,
        )

        # Should have positive suggestions
        assert len(suggestions) > 0
        assert any(s["type"] == "success" for s in suggestions)

    def test_generate_suggestions_poor_quality(self):
        """Test suggestion generation for poor quality."""
        analyzer = AudioQualityAnalyzer()

        suggestions = analyzer._generate_suggestions(
            snr=8.0,  # Very low SNR
            dynamic_range=5.0,
            clipping_ratio=0.05,  # High clipping
            silence_ratio=0.6,  # High silence
            speech_ratio=0.2,  # Low speech
        )

        # Should have warnings
        assert len(suggestions) > 0
        assert any(s["type"] == "warning" for s in suggestions)


class TestSuggestionGeneration:
    """Test suggestion generation logic."""

    def test_low_snr_suggestion(self):
        """Test suggestion for low SNR."""
        analyzer = AudioQualityAnalyzer()

        suggestions = analyzer._generate_suggestions(
            snr=8.0,
            dynamic_range=10.0,
            clipping_ratio=0.001,
            silence_ratio=0.1,
            speech_ratio=0.7,
        )

        # Should warn about low SNR
        assert any("signal-to-noise" in s["message"].lower() for s in suggestions)

    def test_clipping_suggestion(self):
        """Test suggestion for clipping."""
        analyzer = AudioQualityAnalyzer()

        suggestions = analyzer._generate_suggestions(
            snr=25.0,
            dynamic_range=15.0,
            clipping_ratio=0.05,  # High clipping
            silence_ratio=0.1,
            speech_ratio=0.7,
        )

        # Should warn about clipping
        assert any("clipping" in s["message"].lower() for s in suggestions)

    def test_silence_suggestion(self):
        """Test suggestion for high silence."""
        analyzer = AudioQualityAnalyzer()

        suggestions = analyzer._generate_suggestions(
            snr=25.0,
            dynamic_range=15.0,
            clipping_ratio=0.001,
            silence_ratio=0.6,  # High silence
            speech_ratio=0.7,
        )

        # Should suggest VAD
        assert any("silence" in s["message"].lower() for s in suggestions)

    def test_low_speech_suggestion(self):
        """Test suggestion for low speech content."""
        analyzer = AudioQualityAnalyzer()

        suggestions = analyzer._generate_suggestions(
            snr=25.0,
            dynamic_range=15.0,
            clipping_ratio=0.001,
            silence_ratio=0.1,
            speech_ratio=0.2,  # Low speech
        )

        # Should warn about low speech
        assert any("speech" in s["message"].lower() for s in suggestions)
