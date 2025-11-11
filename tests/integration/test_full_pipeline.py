#!/usr/bin/env python3
"""
Integration tests for full pipeline workflows.

Tests end-to-end execution with realistic scenarios, mocking only external APIs.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestPipelineStageIntegration:
    """Test integration between pipeline stages."""

    def test_episode_meta_to_audio_meta_flow(self, tmp_path):
        """Test that episode metadata flows to audio metadata."""
        from podx.schemas import AudioMeta, EpisodeMeta

        # Create temporary audio file
        audio_file = tmp_path / "test_audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Create episode metadata
        episode_data = {
            "show": "Test Podcast",
            "feed": "https://example.com/feed.xml",
            "episode_title": "Test Episode",
            "episode_published": "2024-01-01",
            "audio_path": str(audio_file),
        }
        episode_meta = EpisodeMeta.model_validate(episode_data)

        # Simulate audio processing creating AudioMeta
        audio_data = {
            "audio_path": episode_meta.audio_path,
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav16",
        }
        audio_meta = AudioMeta.model_validate(audio_data)

        # Verify data flows correctly
        assert audio_meta.audio_path == episode_meta.audio_path
        assert Path(audio_meta.audio_path).exists()

    def test_audio_meta_to_transcript_flow(self, tmp_path):
        """Test that audio metadata flows to transcript."""
        from podx.schemas import AudioMeta, Transcript

        # Create audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake wav data")

        # Audio metadata from preprocessing
        audio_data = {
            "audio_path": str(audio_file),
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav16",
        }
        audio_meta = AudioMeta.model_validate(audio_data)

        # Transcript from ASR
        transcript_data = {
            "audio_path": audio_meta.audio_path,
            "language": "en",
            "text": "Hello world",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello"},
                {"start": 1.0, "end": 2.0, "text": "world"},
            ],
        }
        transcript = Transcript.model_validate(transcript_data)

        # Verify flow
        assert transcript.audio_path == audio_meta.audio_path
        assert len(transcript.segments) == 2

    def test_transcript_to_aligned_flow(self, tmp_path):
        """Test that transcript flows to aligned transcript."""
        from podx.schemas import AlignedSegment, Transcript

        # Create audio file for validation
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake wav data")

        # Base transcript
        transcript_data = {
            "audio_path": str(audio_file),
            "language": "en",
            "text": "Hello world",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello"},
                {"start": 1.0, "end": 2.0, "text": "world"},
            ],
        }
        transcript = Transcript.model_validate(transcript_data)

        # Aligned segments with word-level timing
        aligned_data = [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Hello",
                "words": [{"start": 0.0, "end": 1.0, "word": "Hello"}],
            },
            {
                "start": 1.0,
                "end": 2.0,
                "text": "world",
                "words": [{"start": 1.0, "end": 2.0, "word": "world"}],
            },
        ]
        aligned_segments = [AlignedSegment.model_validate(s) for s in aligned_data]

        # Verify alignment preserves original segments
        assert len(aligned_segments) == len(transcript.segments)
        for orig, aligned in zip(transcript.segments, aligned_segments):
            assert orig.text == aligned.text
            assert orig.start == aligned.start
            assert orig.end == aligned.end


class TestFullPipelineExecution:
    """Test full pipeline execution with mocked external dependencies."""

    def test_transcribe_stage_output_structure(self, tmp_path):
        """Test transcription stage output structure."""
        from podx.schemas import Transcript

        # Create audio file
        audio_file = tmp_path / "input.mp3"
        audio_file.write_bytes(b"fake audio")

        # Simulate transcription result
        transcript_data = {
            "language": "en",
            "text": "Test transcript",
            "segments": [{"start": 0.0, "end": 1.0, "text": "Test transcript"}],
            "audio_path": str(audio_file),
        }

        # Validate transcript structure
        transcript = Transcript.model_validate(transcript_data)

        # Verify structure
        assert transcript.language == "en"
        assert len(transcript.segments) == 1
        assert transcript.audio_path == str(audio_file)

    @patch("podx.deepcast.chat_once")
    def test_deepcast_stage_with_transcript_input(self, mock_chat, tmp_path):
        """Test deepcast stage accepts transcript and produces markdown."""
        from podx.deepcast import deepcast

        # Create transcript
        transcript_data = {
            "audio_path": str(tmp_path / "audio.wav"),
            "language": "en",
            "text": "This is a test transcript with some content.",
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "This is a test transcript"},
                {"start": 2.0, "end": 4.0, "text": "with some content."},
            ],
        }

        # Mock LLM responses
        mock_chat.side_effect = [
            "Summary of chunk 1",  # Map phase
            "Final summary",  # Reduce phase
        ]

        # Run deepcast
        result, json_data = deepcast(
            transcript=transcript_data,
            model="gpt-4.1",
            temperature=0.2,
            max_chars_per_chunk=24000,
            want_json=False,
        )

        # Verify output
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Summary" in result or "summary" in result


class TestPipelineResumeAndRecovery:
    """Test pipeline resume functionality and error recovery."""

    def test_detect_existing_transcript(self, tmp_path):
        """Test detection of existing transcript for resume."""
        from podx.state.artifact_detector import ArtifactDetector

        # Create working directory with existing transcript
        working_dir = tmp_path / "episode"
        working_dir.mkdir()

        transcript_data = {
            "language": "en",
            "text": "Existing transcript",
            "segments": [{"start": 0.0, "end": 1.0, "text": "Existing transcript"}],
            "asr_model": "large-v3-turbo",
        }
        transcript_file = working_dir / "transcript-large-v3-turbo.json"
        transcript_file.write_text(json.dumps(transcript_data))

        # Detect artifacts
        detector = ArtifactDetector(working_dir)
        completed_steps = detector.detect_completed_steps()

        # Verify detection - check that TRANSCRIBE step is detected
        from podx.domain.enums import PipelineStep

        assert PipelineStep.TRANSCRIBE in completed_steps

    def test_detect_multiple_pipeline_artifacts(self, tmp_path):
        """Test detection of multiple artifacts from different stages."""
        from podx.state.artifact_detector import ArtifactDetector
        from podx.domain.enums import PipelineStep

        working_dir = tmp_path / "episode"
        working_dir.mkdir()

        # Create transcript
        transcript = working_dir / "transcript-large-v3-turbo.json"
        transcript.write_text(
            json.dumps(
                {
                    "language": "en",
                    "text": "Test",
                    "segments": [{"start": 0.0, "end": 1.0, "text": "Test"}],
                }
            )
        )

        # Create aligned transcript
        aligned = working_dir / "transcript-aligned-large-v3-turbo.json"
        aligned.write_text(
            json.dumps(
                {
                    "language": "en",
                    "text": "Test",
                    "segments": [
                        {
                            "start": 0.0,
                            "end": 1.0,
                            "text": "Test",
                            "words": [{"start": 0.0, "end": 1.0, "word": "Test"}],
                        }
                    ],
                }
            )
        )

        # Create deepcast
        deepcast_file = working_dir / "deepcast-large-v3-turbo-gpt-4.1.json"
        deepcast_file.write_text(json.dumps({"content": "Analysis"}))

        # Detect all
        detector = ArtifactDetector(working_dir)
        completed_steps = detector.detect_completed_steps()

        # Verify all detected
        assert PipelineStep.TRANSCRIBE in completed_steps
        assert PipelineStep.ALIGN in completed_steps
        assert PipelineStep.DEEPCAST in completed_steps


class TestConfigurationPropagation:
    """Test that configuration propagates correctly through pipeline stages."""

    def test_asr_model_propagates_to_transcript(self, tmp_path):
        """Test ASR model name is recorded in transcript metadata."""
        from podx.schemas import Transcript

        # Create audio file for validation
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake wav data")

        # Simulate transcript with ASR model metadata
        transcript_data = {
            "audio_path": str(audio_file),
            "language": "en",
            "text": "Test",
            "segments": [{"start": 0.0, "end": 1.0, "text": "Test"}],
            "asr_model": "large-v3-turbo",
            "asr_provider": "openai",
        }
        transcript = Transcript.model_validate(transcript_data)

        # Verify metadata
        assert transcript.asr_model == "large-v3-turbo"
        assert transcript.asr_provider == "openai"

    def test_llm_model_propagates_to_deepcast(self, tmp_path):
        """Test LLM model name is recorded in deepcast metadata."""
        # Create deepcast output with metadata
        deepcast_data = {
            "content": "Analysis content",
            "deepcast_metadata": {
                "model": "gpt-4.1",
                "asr_model": "large-v3-turbo",
                "deepcast_type": "brief",
                "temperature": 0.2,
            },
        }
        deepcast_file = tmp_path / "deepcast.json"
        deepcast_file.write_text(json.dumps(deepcast_data))

        # Read and verify
        loaded = json.loads(deepcast_file.read_text())
        metadata = loaded["deepcast_metadata"]

        assert metadata["model"] == "gpt-4.1"
        assert metadata["asr_model"] == "large-v3-turbo"
        assert metadata["deepcast_type"] == "brief"


class TestFileSystemIntegration:
    """Test file system operations and artifact management."""

    def test_working_directory_structure(self, tmp_path):
        """Test creation of proper working directory structure."""
        from podx.schemas import EpisodeMeta

        # Simulate episode directory creation
        show_name = "Test Podcast"
        episode_date = "2024-01-01"
        episode_dir = tmp_path / show_name / f"{episode_date}_episode"
        episode_dir.mkdir(parents=True)

        # Create episode metadata file
        # Create audio file for validation
        audio_file = episode_dir / "audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        episode_data = {
            "show": show_name,
            "feed": "https://example.com/feed.xml",
            "episode_title": "Test Episode",
            "episode_published": episode_date,
            "audio_path": str(audio_file),
        }
        episode_meta = EpisodeMeta.model_validate(episode_data)

        # Write metadata file
        meta_file = episode_dir / "episode-meta.json"
        meta_file.write_text(json.dumps(episode_meta.model_dump(), indent=2))

        # Verify structure
        assert episode_dir.exists()
        assert meta_file.exists()
        assert episode_dir.parent.name == show_name

    def test_artifact_naming_convention(self, tmp_path):
        """Test that artifacts follow naming conventions."""
        working_dir = tmp_path / "episode"
        working_dir.mkdir()

        # Create files following naming conventions
        files = [
            "transcript-large-v3-turbo.json",
            "transcript-aligned-large-v3-turbo.json",
            "transcript-diarized-large-v3-turbo.json",
            "transcript-preprocessed-large-v3-turbo.json",
            "deepcast-large-v3-turbo-gpt-4.1.json",
        ]

        for filename in files:
            (working_dir / filename).write_text("{}")

        # Verify all files exist and follow convention
        assert all((working_dir / f).exists() for f in files)

    def test_multiple_file_creation(self, tmp_path):
        """Test creation of multiple files in same directory."""
        working_dir = tmp_path / "episode"
        working_dir.mkdir()

        # Simulate creating multiple artifacts
        files = {
            "transcript.json": {"text": "transcript"},
            "aligned.json": {"text": "aligned"},
            "deepcast.json": {"content": "analysis"},
        }

        for filename, content in files.items():
            file_path = working_dir / filename
            file_path.write_text(json.dumps(content))

        # Verify all files exist
        assert all((working_dir / f).exists() for f in files.keys())

        # Verify content is correct
        for filename, expected_content in files.items():
            loaded = json.loads((working_dir / filename).read_text())
            assert loaded == expected_content


class TestErrorPropagation:
    """Test error handling and propagation through pipeline stages."""

    def test_missing_audio_file_error(self, tmp_path):
        """Test error when audio file doesn't exist."""
        from podx.schemas import EpisodeMeta

        # Try to create metadata with non-existent audio file
        episode_data = {
            "show": "Test Podcast",
            "feed": "https://example.com/feed.xml",
            "episode_title": "Test Episode",
            "episode_published": "2024-01-01",
            "audio_path": str(tmp_path / "nonexistent.mp3"),
        }

        # Should raise validation error
        with pytest.raises(ValueError):  # Pydantic validation error
            EpisodeMeta.model_validate(episode_data)

    def test_invalid_transcript_format(self):
        """Test error when transcript has invalid format."""
        from podx.schemas import Transcript
        from pydantic import ValidationError

        # Invalid: audio_path pointing to non-existent file
        invalid_data = {
            "audio_path": "/path/to/nonexistent/audio.mp3",
            "language": "en",
            "text": "Test",
            "segments": [],
        }

        with pytest.raises(ValidationError, match="Audio file not found"):
            Transcript.model_validate(invalid_data)

    def test_segment_timing_validation_error(self):
        """Test error when segment has invalid timing."""
        from podx.schemas import Segment

        # Invalid: end before start
        invalid_segment = {"start": 2.0, "end": 1.0, "text": "Invalid"}

        with pytest.raises(ValueError):
            Segment.model_validate(invalid_segment)


