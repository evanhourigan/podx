"""Unit tests for _execute_enhancement() helper function."""

from pathlib import Path
from unittest.mock import MagicMock, patch


from podx.orchestrate import _execute_enhancement


@patch("podx.orchestrate._run")
def test_no_enhancement_returns_input_unchanged(mock_run):
    """Test that no enhancement flags returns input unchanged."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": [{"text": "hello"}]}
    input_name = "transcript-base"

    progress = MagicMock()

    # Call with all enhancement flags False
    latest, latest_name = _execute_enhancement(
        preprocess=False,
        restore=False,
        align=False,
        diarize=False,
        dual=False,
        model="base",
        latest=input_transcript,
        latest_name=input_name,
        wd=wd,
        progress=progress,
        verbose=False,
    )

    # Verify no processing occurred
    assert latest == input_transcript
    assert latest_name == input_name
    assert mock_run.call_count == 0
    progress.start_step.assert_not_called()


@patch("podx.utils.build_preprocess_command")
@patch("podx.utils.sanitize_model_name")
@patch("podx.orchestrate._run")
def test_preprocess_single_mode(mock_run, mock_sanitize, mock_build_cmd):
    """Test preprocessing in single mode."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}
    mock_sanitize.return_value = "base"
    mock_build_cmd.return_value = ["podx-preprocess", "--output", "file.json"]

    preprocessed = {"asr_model": "base", "segments": [], "preprocessed": True}
    mock_run.return_value = preprocessed

    progress = MagicMock()

    latest, latest_name = _execute_enhancement(
        preprocess=True,
        restore=False,
        align=False,
        diarize=False,
        dual=False,
        model="base",
        latest=input_transcript,
        latest_name="transcript-base",
        wd=wd,
        progress=progress,
        verbose=False,
    )

    # Verify preprocessing ran
    assert latest == preprocessed
    assert latest_name == "transcript-preprocessed-base"
    mock_run.assert_called_once()
    progress.start_step.assert_called_once()
    progress.complete_step.assert_called_once()


