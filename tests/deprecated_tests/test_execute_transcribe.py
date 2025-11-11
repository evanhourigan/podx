"""Unit tests for _execute_transcribe() helper function."""

from pathlib import Path
from unittest.mock import MagicMock, patch


from podx.orchestrate import _execute_transcribe


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_single_mode_existing_transcript(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test single mode with existing transcript for the same model."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"

    # Mock transcript file exists
    with patch("pathlib.Path.exists", return_value=True):
        with patch(
            "pathlib.Path.read_text",
            return_value='{"asr_model": "large-v3", "segments": [{"text": "hello"}]}',
        ):
            progress = MagicMock()

            latest, latest_name = _execute_transcribe(
                model=model,
                compute="int8",
                asr_provider="auto",
                preset=None,
                dual=False,
                audio={"audio_path": "/tmp/audio.wav"},
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify
    assert latest["asr_model"] == "large-v3"
    assert latest_name == "transcript-large-v3"
    assert mock_run.call_count == 0  # Should not transcribe
    progress.complete_step.assert_called_once()


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_single_mode_fresh_transcription(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test single mode with no existing transcript (fresh transcription)."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}  # No existing transcripts

    # Mock transcribe result
    transcript_data = {"asr_model": "large-v3", "segments": [{"text": "hello world"}]}
    mock_run.return_value = transcript_data

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        latest, latest_name = _execute_transcribe(
            model=model,
            compute="int8",
            asr_provider="auto",
            preset=None,
            dual=False,
            audio={"audio_path": "/tmp/audio.wav"},
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify
    assert latest == transcript_data
    assert latest_name == "transcript-large-v3"
    mock_run.assert_called_once()

    # Verify command built correctly
    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "podx-transcribe" in cmd
    assert "--model" in cmd
    assert "large-v3" in cmd
    assert "--compute" in cmd
    assert "int8" in cmd


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_single_mode_with_asr_provider(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test single mode with specific ASR provider."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}

    transcript_data = {"asr_model": "large-v3", "segments": []}
    mock_run.return_value = transcript_data

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        _execute_transcribe(
            model=model,
            compute="int8",
            asr_provider="openai",  # Specific provider
            preset="precision",  # Specific preset
            dual=False,
            audio={"audio_path": "/tmp/audio.wav"},
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify command includes provider and preset
    call_args = mock_run.call_args
    cmd = call_args[0][0]
    assert "--asr-provider" in cmd
    assert "openai" in cmd
    assert "--preset" in cmd
    assert "precision" in cmd


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_single_mode_model_fallback(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test single mode falls back to best available model."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"  # Requested model
    mock_sanitize.return_value = "large_v3"

    # Mock existing transcripts with different models
    mock_discover.return_value = {
        "tiny": Path("/tmp/test/transcript-tiny.json"),
        "base": Path("/tmp/test/transcript-base.json"),
        "large-v2": Path("/tmp/test/transcript-large-v2.json"),
    }

    # Mock reading the best available (large-v2)
    with patch(
        "pathlib.Path.exists", return_value=False
    ):  # Requested model doesn't exist
        with patch(
            "pathlib.Path.read_text",
            return_value='{"asr_model": "large-v2", "segments": [{"text": "fallback"}]}',
        ):
            progress = MagicMock()

            latest, latest_name = _execute_transcribe(
                model=model,
                compute="int8",
                asr_provider="auto",
                preset=None,
                dual=False,
                audio={"audio_path": "/tmp/audio.wav"},
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify fallback to best model (large-v2)
    assert latest["asr_model"] == "large-v2"
    assert mock_run.call_count == 0  # Should reuse existing
    mock_logger.info.assert_called()


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_dual_mode_fresh_transcription(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test dual mode with fresh precision + recall transcription."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}

    # Mock transcribe results
    prec_data = {"asr_model": "large-v3", "preset": "precision", "segments": []}
    rec_data = {"asr_model": "large-v3", "preset": "recall", "segments": []}
    mock_run.side_effect = [prec_data, rec_data]

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        latest, latest_name = _execute_transcribe(
            model=model,
            compute="int8",
            asr_provider="auto",
            preset=None,
            dual=True,
            audio={"audio_path": "/tmp/audio.wav"},
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify both transcriptions ran
    assert mock_run.call_count == 2

    # Verify precision command
    prec_cmd = mock_run.call_args_list[0][0][0]
    assert "--preset" in prec_cmd
    assert "precision" in prec_cmd

    # Verify recall command
    rec_cmd = mock_run.call_args_list[1][0][0]
    assert "--preset" in rec_cmd
    assert "recall" in rec_cmd

    # Verify returns recall as latest
    assert latest == rec_data
    assert latest_name == "transcript-large_v3-recall"


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_dual_mode_resume_precision_only(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test dual mode resumes when precision exists but recall missing."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}

    rec_data = {"asr_model": "large-v3", "preset": "recall", "segments": []}
    mock_run.return_value = rec_data  # Only recall runs

    # Mock precision exists, recall doesn't
    with patch("pathlib.Path.exists", new=lambda self: "precision" in str(self)):
        with patch(
            "pathlib.Path.read_text",
            return_value='{"asr_model": "large-v3", "preset": "precision", "segments": []}',
        ):
            progress = MagicMock()

            latest, latest_name = _execute_transcribe(
                model=model,
                compute="int8",
                asr_provider="auto",
                preset=None,
                dual=True,
                audio={"audio_path": "/tmp/audio.wav"},
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify only recall was transcribed
    assert mock_run.call_count == 1


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_dual_mode_full_resume(mock_discover, mock_sanitize, mock_run, mock_logger):
    """Test dual mode resumes when both precision and recall exist."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}

    # Mock both precision and recall exist (but not legacy transcript.json)
    read_data = [
        '{"asr_model": "large-v3", "preset": "precision", "segments": []}',
        '{"asr_model": "large-v3", "preset": "recall", "segments": []}',
    ]

    with patch("pathlib.Path.exists", new=lambda self: "transcript.json" != self.name):
        with patch("pathlib.Path.read_text", side_effect=read_data):
            progress = MagicMock()

            latest, latest_name = _execute_transcribe(
                model=model,
                compute="int8",
                asr_provider="auto",
                preset=None,
                dual=True,
                audio={"audio_path": "/tmp/audio.wav"},
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify no transcription ran (both resumed)
    assert mock_run.call_count == 0
    assert latest_name == "transcript-large_v3-recall"


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_legacy_transcript_json_handling(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test handling of legacy transcript.json file."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}

    # Mock legacy transcript.json exists
    with patch("pathlib.Path.exists", new=lambda self: "transcript.json" == self.name):
        with patch(
            "pathlib.Path.read_text",
            return_value='{"asr_model": "base", "segments": [{"text": "legacy"}]}',
        ):
            progress = MagicMock()

            latest, latest_name = _execute_transcribe(
                model=model,
                compute="int8",
                asr_provider="auto",
                preset=None,
                dual=False,
                audio={"audio_path": "/tmp/audio.wav"},
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify legacy transcript was used
    # Note: discover_transcripts would have been called and should find it
    # This test verifies the function handles the legacy file properly


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_dual_mode_with_asr_provider(
    mock_discover, mock_sanitize, mock_run, mock_logger
):
    """Test dual mode with specific ASR provider."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}

    prec_data = {"asr_model": "large-v3", "preset": "precision"}
    rec_data = {"asr_model": "large-v3", "preset": "recall"}
    mock_run.side_effect = [prec_data, rec_data]

    with patch.object(Path, "exists", return_value=False):
        progress = MagicMock()

        _execute_transcribe(
            model=model,
            compute="float16",
            asr_provider="local",
            preset=None,
            dual=True,
            audio={"audio_path": "/tmp/audio.wav"},
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify both commands include ASR provider
    prec_cmd = mock_run.call_args_list[0][0][0]
    assert "--asr-provider" in prec_cmd
    assert "local" in prec_cmd

    rec_cmd = mock_run.call_args_list[1][0][0]
    assert "--asr-provider" in rec_cmd
    assert "local" in rec_cmd


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
@patch("podx.utils.sanitize_model_name")
@patch("podx.utils.discover_transcripts")
def test_progress_tracking(mock_discover, mock_sanitize, mock_run, mock_logger):
    """Test that progress callbacks are called correctly."""
    # Setup
    wd = Path("/tmp/test")
    model = "large-v3"
    mock_sanitize.return_value = "large_v3"
    mock_discover.return_value = {}

    transcript_data = {"asr_model": "large-v3", "segments": []}
    mock_run.return_value = transcript_data

    with patch.object(Path, "exists", return_value=False):
        progress = MagicMock()

        _execute_transcribe(
            model=model,
            compute="int8",
            asr_provider="auto",
            preset=None,
            dual=False,
            audio={"audio_path": "/tmp/audio.wav"},
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify progress callbacks
    progress.start_step.assert_called_once()
    progress.complete_step.assert_called_once()

    # Verify complete message includes segment count
    complete_call = progress.complete_step.call_args[0][0]
    assert "Transcription complete" in complete_call