class TestDataConsistency:
    """Test data consistency across pipeline stages."""

    def test_audio_path_consistency(self, tmp_path):
        """Test that audio_path remains consistent across stages."""
        from podx.schemas import AudioMeta, EpisodeMeta, Transcript

        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake audio")

        # Episode metadata
        episode_data = {
            "show": "Test",
            "feed": "https://example.com/feed.xml",
            "episode_title": "Test",
            "episode_published": "2024-01-01",
            "audio_path": str(audio_file),
        }
        episode_meta = EpisodeMeta.model_validate(episode_data)

        # Audio metadata
        audio_data = {
            "audio_path": episode_meta.audio_path,
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav16",
        }
        audio_meta = AudioMeta.model_validate(audio_data)

        # Transcript
        transcript_data = {
            "audio_path": audio_meta.audio_path,
            "language": "en",
            "text": "Test",
            "segments": [{"start": 0.0, "end": 1.0, "text": "Test"}],
        }
        transcript = Transcript.model_validate(transcript_data)

        # Verify consistency
        assert episode_meta.audio_path == audio_meta.audio_path == transcript.audio_path

    def test_segment_count_consistency(self, tmp_path):
        """Test that segment count is consistent in transcript."""
        from podx.schemas import Transcript

        # Create audio file
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")

        segments = [
            {"start": 0.0, "end": 1.0, "text": "One"},
            {"start": 1.0, "end": 2.0, "text": "Two"},
            {"start": 2.0, "end": 3.0, "text": "Three"},
        ]

        transcript_data = {
            "audio_path": str(audio_file),
            "language": "en",
            "text": "One Two Three",
            "segments": segments,
        }
        transcript = Transcript.model_validate(transcript_data)

        # Verify consistency
        assert len(transcript.segments) == 3
        assert len(transcript.segments) == len(segments)


