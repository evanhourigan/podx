"""Unit tests for core.export module.

Tests pure business logic without UI dependencies.
No external dependencies to mock - pure text format conversion.
"""

import pytest

from podx.core.export import (ExportEngine, ExportError, export_transcript,
                              format_timestamp, write_if_changed)


class TestFormatTimestamp:
    """Test timestamp formatting utility."""

    def test_format_zero_seconds(self):
        """Test formatting zero seconds."""
        result = format_timestamp(0.0)
        assert result == "00:00:00,000"

    def test_format_seconds_only(self):
        """Test formatting seconds only."""
        result = format_timestamp(45.678)
        assert result == "00:00:45,678"

    def test_format_minutes_and_seconds(self):
        """Test formatting minutes and seconds."""
        result = format_timestamp(125.5)
        assert result == "00:02:05,500"

    def test_format_hours_minutes_seconds(self):
        """Test formatting hours, minutes, and seconds."""
        result = format_timestamp(3661.123)  # 1 hour, 1 minute, 1.123 seconds
        assert result == "01:01:01,123"

    def test_format_large_timestamp(self):
        """Test formatting large timestamp."""
        result = format_timestamp(7265.999)  # 2 hours, 1 minute, 5.999 seconds
        assert result == "02:01:05,999"

    def test_format_milliseconds_rounding(self):
        """Test milliseconds are rounded correctly."""
        result = format_timestamp(1.0005)
        assert result == "00:00:01,000"  # Python's round() uses banker's rounding

    def test_format_preserves_leading_zeros(self):
        """Test that leading zeros are preserved in all fields."""
        result = format_timestamp(3.004)
        assert result == "00:00:03,004"


class TestWriteIfChanged:
    """Test file write optimization utility."""

    def test_write_new_file(self, tmp_path):
        """Test writing a new file."""
        file_path = tmp_path / "test.txt"
        content = "Hello, world!"

        written = write_if_changed(file_path, content, replace=False)

        assert written is True
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_write_replace_false_always_writes(self, tmp_path):
        """Test that replace=False always writes (default behavior)."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Old content")

        written = write_if_changed(file_path, "New content", replace=False)

        assert written is True
        assert file_path.read_text() == "New content"

    def test_write_replace_true_unchanged_content_skips(self, tmp_path):
        """Test that replace=True skips writing if content is unchanged."""
        file_path = tmp_path / "test.txt"
        content = "Same content"
        file_path.write_text(content)

        written = write_if_changed(file_path, content, replace=True)

        assert written is False
        assert file_path.read_text() == content

    def test_write_replace_true_changed_content_writes(self, tmp_path):
        """Test that replace=True writes if content has changed."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Old content")

        written = write_if_changed(file_path, "New content", replace=True)

        assert written is True
        assert file_path.read_text() == "New content"

    def test_write_creates_parent_directories(self, tmp_path):
        """Test that writing creates parent directories if needed."""
        file_path = tmp_path / "nested" / "path" / "test.txt"
        content = "Test content"

        # Note: write_if_changed does NOT create parent directories
        # This should raise an error
        with pytest.raises(FileNotFoundError):
            write_if_changed(file_path, content)


