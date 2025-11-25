"""Tests for custom deepcast templates."""

import tempfile
from pathlib import Path

import pytest

from podx.templates import TemplateError, TemplateManager
from podx.templates.manager import DeepcastTemplate


class TestDeepcastTemplate:
    """Test DeepcastTemplate."""

    def test_render_basic(self):
        """Test basic template rendering."""
        template = DeepcastTemplate(
            name="test",
            description="Test template",
            system_prompt="You are analyzing {{show}}",
            user_prompt="Analyze: {{title}}\n{{transcript}}",
            variables=["show", "title", "transcript"],
        )

        context = {
            "show": "Test Show",
            "title": "Episode 1",
            "transcript": "Hello world",
        }

        system, user = template.render(context)

        assert system == "You are analyzing Test Show"
        assert user == "Analyze: Episode 1\nHello world"

    def test_render_missing_variables(self):
        """Test rendering with missing variables."""
        template = DeepcastTemplate(
            name="test",
            description="Test template",
            system_prompt="System",
            user_prompt="User {{title}}",
            variables=["title", "duration"],
        )

        context = {"title": "Test"}  # Missing 'duration'

        with pytest.raises(TemplateError) as exc:
            template.render(context)

        assert "Missing required variables" in str(exc.value)
        assert "duration" in str(exc.value)

    def test_render_extra_variables(self):
        """Test rendering with extra variables (should be ignored)."""
        template = DeepcastTemplate(
            name="test",
            description="Test",
            system_prompt="System {{var1}}",
            user_prompt="User",
            variables=["var1"],
        )

        context = {
            "var1": "value1",
            "var2": "value2",  # Extra variable
        }

        system, user = template.render(context)
        assert system == "System value1"


class TestTemplateManager:
    """Test TemplateManager."""

    @pytest.fixture
    def temp_template_dir(self):
        """Create temporary template directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_template_dir):
        """Create template manager with temp directory."""
        return TemplateManager(template_dir=temp_template_dir)

    def test_get_builtin_templates(self, manager):
        """Test getting built-in templates."""
        builtins = manager.get_builtin_templates()

        # Verify all 10 new format-based templates exist
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
            assert template_name in builtins, f"Template {template_name} not found"

        # Verify structure
        assert builtins["interview-1on1"].name == "interview-1on1"
        assert len(builtins["interview-1on1"].variables) > 0

    def test_load_builtin_template(self, manager):
        """Test loading built-in template."""
        template = manager.load("interview-1on1")

        assert template.name == "interview-1on1"
        assert "title" in template.variables
        assert "transcript" in template.variables
        assert "speakers" in template.variables

    def test_load_nonexistent_template(self, manager):
        """Test loading nonexistent template."""
        with pytest.raises(TemplateError) as exc:
            manager.load("nonexistent")

        assert "not found" in str(exc.value).lower()

    def test_save_and_load_user_template(self, manager):
        """Test saving and loading user template."""
        template = DeepcastTemplate(
            name="custom",
            description="Custom template",
            system_prompt="Custom system {{var1}}",
            user_prompt="Custom user {{var2}}",
            variables=["var1", "var2"],
        )

        # Save
        manager.save(template)

        # Verify file exists
        template_file = manager.template_dir / "custom.yaml"
        assert template_file.exists()

        # Clear cache and reload
        manager._cache.clear()
        loaded = manager.load("custom")

        assert loaded.name == "custom"
        assert loaded.description == "Custom template"
        assert loaded.variables == ["var1", "var2"]

    def test_list_templates(self, manager):
        """Test listing templates."""
        # Initially only built-ins
        templates = manager.list_templates()
        assert "interview-1on1" in templates
        assert "solo-commentary" in templates
        assert "panel-discussion" in templates

        # Add user template
        custom = DeepcastTemplate(
            name="user-custom",
            description="User template",
            system_prompt="System",
            user_prompt="User",
        )
        manager.save(custom)

        # List should include user template
        templates = manager.list_templates()
        assert "user-custom" in templates

    def test_delete_user_template(self, manager):
        """Test deleting user template."""
        # Create and save template
        template = DeepcastTemplate(
            name="deleteme",
            description="To be deleted",
            system_prompt="System",
            user_prompt="User",
        )
        manager.save(template)

        # Verify it exists
        assert "deleteme" in manager.list_templates()

        # Delete it
        result = manager.delete("deleteme")
        assert result is True

        # Verify it's gone
        assert "deleteme" not in manager.list_templates()

    def test_delete_builtin_template_fails(self, manager):
        """Test that deleting built-in template raises error."""
        with pytest.raises(TemplateError) as exc:
            manager.delete("interview-1on1")

        assert "Cannot delete built-in" in str(exc.value)

    def test_delete_nonexistent_template(self, manager):
        """Test deleting nonexistent template."""
        result = manager.delete("nonexistent")
        assert result is False

    def test_export_template(self, manager):
        """Test exporting template as YAML."""
        yaml_str = manager.export("interview-1on1")

        assert "name: interview-1on1" in yaml_str
        assert "description:" in yaml_str
        assert "system_prompt:" in yaml_str
        assert "user_prompt:" in yaml_str
        assert "format:" in yaml_str

    def test_import_template(self, manager):
        """Test importing template from YAML."""
        yaml_content = """