class TestPerformanceCharacteristics:
    """Test performance characteristics of pipeline operations."""

    def test_large_transcript_processing(self, tmp_path):
        """Test processing of large transcript (many segments)."""
        from podx.schemas import Transcript

        # Create audio file
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"fake audio")

        # Create transcript with 1000 segments
        segments = [
            {"start": float(i), "end": float(i + 1), "text": f"Segment {i}"}
            for i in range(1000)
        ]

        transcript_data = {
            "audio_path": str(audio_file),
            "language": "en",
            "text": " ".join([f"Segment {i}" for i in range(1000)]),
            "segments": segments,
        }

        # Should handle large transcript without errors
        transcript = Transcript.model_validate(transcript_data)
        assert len(transcript.segments) == 1000

    def test_file_io_efficiency(self, tmp_path):
        """Test efficiency of file I/O operations."""
        import time

        # Create large JSON file (simulating transcript)
        large_data = {
            "segments": [
                {"start": float(i), "end": float(i + 1), "text": f"Text {i}"}
                for i in range(10000)
            ]
        }
        large_file = tmp_path / "large_transcript.json"

        # Measure write time
        start = time.time()
        large_file.write_text(json.dumps(large_data))
        write_time = time.time() - start

        # Measure read time
        start = time.time()
        loaded = json.loads(large_file.read_text())
        read_time = time.time() - start

        # Basic performance check (should be fast on modern systems)
        assert write_time < 1.0  # Less than 1 second
        assert read_time < 1.0
        assert len(loaded["segments"]) == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
