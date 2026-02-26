"""Unit tests for ui.prompts module."""

from unittest.mock import patch

from podx.ui.prompts import _read_paste_continuation, prompt_optional


class TestReadPasteContinuation:
    """Test _read_paste_continuation helper."""

    def test_no_buffered_data(self):
        """Returns empty list when no data is buffered."""
        with patch("podx.ui.prompts.select") as mock_select:
            mock_select.select.return_value = ([], [], [])
            result = _read_paste_continuation()
            assert result == []

    def test_buffered_lines(self):
        """Reads multiple buffered lines from a paste."""
        import io

        fake_stdin = io.StringIO("line two\nline three\n")
        with (
            patch("podx.ui.prompts.select") as mock_select,
            patch("podx.ui.prompts.sys") as mock_sys,
        ):
            mock_sys.stdin = fake_stdin
            # First two calls have data, third does not
            mock_select.select.side_effect = [
                ([fake_stdin], [], []),
                ([fake_stdin], [], []),
                ([], [], []),
            ]
            result = _read_paste_continuation()
            assert result == ["line two", "line three"]

    def test_select_not_available(self):
        """Returns empty list when select raises OSError."""
        with patch("podx.ui.prompts.select") as mock_select:
            mock_select.select.side_effect = OSError("not supported")
            result = _read_paste_continuation()
            assert result == []


class TestPromptOptional:
    """Test prompt_optional function."""

    def test_single_line_input(self):
        """Single line input returns as-is."""
        with (
            patch("builtins.input", return_value="a simple question"),
            patch("podx.ui.prompts._read_paste_continuation", return_value=[]),
        ):
            result = prompt_optional("Question")
            assert result == "a simple question"

    def test_empty_input_returns_empty(self):
        """Enter with no input returns empty string."""
        with patch("builtins.input", return_value=""):
            result = prompt_optional("Question")
            assert result == ""

    def test_multiline_paste(self):
        """Multiline paste is captured and joined."""
        with (
            patch("builtins.input", return_value="first line"),
            patch(
                "podx.ui.prompts._read_paste_continuation",
                return_value=["second line", "third line"],
            ),
        ):
            result = prompt_optional("Question")
            assert result == "first line\nsecond line\nthird line"

    def test_multiline_paste_strips_trailing(self):
        """Trailing whitespace from multiline paste is stripped."""
        with (
            patch("builtins.input", return_value="first line"),
            patch(
                "podx.ui.prompts._read_paste_continuation",
                return_value=["second line", ""],
            ),
        ):
            result = prompt_optional("Question")
            assert result == "first line\nsecond line"