name: imported
description: Imported template
system_prompt: System {{var1}}
user_prompt: User {{var2}}
variables:
  - var1
  - var2
output_format: markdown
"""

        template = manager.import_template(yaml_content)

        assert template.name == "imported"
        assert template.description == "Imported template"
        assert "var1" in template.variables
        assert "var2" in template.variables

        # Verify it was saved
        assert "imported" in manager.list_templates()

    def test_import_invalid_yaml(self, manager):
        """Test importing invalid YAML."""
        invalid_yaml = "{ this is not valid yaml"

        with pytest.raises(TemplateError):
            manager.import_template(invalid_yaml)

    def test_cache_functionality(self, manager):
        """Test that templates are cached."""
        # Load template twice
        template1 = manager.load("interview-1on1")
        template2 = manager.load("interview-1on1")

        # Should be same object (from cache)
        assert template1 is template2

    def test_builtin_template_variables(self, manager):
        """Test that built-in templates have correct variables."""
        # Test solo-commentary variables
        solo = manager.load("solo-commentary")
        assert set(solo.variables) == {"title", "show", "duration", "transcript"}

        # Test interview-1on1 variables
        interview = manager.load("interview-1on1")
        assert "speakers" in interview.variables
        assert "title" in interview.variables
        assert "transcript" in interview.variables

        # Test panel-discussion variables
        panel = manager.load("panel-discussion")
        assert "speaker_count" in panel.variables

    def test_builtin_template_format_field(self, manager):
        """Test that built-in templates have format field."""
        interview = manager.load("interview-1on1")
        assert interview.format == "interview"

        panel = manager.load("panel-discussion")
        assert panel.format == "panel"

        solo = manager.load("solo-commentary")
        assert solo.format == "solo"

    def test_all_templates_have_scaling_guidance(self, manager):
        """Test that all templates include length-adaptive scaling guidance."""
        builtins = manager.get_builtin_templates()

        for name, template in builtins.items():
            # Check that system prompt contains scaling guidance
            assert "Adapt your analysis depth based on episode length" in template.system_prompt, \
                f"Template {name} missing scaling guidance"
            assert "<30 minutes" in template.system_prompt, \
                f"Template {name} missing tier definitions"

    def test_template_rendering_with_duration(self, manager):
        """Test that templates render correctly with duration variable."""
        template = manager.load("interview-1on1")

        context = {
            "title": "Test Episode",
            "show": "Test Podcast",
            "duration": 45,
            "transcript": "Sample transcript content",
            "speakers": "Host, Guest",
        }

        system, user = template.render(context)

        # Verify variables are substituted
        assert "Test Episode" in user
        assert "Test Podcast" in user
        assert "45" in user
        assert "Sample transcript content" in user
        assert "Host, Guest" in user