@patch("podx.utils.build_preprocess_command")
@patch("podx.utils.sanitize_model_name")
@patch("podx.orchestrate._run")
def test_preprocess_dual_mode(mock_run, mock_sanitize, mock_build_cmd):
    """Test preprocessing in dual mode (precision + recall)."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "large-v3", "preset": "recall", "segments": []}
    mock_sanitize.return_value = "large_v3"
    mock_build_cmd.return_value = ["podx-preprocess", "--output", "file.json"]

    prec_preprocessed = {"asr_model": "large-v3", "preset": "precision", "preprocessed": True}
    rec_preprocessed = {"asr_model": "large-v3", "preset": "recall", "preprocessed": True}
    mock_run.side_effect = [prec_preprocessed, rec_preprocessed]

    progress = MagicMock()

    latest, latest_name = _execute_enhancement(
        preprocess=False,  # Not explicitly set, but dual=True implies it
        restore=False,
        align=False,
        diarize=False,
        dual=True,  # Dual mode triggers preprocessing
        model="large-v3",
        latest=input_transcript,
        latest_name="transcript-large_v3-recall",
        wd=wd,
        progress=progress,
        verbose=False,
    )

    # Verify both tracks were preprocessed
    assert mock_run.call_count == 2
    assert latest == rec_preprocessed
    assert latest_name == "transcript-preprocessed-large_v3-recall"


@patch("podx.utils.build_preprocess_command")
@patch("podx.utils.sanitize_model_name")
@patch("podx.orchestrate._run")
def test_preprocess_with_restore(mock_run, mock_sanitize, mock_build_cmd):
    """Test preprocessing with restore flag."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}
    mock_sanitize.return_value = "base"
    mock_build_cmd.return_value = ["podx-preprocess", "--restore", "--output", "file.json"]

    preprocessed = {"asr_model": "base", "restored": True}
    mock_run.return_value = preprocessed

    progress = MagicMock()

    latest, latest_name = _execute_enhancement(
        preprocess=True,
        restore=True,  # Enable restore
        align=False,
        diarize=False,
        dual=False,
        model="base",
        latest=input_transcript,
        latest_name="transcript-base",
        wd=wd,
        progress=progress,
        verbose=False,
    )

    # Verify restore flag was passed
    mock_build_cmd.assert_called_with(Path("/tmp/test/transcript-preprocessed-base.json"), True)
    assert latest == preprocessed


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
def test_align_fresh_alignment(mock_run, mock_logger):
    """Test fresh alignment when no existing aligned file."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}

    aligned = {"asr_model": "base", "segments": [], "words": []}
    mock_run.return_value = aligned

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        latest, latest_name = _execute_enhancement(
            preprocess=False,
            restore=False,
            align=True,  # Enable alignment
            diarize=False,
            dual=False,
            model="base",
            latest=input_transcript,
            latest_name="transcript-base",
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify alignment ran
    assert latest == aligned
    assert latest_name == "transcript-aligned-base"
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["podx-align"]


@patch("podx.orchestrate.logger")
def test_align_resume_existing_file(mock_logger):
    """Test alignment resume when existing aligned file found."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value='{"asr_model": "base", "segments": [], "words": []}'):
            progress = MagicMock()

            latest, latest_name = _execute_enhancement(
                preprocess=False,
                restore=False,
                align=True,
                diarize=False,
                dual=False,
                model="base",
                latest=input_transcript,
                latest_name="transcript-base",
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify resumed without running alignment
    assert latest["asr_model"] == "base"
    assert latest_name == "transcript-aligned-base"
    progress.complete_step.assert_called_once()
    assert "existing" in progress.complete_step.call_args[0][0].lower()


@patch("podx.orchestrate.logger")
def test_align_resume_legacy_file(mock_logger):
    """Test alignment resume from legacy aligned-transcript.json file."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}

    def exists_side_effect(self):
        # New format doesn't exist, but legacy does
        if self.name == "aligned-transcript.json":
            return True
        return False

    with patch("pathlib.Path.exists", new=exists_side_effect):
        with patch("pathlib.Path.read_text", return_value='{"asr_model": "base", "words": []}'):
            progress = MagicMock()

            latest, latest_name = _execute_enhancement(
                preprocess=False,
                restore=False,
                align=True,
                diarize=False,
                dual=False,
                model="base",
                latest=input_transcript,
                latest_name="transcript-base",
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify resumed from legacy file
    assert latest_name == "transcript-aligned"
    mock_logger.info.assert_called()


@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
def test_diarize_fresh_diarization(mock_run, mock_logger):
    """Test fresh diarization when no existing diarized file."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}

    diarized = {"asr_model": "base", "segments": [{"speaker": "SPEAKER_00"}]}
    mock_run.return_value = diarized

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        latest, latest_name = _execute_enhancement(
            preprocess=False,
            restore=False,
            align=False,
            diarize=True,  # Enable diarization
            dual=False,
            model="base",
            latest=input_transcript,
            latest_name="transcript-base",
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify diarization ran
    assert latest == diarized
    assert latest_name == "transcript-diarized-base"
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["podx-diarize"]


@patch("podx.orchestrate.logger")
def test_diarize_resume_existing_file(mock_logger):
    """Test diarization resume when existing diarized file found."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value='{"asr_model": "base", "segments": [{"speaker": "SPEAKER_00"}]}'):
            progress = MagicMock()

            latest, latest_name = _execute_enhancement(
                preprocess=False,
                restore=False,
                align=False,
                diarize=True,
                dual=False,
                model="base",
                latest=input_transcript,
                latest_name="transcript-base",
                wd=wd,
                progress=progress,
                verbose=False,
            )

    # Verify resumed without running diarization
    assert latest_name == "transcript-diarized-base"
    progress.complete_step.assert_called_once()


@patch("podx.utils.build_preprocess_command")
@patch("podx.utils.sanitize_model_name")
@patch("podx.orchestrate.logger")
@patch("podx.orchestrate._run")
def test_full_pipeline_preprocess_align_diarize(mock_run, mock_logger, mock_sanitize, mock_build_cmd):
    """Test full enhancement pipeline with all steps."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}
    mock_sanitize.return_value = "base"
    mock_build_cmd.return_value = ["podx-preprocess", "--output", "file.json"]

    preprocessed = {"asr_model": "base", "preprocessed": True}
    aligned = {"asr_model": "base", "preprocessed": True, "words": []}
    diarized = {"asr_model": "base", "preprocessed": True, "words": [], "speaker": "SPEAKER_00"}

    mock_run.side_effect = [preprocessed, aligned, diarized]

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        latest, latest_name = _execute_enhancement(
            preprocess=True,
            restore=False,
            align=True,
            diarize=True,
            dual=False,
            model="base",
            latest=input_transcript,
            latest_name="transcript-base",
            wd=wd,
            progress=progress,
            verbose=False,
        )

    # Verify all three steps ran
    assert mock_run.call_count == 3
    assert latest == diarized
    assert latest_name == "transcript-diarized-base"

    # Verify progress tracking for each step
    assert progress.start_step.call_count == 3
    assert progress.complete_step.call_count == 3


@patch("podx.utils.build_preprocess_command")
@patch("podx.utils.sanitize_model_name")
@patch("podx.orchestrate._run")
def test_progress_tracking(mock_run, mock_sanitize, mock_build_cmd):
    """Test that progress callbacks are called correctly."""
    # Setup
    wd = Path("/tmp/test")
    input_transcript = {"asr_model": "base", "segments": []}
    mock_sanitize.return_value = "base"
    mock_build_cmd.return_value = ["podx-preprocess"]

    preprocessed = {"asr_model": "base", "preprocessed": True}
    mock_run.return_value = preprocessed

    progress = MagicMock()

    _execute_enhancement(
        preprocess=True,
        restore=False,
        align=False,
        diarize=False,
        dual=False,
        model="base",
        latest=input_transcript,
        latest_name="transcript-base",
        wd=wd,
        progress=progress,
        verbose=False,
    )

    # Verify progress callbacks
    progress.start_step.assert_called_once()
    start_call = progress.start_step.call_args[0][0]
    assert "Preprocessing" in start_call

    progress.complete_step.assert_called_once()
    complete_call = progress.complete_step.call_args[0][0]
    assert "completed" in complete_call.lower()
