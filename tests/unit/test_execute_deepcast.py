"""Unit tests for _execute_deepcast() helper function."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from podx.orchestrate import _execute_deepcast


def test_no_deepcast_returns_immediately():
    """Test that no deepcast flags returns immediately without processing."""
    # Setup
    wd = Path("/tmp/test")
    results = {}
    progress = MagicMock()

    # Call with both flags False
    _execute_deepcast(
        deepcast=False,
        dual=False,
        no_consensus=False,
        model="base",
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        yaml_analysis_type=None,
        extract_markdown=False,
        deepcast_pdf=False,
        wd=wd,
        results=results,
        progress=progress,
        verbose=False,
    )

    # Verify no processing occurred
    assert results == {}
    progress.start_step.assert_not_called()
    progress.complete_step.assert_not_called()


@patch("podx.utils.build_deepcast_command")
@patch("podx.orchestrate._run")
def test_single_mode_fresh_analysis(mock_run, mock_build_cmd):
    """Test single mode fresh analysis when no existing file."""
    # Setup
    wd = Path("/tmp/test")
    results = {}
    mock_build_cmd.return_value = ["podx-deepcast", "--model", "gpt-4"]

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=False,
            no_consensus=False,
            model="base",
            deepcast_model="gpt-4",
            deepcast_temp=0.7,
            yaml_analysis_type=None,
            extract_markdown=False,
            deepcast_pdf=False,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify analysis ran
    mock_run.assert_called_once()
    assert "deepcast_json" in results
    assert "deepcast-brief-gpt_4.json" in results["deepcast_json"]
    progress.start_step.assert_called_once()
    progress.complete_step.assert_called_once()


@patch("podx.orchestrate.logger")
def test_single_mode_resume_existing_file(mock_logger):
    """Test single mode resumes when existing deepcast file found."""
    # Setup
    wd = Path("/tmp/test")
    results = {}

    with patch("pathlib.Path.exists", return_value=True):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=False,
            no_consensus=False,
            model="base",
            deepcast_model="gpt-4",
            deepcast_temp=0.7,
            yaml_analysis_type=None,
            extract_markdown=False,
            deepcast_pdf=False,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify resumed without running analysis
    assert "deepcast_json" in results
    progress.complete_step.assert_called_once()
    complete_msg = progress.complete_step.call_args[0][0]
    assert "existing" in complete_msg.lower()
    mock_logger.info.assert_called()


@patch("podx.utils.build_deepcast_command")
@patch("podx.orchestrate._run")
def test_single_mode_with_markdown_extraction(mock_run, mock_build_cmd):
    """Test single mode with markdown extraction enabled."""
    # Setup
    wd = Path("/tmp/test")
    results = {}
    mock_build_cmd.return_value = ["podx-deepcast", "--extract-markdown"]

    def exists_side_effect(self):
        # JSON doesn't exist initially, but MD does after processing
        return "md" in str(self)

    with patch("pathlib.Path.exists", new=exists_side_effect):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=False,
            no_consensus=False,
            model="base",
            deepcast_model="gpt-4",
            deepcast_temp=0.7,
            yaml_analysis_type=None,
            extract_markdown=True,  # Enable markdown extraction
            deepcast_pdf=False,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify markdown file included in results
    assert "deepcast_json" in results
    assert "deepcast_md" in results
    assert ".md" in results["deepcast_md"]


@patch("podx.utils.build_deepcast_command")
@patch("podx.utils.sanitize_model_name")
@patch("podx.orchestrate._run")
def test_dual_mode_full_pipeline(mock_run, mock_sanitize, mock_build_cmd):
    """Test dual mode with precision, recall, agreement, and consensus."""
    # Setup
    wd = Path("/tmp/test")
    results = {}
    mock_sanitize.return_value = "large_v3"
    mock_build_cmd.return_value = ["podx-deepcast", "--model", "gpt-4"]

    # Mock preprocessed files exist
    def exists_side_effect(self):
        # Preprocessed files exist, deepcast outputs don't initially
        return "preprocessed" in str(self)

    with patch("pathlib.Path.exists", new=exists_side_effect):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=True,  # Enable dual mode
            no_consensus=False,
            model="large-v3",
            deepcast_model="gpt-4",
            deepcast_temp=0.7,
            yaml_analysis_type=None,
            extract_markdown=False,
            deepcast_pdf=False,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify all four steps ran: precision, recall, agreement, consensus
    assert mock_run.call_count == 4

    # Verify results contain all outputs
    assert "deepcast_precision" in results
    assert "deepcast_recall" in results
    assert "agreement" in results
    assert "consensus" in results

    # Verify progress tracking for each step
    assert progress.start_step.call_count == 3  # dual analyses, agreement, consensus
    assert progress.complete_step.call_count == 3


@patch("podx.utils.build_deepcast_command")
@patch("podx.utils.sanitize_model_name")
@patch("podx.orchestrate._run")
def test_dual_mode_no_consensus(mock_run, mock_sanitize, mock_build_cmd):
    """Test dual mode with consensus generation disabled."""
    # Setup
    wd = Path("/tmp/test")
    results = {}
    mock_sanitize.return_value = "large_v3"
    mock_build_cmd.return_value = ["podx-deepcast"]

    def exists_side_effect(self):
        return "preprocessed" in str(self)

    with patch("pathlib.Path.exists", new=exists_side_effect):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=True,
            no_consensus=True,  # Skip consensus
            model="large-v3",
            deepcast_model="gpt-4",
            deepcast_temp=0.7,
            yaml_analysis_type=None,
            extract_markdown=False,
            deepcast_pdf=False,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify only 3 steps ran (no consensus)
    assert mock_run.call_count == 3

    # Verify consensus NOT in results
    assert "deepcast_precision" in results
    assert "deepcast_recall" in results
    assert "agreement" in results
    assert "consensus" not in results


@patch("podx.utils.sanitize_model_name")
def test_dual_mode_missing_prerequisites_raises_error(mock_sanitize):
    """Test dual mode raises error when preprocessed files missing."""
    from podx.errors import ValidationError

    # Setup
    wd = Path("/tmp/test")
    results = {}
    mock_sanitize.return_value = "large_v3"

    # Mock preprocessed files don't exist
    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        with pytest.raises(ValidationError) as exc_info:
            _execute_deepcast(
                deepcast=True,
                dual=True,
                no_consensus=False,
                model="large-v3",
                deepcast_model="gpt-4",
                deepcast_temp=0.7,
                yaml_analysis_type=None,
                extract_markdown=False,
                deepcast_pdf=False,
                wd=wd,
                results=results,
                progress=progress,
                verbose=False,
            )

    # Verify error message mentions missing prerequisites
    assert "preprocessed precision/recall" in str(exc_info.value).lower()


@patch("podx.utils.build_deepcast_command")
@patch("podx.orchestrate._run")
def test_progress_tracking(mock_run, mock_build_cmd):
    """Test that progress callbacks are called correctly."""
    # Setup
    wd = Path("/tmp/test")
    results = {}
    mock_build_cmd.return_value = ["podx-deepcast"]

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=False,
            no_consensus=False,
            model="base",
            deepcast_model="gpt-4",
            deepcast_temp=0.7,
            yaml_analysis_type=None,
            extract_markdown=False,
            deepcast_pdf=False,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify progress callbacks
    progress.start_step.assert_called_once()
    start_msg = progress.start_step.call_args[0][0]
    assert "gpt-4" in start_msg

    progress.complete_step.assert_called_once()
    complete_msg = progress.complete_step.call_args[0][0]
    assert "completed" in complete_msg.lower()


@patch("podx.utils.build_deepcast_command")
@patch("podx.orchestrate._run")
def test_results_dict_updates(mock_run, mock_build_cmd):
    """Test that results dictionary is correctly updated."""
    # Setup
    wd = Path("/tmp/test")
    results = {"existing_key": "existing_value"}
    mock_build_cmd.return_value = ["podx-deepcast"]

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=False,
            no_consensus=False,
            model="base",
            deepcast_model="gpt-4o",
            deepcast_temp=0.5,
            yaml_analysis_type=None,
            extract_markdown=False,
            deepcast_pdf=False,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify existing keys preserved and new keys added
    assert "existing_key" in results
    assert results["existing_key"] == "existing_value"
    assert "deepcast_json" in results
    assert "deepcast-brief-gpt_4o.json" in results["deepcast_json"]


@patch("podx.utils.build_deepcast_command")
@patch("podx.orchestrate._run")
def test_deepcast_command_building(mock_run, mock_build_cmd):
    """Test that deepcast command is built with correct parameters."""
    # Setup
    wd = Path("/tmp/test")
    results = {}
    mock_build_cmd.return_value = ["podx-deepcast", "--model", "gpt-4"]

    with patch("pathlib.Path.exists", return_value=False):
        progress = MagicMock()

        _execute_deepcast(
            deepcast=True,
            dual=False,
            no_consensus=False,
            model="base",
            deepcast_model="gpt-4o-mini",
            deepcast_temp=0.3,
            yaml_analysis_type="detailed",
            extract_markdown=True,
            deepcast_pdf=True,
            wd=wd,
            results=results,
            progress=progress,
            verbose=False,
        )

    # Verify build_deepcast_command called with correct args
    mock_build_cmd.assert_called_once()
    call_kwargs = mock_build_cmd.call_args[1]
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["analysis_type"] == "detailed"
    assert call_kwargs["extract_markdown"] is True
    assert call_kwargs["generate_pdf"] is True