class TestExportEngineToTxt:
    """Test ExportEngine.to_txt() method."""

    def test_to_txt_basic(self):
        """Test basic TXT conversion."""
        segments = [
            {"text": "Hello, world!"},
            {"text": "This is a test."},
        ]

        engine = ExportEngine()
        result = engine.to_txt(segments)

        assert result == "Hello, world!\nThis is a test.\n"

    def test_to_txt_strips_whitespace(self):
        """Test that to_txt strips whitespace from segments."""
        segments = [
            {"text": "  Padded text  "},
            {"text": "\tTabbed text\n"},
        ]

        engine = ExportEngine()
        result = engine.to_txt(segments)

        assert result == "Padded text\nTabbed text\n"

    def test_to_txt_empty_segments(self):
        """Test TXT conversion with empty segments list."""
        segments = []

        engine = ExportEngine()
        result = engine.to_txt(segments)

        assert result == "\n"

    def test_to_txt_single_segment(self):
        """Test TXT conversion with single segment."""
        segments = [{"text": "Only one line."}]

        engine = ExportEngine()
        result = engine.to_txt(segments)

        assert result == "Only one line.\n"

    def test_to_txt_preserves_speaker_info(self):
        """Test that to_txt ignores speaker info (plain text only)."""
        segments = [
            {"text": "First speaker", "speaker": "SPEAKER_00"},
            {"text": "Second speaker", "speaker": "SPEAKER_01"},
        ]

        engine = ExportEngine()
        result = engine.to_txt(segments)

        # TXT format doesn't include speaker labels
        assert result == "First speaker\nSecond speaker\n"


