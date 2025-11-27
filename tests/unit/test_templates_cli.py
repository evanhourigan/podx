"""Tests for templates CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from podx.cli.templates import main as templates_cli
from podx.templates.manager import DeepcastTemplate, TemplateManager


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

    def test_list_templates_table_format(self, runner, mock_manager):
        """Test listing templates in table format."""
        result = runner.invoke(templates_cli, ["list"])

        assert result.exit_code == 0
        # Check that built-in templates are listed
        assert "interview-1on1" in result.output
        assert "solo-commentary" in result.output
        assert "panel-discussion" in result.output

    def test_list_templates_json_format(self, runner, mock_manager):
        """Test listing templates in JSON format."""
        result = runner.invoke(templates_cli, ["list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 11  # All 11 built-in templates

        # Verify structure
        template_names = {t["name"] for t in data}
        assert "general" in template_names
        assert "interview-1on1" in template_names
        assert "solo-commentary" in template_names

        # Verify required fields
        for template in data:
            assert "name" in template
            assert "description" in template
            assert "format" in template
            assert "variables" in template

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

    # ========================================================================
    # Preview Command Tests
    # ========================================================================

    def test_preview_with_sample_data(self, runner, mock_manager):
        """Test preview command with sample data."""
        result = runner.invoke(
            templates_cli, ["preview", "interview-1on1", "--sample"]
        )

        assert result.exit_code == 0
        assert "Template Preview" in result.output
        assert "System Prompt" in result.output
        assert "User Prompt" in result.output
        assert "interview-1on1" in result.output

    def test_preview_with_individual_options(self, runner, mock_manager, temp_dir):
        """Test preview with individual CLI options."""
        # Create sample transcript file
        transcript_file = temp_dir / "transcript.txt"
        transcript_file.write_text("This is a sample transcript.")

        result = runner.invoke(
            templates_cli,
            [
                "preview",
                "interview-1on1",
                "--title",
                "Test Episode",
                "--show",
                "Test Show",
                "--duration",
                "45",
                "--transcript",
                str(transcript_file),
                "--speakers",
                "Host, Guest",
            ],
        )

        assert result.exit_code == 0
        assert "Test Episode" in result.output
        assert "Test Show" in result.output
        assert "This is a sample transcript" in result.output

    def test_preview_with_vars_json(self, runner, mock_manager, temp_dir):
        """Test preview with JSON variables file."""
        # Create variables JSON file
        vars_file = temp_dir / "vars.json"
        vars_data = {
            "title": "JSON Episode",
            "show": "JSON Show",
            "duration": 60,
            "transcript": "JSON transcript content",
            "speakers": "Host, Guest",
        }
        vars_file.write_text(json.dumps(vars_data))

        result = runner.invoke(
            templates_cli,
            ["preview", "interview-1on1", "--vars-json", str(vars_file)],
        )

        assert result.exit_code == 0
        assert "JSON Episode" in result.output
        assert "JSON Show" in result.output

    def test_preview_with_cost_estimation(self, runner, mock_manager):
        """Test preview with cost estimation."""
        result = runner.invoke(
            templates_cli, ["preview", "interview-1on1", "--sample", "--cost"]
        )

        assert result.exit_code == 0
        assert "Cost Estimation" in result.output
        assert "tokens" in result.output.lower()
        assert "$" in result.output

    def test_preview_missing_vars_json_file(self, runner, mock_manager):
        """Test preview with nonexistent JSON file."""
        result = runner.invoke(
            templates_cli,
            ["preview", "interview-1on1", "--vars-json", "/nonexistent/vars.json"],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    # ========================================================================
    # Export Command Tests
    # ========================================================================

    def test_export_template_to_stdout(self, runner, mock_manager):
        """Test exporting template to stdout."""
        result = runner.invoke(templates_cli, ["export", "interview-1on1"])

        assert result.exit_code == 0
        assert "name: interview-1on1" in result.output
        assert "description:" in result.output
        assert "system_prompt:" in result.output
        assert "user_prompt:" in result.output
        assert "format:" in result.output

    def test_export_template_to_file(self, runner, mock_manager, temp_dir):
        """Test exporting template to file."""
        output_file = temp_dir / "exported.yaml"

        result = runner.invoke(
            templates_cli, ["export", "interview-1on1", "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "name: interview-1on1" in content
        assert "format:" in content

    def test_export_nonexistent_template(self, runner, mock_manager):
        """Test exporting nonexistent template."""
        result = runner.invoke(templates_cli, ["export", "nonexistent"])

        assert result.exit_code != 0

    # ========================================================================
    # Import Command Tests
    # ========================================================================

    def test_import_template_from_file(self, runner, mock_manager, temp_dir):
        """Test importing template from file."""
        # Create template YAML file
        template_file = temp_dir / "custom.yaml"
        yaml_content = """
