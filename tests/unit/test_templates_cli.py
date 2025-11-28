"""Tests for templates CLI commands - v4.0 simplified."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from podx.cli.templates import main as templates_cli
from podx.templates.manager import TemplateManager


class TestTemplatesCLI:
    """Test templates CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_manager(self, temp_dir):
        """Create mocked template manager."""
        with patch("podx.cli.templates.TemplateManager") as MockManager:
            manager = TemplateManager(template_dir=temp_dir)
            MockManager.return_value = manager
            yield manager

    # ========================================================================
    # List Command Tests
    # ========================================================================

    def test_list_templates(self, runner, mock_manager):
        """Test listing templates."""
        result = runner.invoke(templates_cli, ["list"])

        assert result.exit_code == 0
        # Check that built-in templates are listed
        assert "interview-1on1" in result.output
        assert "solo-commentary" in result.output
        assert "panel-discussion" in result.output
        assert "general" in result.output

    def test_list_shows_descriptions(self, runner, mock_manager):
        """Test that list shows template descriptions."""
        result = runner.invoke(templates_cli, ["list"])

        assert result.exit_code == 0
        assert "Available Templates" in result.output

    # ========================================================================
    # Show Command Tests
    # ========================================================================

    def test_show_template(self, runner, mock_manager):
        """Test showing template details."""
        result = runner.invoke(templates_cli, ["show", "interview-1on1"])

        assert result.exit_code == 0
        assert "interview-1on1" in result.output
        assert "Format:" in result.output
        assert "Variables:" in result.output
        assert "System Prompt" in result.output
        assert "User Prompt" in result.output

    def test_show_nonexistent_template(self, runner, mock_manager):
        """Test showing nonexistent template."""
        result = runner.invoke(templates_cli, ["show", "nonexistent"])

        assert result.exit_code != 0
        assert "Error" in result.output

    def test_show_general_template(self, runner, mock_manager):
        """Test showing the general template (default)."""
        result = runner.invoke(templates_cli, ["show", "general"])

        assert result.exit_code == 0
        assert "general" in result.output

    # ========================================================================
    # All Built-in Templates Tests
    # ========================================================================

    def test_show_all_builtin_templates(self, runner, mock_manager):
        """Test that all built-in templates can be shown."""
        expected_templates = [
            "general",
            "solo-commentary",
            "interview-1on1",
            "panel-discussion",
            "lecture-presentation",
            "debate-roundtable",
            "news-analysis",
            "case-study",
            "technical-deep-dive",
            "business-strategy",
            "research-review",
        ]

        for template_name in expected_templates:
            result = runner.invoke(templates_cli, ["show", template_name])
            assert result.exit_code == 0, f"Failed to show {template_name}: {result.output}"
            assert template_name in result.output

    # ========================================================================
    # Help Tests
    # ========================================================================

    def test_help_shows_subcommands(self, runner):
        """Test that help shows available subcommands."""
        result = runner.invoke(templates_cli, ["--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output

    def test_list_help(self, runner):
        """Test list subcommand help."""
        result = runner.invoke(templates_cli, ["list", "--help"])

        assert result.exit_code == 0
        assert "List available" in result.output

    def test_show_help(self, runner):
        """Test show subcommand help."""
        result = runner.invoke(templates_cli, ["show", "--help"])

        assert result.exit_code == 0
        assert "TEMPLATE_NAME" in result.output