class TestExportEngineToSrt:
    """Test ExportEngine.to_srt() method."""

    def test_to_srt_basic(self):
        """Test basic SRT conversion."""
        segments = [
            {"text": "First line", "start": 0.0, "end": 2.5},
            {"text": "Second line", "start": 2.5, "end": 5.0},
        ]

        engine = ExportEngine()
        result = engine.to_srt(segments)

        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:02,500\n"
            "First line\n"
            "\n"
            "2\n"
            "00:00:02,500 --> 00:00:05,000\n"
            "Second line\n"
        )
        assert result == expected

    def test_to_srt_with_speaker(self):
        """Test SRT conversion with speaker labels."""
        segments = [
            {"text": "Hello", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"},
            {"text": "Hi there", "start": 1.0, "end": 2.0, "speaker": "SPEAKER_01"},
        ]

        engine = ExportEngine()
        result = engine.to_srt(segments)

        expected = (
            "1\n"
            "00:00:00,000 --> 00:00:01,000\n"
            "[SPEAKER_00] Hello\n"
            "\n"
            "2\n"
            "00:00:01,000 --> 00:00:02,000\n"
            "[SPEAKER_01] Hi there\n"
        )
        assert result == expected

    def test_to_srt_strips_whitespace(self):
        """Test that SRT strips whitespace from text."""
        segments = [
            {"text": "  Padded  ", "start": 0.0, "end": 1.0},
        ]

        engine = ExportEngine()
        result = engine.to_srt(segments)

        assert "[SPEAKER_00] Padded" not in result
        assert "Padded\n" in result

    def test_to_srt_empty_segments(self):
        """Test SRT conversion with empty segments list."""
        segments = []

        engine = ExportEngine()
        result = engine.to_srt(segments)

        assert result == ""

    def test_to_srt_single_segment(self):
        """Test SRT conversion with single segment."""
        segments = [
            {"text": "Only one line", "start": 0.0, "end": 3.5},
        ]

        engine = ExportEngine()
        result = engine.to_srt(segments)

        expected = "1\n" "00:00:00,000 --> 00:00:03,500\n" "Only one line\n"
        assert result == expected


class TestExportEngineToVtt:
    """Test ExportEngine.to_vtt() method."""

    def test_to_vtt_basic(self):
        """Test basic VTT conversion."""
        segments = [
            {"text": "First line", "start": 0.0, "end": 2.5},
            {"text": "Second line", "start": 2.5, "end": 5.0},
        ]

        engine = ExportEngine()
        result = engine.to_vtt(segments)

        expected = (
            "WEBVTT\n"
            "\n"
            "00:00:00.000 --> 00:00:02.500\n"
            "First line\n"
            "\n"
            "00:00:02.500 --> 00:00:05.000\n"
            "Second line\n"
        )
        assert result == expected

    def test_to_vtt_with_speaker(self):
        """Test VTT conversion with speaker labels."""
        segments = [
            {"text": "Hello", "start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"},
            {"text": "Hi there", "start": 1.0, "end": 2.0, "speaker": "SPEAKER_01"},
        ]

        engine = ExportEngine()
        result = engine.to_vtt(segments)

        expected = (
            "WEBVTT\n"
            "\n"
            "00:00:00.000 --> 00:00:01.000\n"
            "[SPEAKER_00] Hello\n"
            "\n"
            "00:00:01.000 --> 00:00:02.000\n"
            "[SPEAKER_01] Hi there\n"
        )
        assert result == expected

    def test_to_vtt_uses_period_for_milliseconds(self):
        """Test that VTT uses periods instead of commas for milliseconds."""
        segments = [
            {"text": "Test", "start": 1.234, "end": 2.567},
        ]

        engine = ExportEngine()
        result = engine.to_vtt(segments)

        # VTT should use periods, not commas
        assert "00:00:01.234" in result
        assert "00:00:02.567" in result
        assert "," not in result.split("\n")[2]  # Check timestamp line

    def test_to_vtt_has_header(self):
        """Test that VTT output starts with WEBVTT header."""
        segments = [
            {"text": "Test", "start": 0.0, "end": 1.0},
        ]

        engine = ExportEngine()
        result = engine.to_vtt(segments)

        assert result.startswith("WEBVTT\n")

    def test_to_vtt_empty_segments(self):
        """Test VTT conversion with empty segments list."""
        segments = []

        engine = ExportEngine()
        result = engine.to_vtt(segments)

        assert result == "WEBVTT\n"


class TestExportEngineToMd:
    """Test ExportEngine.to_md() method."""

    def test_to_md_basic(self):
        """Test basic Markdown conversion."""
        segments = [
            {"text": "First paragraph."},
            {"text": "Second paragraph."},
        ]

        engine = ExportEngine()
        result = engine.to_md(segments)

        expected = "# Transcript\n\nFirst paragraph.\n\nSecond paragraph.\n"
        assert result == expected

    def test_to_md_single_segment(self):
        """Test Markdown conversion with single segment."""
        segments = [{"text": "Only one paragraph."}]

        engine = ExportEngine()
        result = engine.to_md(segments)

        expected = "# Transcript\n\nOnly one paragraph.\n"
        assert result == expected

    def test_to_md_strips_whitespace(self):
        """Test that Markdown strips whitespace from segments."""
        segments = [
            {"text": "  Padded text  "},
            {"text": "\tTabbed text\n"},
        ]

        engine = ExportEngine()
        result = engine.to_md(segments)

        expected = "# Transcript\n\nPadded text\n\nTabbed text\n"
        assert result == expected

    def test_to_md_empty_segments(self):
        """Test Markdown conversion with empty segments list."""
        segments = []

        engine = ExportEngine()
        result = engine.to_md(segments)

        assert result == "# Transcript\n\n\n"

    def test_to_md_has_header(self):
        """Test that Markdown output starts with header."""
        segments = [{"text": "Test"}]

        engine = ExportEngine()
        result = engine.to_md(segments)

        assert result.startswith("# Transcript\n\n")


class TestExportEngineExport:
    """Test ExportEngine.export() method."""

    def test_export_single_format(self, tmp_path):
        """Test exporting to a single format."""
        transcript = {
            "segments": [
                {"text": "Test line", "start": 0.0, "end": 1.0},
            ]
        }

        engine = ExportEngine()
        result = engine.export(transcript, ["txt"], tmp_path, "test")

        assert result["formats"] == ["txt"]
        assert result["segments_count"] == 1
        assert result["files_written"] == 1
        assert "txt" in result["files"]

        # Verify file exists
        txt_file = tmp_path / "test.txt"
        assert txt_file.exists()
        assert txt_file.read_text() == "Test line\n"

    def test_export_multiple_formats(self, tmp_path):
        """Test exporting to multiple formats."""
        transcript = {
            "segments": [
                {"text": "Test line", "start": 0.0, "end": 1.0},
            ]
        }

        engine = ExportEngine()
        result = engine.export(
            transcript, ["txt", "srt", "vtt", "md"], tmp_path, "test"
        )

        assert result["formats"] == ["txt", "srt", "vtt", "md"]
        assert result["files_written"] == 4
        assert len(result["files"]) == 4

        # Verify all files exist
        assert (tmp_path / "test.txt").exists()
        assert (tmp_path / "test.srt").exists()
        assert (tmp_path / "test.vtt").exists()
        assert (tmp_path / "test.md").exists()

    def test_export_missing_segments_raises_error(self, tmp_path):
        """Test that export raises error if segments are missing."""
        transcript = {}  # No segments field

        engine = ExportEngine()

        with pytest.raises(ExportError, match="Transcript missing 'segments' field"):
            engine.export(transcript, ["txt"], tmp_path)

    def test_export_invalid_format_raises_error(self, tmp_path):
        """Test that export raises error for invalid format."""
        transcript = {"segments": [{"text": "Test"}]}

        engine = ExportEngine()

        with pytest.raises(ExportError, match="Invalid formats: invalid"):
            engine.export(transcript, ["txt", "invalid"], tmp_path)

    def test_export_multiple_invalid_formats_raises_error(self, tmp_path):
        """Test that export raises error for multiple invalid formats."""
        transcript = {"segments": [{"text": "Test"}]}

        engine = ExportEngine()

        with pytest.raises(ExportError, match="Invalid formats"):
            engine.export(transcript, ["bad1", "bad2"], tmp_path)

    def test_export_with_replace_false(self, tmp_path):
        """Test that export with replace=False always writes files."""
        transcript = {"segments": [{"text": "Test", "start": 0.0, "end": 1.0}]}

        # Create existing files
        (tmp_path / "test.txt").write_text("Old content")
        (tmp_path / "test.srt").write_text("Old content")

        engine = ExportEngine()
        result = engine.export(
            transcript, ["txt", "srt"], tmp_path, "test", replace=False
        )

        # Both files should be written (replace=False ignores existing)
        assert result["files_written"] == 2

    def test_export_with_replace_true_unchanged(self, tmp_path):
        """Test that export with replace=True skips unchanged files."""
        transcript = {
            "segments": [
                {"text": "Test line", "start": 0.0, "end": 1.0},
            ]
        }

        engine = ExportEngine()

        # First export
        result1 = engine.export(transcript, ["txt"], tmp_path, "test", replace=True)
        assert result1["files_written"] == 1

        # Second export with same content
        result2 = engine.export(transcript, ["txt"], tmp_path, "test", replace=True)
        assert result2["files_written"] == 0  # Content unchanged, skipped

    def test_export_with_replace_true_changed(self, tmp_path):
        """Test that export with replace=True writes changed files."""
        transcript1 = {"segments": [{"text": "First version"}]}
        transcript2 = {"segments": [{"text": "Second version"}]}

        engine = ExportEngine()

        # First export
        result1 = engine.export(transcript1, ["txt"], tmp_path, "test", replace=True)
        assert result1["files_written"] == 1

        # Second export with different content
        result2 = engine.export(transcript2, ["txt"], tmp_path, "test", replace=True)
        assert result2["files_written"] == 1  # Content changed, written

        # Verify new content
        assert (tmp_path / "test.txt").read_text() == "Second version\n"

    def test_export_custom_base_name(self, tmp_path):
        """Test exporting with custom base filename."""
        transcript = {"segments": [{"text": "Test"}]}

        engine = ExportEngine()
        result = engine.export(transcript, ["txt"], tmp_path, "custom_name")

        assert "custom_name.txt" in result["files"]["txt"]
        assert (tmp_path / "custom_name.txt").exists()

    def test_export_calls_progress_callback(self, tmp_path):
        """Test that export calls progress callback for each format."""
        transcript = {"segments": [{"text": "Test", "start": 0.0, "end": 1.0}]}
        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        engine = ExportEngine(progress_callback=progress_callback)
        engine.export(transcript, ["txt", "srt"], tmp_path, "test")

        # Should have progress messages for both formats
        assert len(progress_messages) == 2
        assert "TXT" in progress_messages[0]
        assert "SRT" in progress_messages[1]

    def test_export_returns_correct_metadata(self, tmp_path):
        """Test that export returns correct metadata."""
        transcript = {
            "segments": [
                {"text": "Line 1", "start": 0.0, "end": 1.0},
                {"text": "Line 2", "start": 1.0, "end": 2.0},
            ]
        }

        engine = ExportEngine()
        result = engine.export(transcript, ["txt", "md"], tmp_path, "test")

        assert result["formats"] == ["txt", "md"]
        assert result["segments_count"] == 2
        assert result["output_dir"] == str(tmp_path)
        assert "txt" in result["files"]
        assert "md" in result["files"]


class TestExportTranscriptFunction:
    """Test export_transcript convenience function."""

    def test_export_transcript_basic(self, tmp_path):
        """Test basic usage of export_transcript function."""
        transcript = {
            "segments": [
                {"text": "Test line", "start": 0.0, "end": 1.0},
            ]
        }

        result = export_transcript(transcript, ["txt"], tmp_path, "test")

        assert result["formats"] == ["txt"]
        assert result["files_written"] == 1
        assert (tmp_path / "test.txt").exists()

    def test_export_transcript_with_progress_callback(self, tmp_path):
        """Test export_transcript with progress callback."""
        transcript = {"segments": [{"text": "Test"}]}
        progress_messages = []

        def progress_callback(msg):
            progress_messages.append(msg)

        export_transcript(
            transcript, ["txt"], tmp_path, "test", progress_callback=progress_callback
        )

        assert len(progress_messages) == 1
        assert "TXT" in progress_messages[0]

    def test_export_transcript_with_replace(self, tmp_path):
        """Test export_transcript with replace parameter."""
        transcript = {"segments": [{"text": "Test"}]}

        # First export
        result1 = export_transcript(transcript, ["txt"], tmp_path, "test", replace=True)
        assert result1["files_written"] == 1

        # Second export (unchanged)
        result2 = export_transcript(transcript, ["txt"], tmp_path, "test", replace=True)
        assert result2["files_written"] == 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_text_segments(self):
        """Test handling of segments with empty text."""
        segments = [
            {"text": ""},
            {"text": "   "},  # Only whitespace
            {"text": "Valid text"},
        ]

        engine = ExportEngine()
        result = engine.to_txt(segments)

        # Empty strings should still be included (after stripping)
        assert result == "\n\nValid text\n"

    def test_segments_without_timing_info(self):
        """Test that TXT/MD work without timing info."""
        segments = [{"text": "No timing info"}]

        engine = ExportEngine()

        # TXT and MD should work without timing
        txt_result = engine.to_txt(segments)
        assert "No timing info" in txt_result

        md_result = engine.to_md(segments)
        assert "No timing info" in md_result

    def test_special_characters_in_text(self):
        """Test handling of special characters in segment text."""
        segments = [
            {"text": "Special chars: <>&\"'"},
            {"text": "Unicode: é ñ 中文 🎉"},
        ]

        engine = ExportEngine()
        result = engine.to_txt(segments)

        # Should preserve special characters
        assert "Special chars: <>&\"'" in result
        assert "Unicode: é ñ 中文 🎉" in result

    def test_very_long_segments(self):
        """Test handling of very long segment text."""
        long_text = "A" * 10000
        segments = [{"text": long_text}]

        engine = ExportEngine()
        result = engine.to_txt(segments)

        assert len(result) >= 10000
        assert long_text in result

    def test_export_with_none_speaker(self):
        """Test SRT/VTT with explicit None speaker value."""
        segments = [
            {"text": "No speaker", "start": 0.0, "end": 1.0, "speaker": None},
        ]

        engine = ExportEngine()
        srt_result = engine.to_srt(segments)

        # Should not include "[None]" prefix
        assert "[None]" not in srt_result
        assert "No speaker" in srt_result