name: custom-template
description: Custom imported template
format: custom
system_prompt: System {{var1}}
user_prompt: User {{var2}}
variables:
  - var1
  - var2
output_format: markdown
"""
        template_file.write_text(yaml_content)

        result = runner.invoke(templates_cli, ["import", str(template_file)])

        assert result.exit_code == 0
        assert "imported" in result.output.lower()
        assert "custom-template" in result.output

    def test_import_template_from_nonexistent_file(self, runner, mock_manager):
        """Test importing from nonexistent file."""
        result = runner.invoke(templates_cli, ["import", "/nonexistent/template.yaml"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_import_invalid_yaml(self, runner, mock_manager, temp_dir):
        """Test importing invalid YAML."""
        invalid_file = temp_dir / "invalid.yaml"
        invalid_file.write_text("{ this is not valid yaml")

        result = runner.invoke(templates_cli, ["import", str(invalid_file)])

        assert result.exit_code != 0

    # ========================================================================
    # Delete Command Tests
    # ========================================================================

    def test_delete_user_template_with_confirmation(self, runner, mock_manager):
        """Test deleting user template with confirmation."""
        # Create a user template
        template = DeepcastTemplate(
            name="user-deleteme",
            description="User template to delete",
            system_prompt="System",
            user_prompt="User",
        )
        mock_manager.save(template)

        # Delete with confirmation (auto-yes)
        result = runner.invoke(
            templates_cli, ["delete", "user-deleteme", "--yes"]
        )

        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_delete_builtin_template_fails(self, runner, mock_manager):
        """Test that deleting built-in template fails."""
        result = runner.invoke(
            templates_cli, ["delete", "interview-1on1", "--yes"]
        )

        assert result.exit_code != 0
        assert "cannot delete built-in" in result.output.lower()

    def test_delete_nonexistent_template(self, runner, mock_manager):
        """Test deleting nonexistent template."""
        result = runner.invoke(
            templates_cli, ["delete", "nonexistent", "--yes"]
        )

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    # ========================================================================
    # Integration Tests
    # ========================================================================

    def test_export_import_roundtrip(self, runner, mock_manager, temp_dir):
        """Test export → import roundtrip."""
        export_file = temp_dir / "exported.yaml"

        # Export built-in template
        result = runner.invoke(
            templates_cli, ["export", "interview-1on1", "--output", str(export_file)]
        )
        assert result.exit_code == 0

        # Modify the exported file to create a new template
        content = export_file.read_text()
        content = content.replace("name: interview-1on1", "name: custom-interview")
        export_file.write_text(content)

        # Import it back
        result = runner.invoke(templates_cli, ["import", str(export_file)])
        assert result.exit_code == 0

        # Verify it's listed
        result = runner.invoke(templates_cli, ["list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        template_names = {t["name"] for t in data}
        assert "custom-interview" in template_names

    def test_preview_all_builtin_templates(self, runner, mock_manager):
        """Test that all built-in templates can be previewed."""
        expected_templates = [
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
            result = runner.invoke(
                templates_cli, ["preview", template_name, "--sample"]
            )
            assert result.exit_code == 0, f"Failed to preview {template_name}"
            assert template_name in result.output

    def test_show_all_builtin_templates(self, runner, mock_manager):
        """Test that all built-in templates can be shown."""
        expected_templates = [
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
            assert result.exit_code == 0, f"Failed to show {template_name}"
            assert template_name in result.output
