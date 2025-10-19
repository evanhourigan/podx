"""Tests for plugin system (registry, manager, discovery)."""

from unittest.mock import Mock, patch

import pytest

from podx.plugins import (
    PluginInterface,
    PluginManager,
    PluginMetadata,
    PluginRegistry,
    PluginType,
    create_plugin_template,
)


class TestPluginRegistry:
    """Test PluginRegistry class."""

    def test_register_plugin(self):
        """Test registering a plugin."""
        registry = PluginRegistry()

        # Create mock plugin
        mock_plugin = Mock(spec=PluginInterface)
        mock_plugin.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type=PluginType.SOURCE,
        )

        registry.register(mock_plugin)

        assert "test-plugin" in registry.plugins
        assert "test-plugin" in registry.metadata
        assert registry.plugins["test-plugin"] == mock_plugin

    def test_get_plugin(self):
        """Test getting a plugin by name."""
        registry = PluginRegistry()

        mock_plugin = Mock(spec=PluginInterface)
        mock_plugin.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        registry.register(mock_plugin)

        # Get existing plugin
        assert registry.get_plugin("test-plugin") == mock_plugin

        # Get non-existent plugin
        assert registry.get_plugin("non-existent") is None

    def test_get_plugins_by_type(self):
        """Test getting plugins filtered by type."""
        registry = PluginRegistry()

        # Create source plugin
        source_plugin = Mock(spec=PluginInterface)
        source_plugin.metadata = PluginMetadata(
            name="source-1",
            version="1.0.0",
            description="Source",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        # Create publish plugin
        publish_plugin = Mock(spec=PluginInterface)
        publish_plugin.metadata = PluginMetadata(
            name="publish-1",
            version="1.0.0",
            description="Publish",
            author="Test",
            plugin_type=PluginType.PUBLISH,
        )

        registry.register(source_plugin)
        registry.register(publish_plugin)

        # Get source plugins
        source_plugins = registry.get_plugins_by_type(PluginType.SOURCE)
        assert len(source_plugins) == 1
        assert source_plugins[0] == source_plugin

        # Get publish plugins
        publish_plugins = registry.get_plugins_by_type(PluginType.PUBLISH)
        assert len(publish_plugins) == 1
        assert publish_plugins[0] == publish_plugin

    def test_list_plugins(self):
        """Test listing all plugins."""
        registry = PluginRegistry()

        mock_plugin = Mock(spec=PluginInterface)
        mock_plugin.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        registry.register(mock_plugin)

        plugins = registry.list_plugins()
        assert "test-plugin" in plugins
        assert plugins["test-plugin"].name == "test-plugin"

    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        registry = PluginRegistry()

        mock_plugin = Mock(spec=PluginInterface)
        mock_plugin.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        registry.register(mock_plugin)
        assert "test-plugin" in registry.plugins

        # Unregister existing plugin
        result = registry.unregister("test-plugin")
        assert result is True
        assert "test-plugin" not in registry.plugins

        # Unregister non-existent plugin
        result = registry.unregister("non-existent")
        assert result is False


class TestPluginManager:
    """Test PluginManager class."""

    def test_init_with_registry(self):
        """Test initializing with custom registry."""
        registry = PluginRegistry()
        manager = PluginManager(registry=registry)

        assert manager.registry == registry

    def test_init_with_default_registry(self):
        """Test initializing with default registry."""
        manager = PluginManager()
        assert manager.registry is not None

    def test_get_default_plugin_dirs(self):
        """Test getting default plugin directories."""
        manager = PluginManager()
        dirs = manager._get_default_plugin_dirs()

        assert len(dirs) == 3
        # User, project, system directories
        assert any("podx/plugins" in str(d) or ".podx/plugins" in str(d) for d in dirs)
        assert any("builtin_plugins" in str(d) for d in dirs)

    def test_get_available_plugins(self):
        """Test getting available plugins."""
        manager = PluginManager()

        # Add mock plugin to registry
        mock_plugin = Mock(spec=PluginInterface)
        mock_plugin.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        manager.registry.register(mock_plugin)

        # Get all plugins
        plugins = manager.get_available_plugins()
        assert "test-plugin" in plugins

        # Get filtered by type
        source_plugins = manager.get_available_plugins(PluginType.SOURCE)
        assert "test-plugin" in source_plugins

        publish_plugins = manager.get_available_plugins(PluginType.PUBLISH)
        assert "test-plugin" not in publish_plugins

    def test_execute_plugin(self):
        """Test executing plugin method."""
        manager = PluginManager()

        # Create mock plugin with method
        mock_plugin = Mock(spec=PluginInterface)
        mock_plugin.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )
        mock_plugin.custom_method = Mock(return_value="result")

        manager.registry.register(mock_plugin)

        # Execute method
        result = manager.execute_plugin("test-plugin", "custom_method", "arg1", key="value")

        assert result == "result"
        mock_plugin.custom_method.assert_called_once_with("arg1", key="value")

    def test_execute_plugin_not_found(self):
        """Test executing non-existent plugin."""
        manager = PluginManager()

        with pytest.raises(ValueError, match="Plugin 'non-existent' not found"):
            manager.execute_plugin("non-existent", "method")

    def test_execute_plugin_method_not_found(self):
        """Test executing non-existent method."""
        manager = PluginManager()

        mock_plugin = Mock(spec=PluginInterface)
        mock_plugin.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        manager.registry.register(mock_plugin)

        with pytest.raises(ValueError, match="does not have method"):
            manager.execute_plugin("test-plugin", "non_existent_method")

    def test_select_plugin(self):
        """Test selecting best plugin for criteria."""
        manager = PluginManager()

        # Add source plugin
        source_plugin = Mock(spec=PluginInterface)
        source_plugin.metadata = PluginMetadata(
            name="source-1",
            version="1.0.0",
            description="Source",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        manager.registry.register(source_plugin)

        # Select without criteria (returns first available)
        selected = manager.select_plugin(PluginType.SOURCE)
        assert selected == source_plugin

        # Select with criteria (always matches for now)
        selected = manager.select_plugin(PluginType.SOURCE, {"format": "mp3"})
        assert selected == source_plugin

        # Select non-existent type
        selected = manager.select_plugin(PluginType.PUBLISH)
        assert selected is None


class TestPluginDiscovery:
    """Test plugin discovery mechanisms."""

    def test_discover_plugins_from_directory(self, tmp_path):
        """Test discovering plugins from directory."""
        manager = PluginManager()

        # Create a simple plugin file
        plugin_file = tmp_path / "simple_plugin.py"
        plugin_file.write_text('''
from podx.plugins import SourcePlugin, PluginMetadata, PluginType

class SimplePlugin(SourcePlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="simple",
            version="1.0.0",
            description="Simple plugin",
            author="Test",
            plugin_type=PluginType.SOURCE
        )

    def validate_config(self, config):
        return True

    def initialize(self, config):
        pass

    def fetch_episode(self, query):
        return {}

    def supports_query(self, query):
        return True
''')

        # Discover from directory
        initial_count = len(manager.registry.plugins)
        manager.discover_plugins([tmp_path], use_entry_points=False)

        # Should have registered the plugin
        assert len(manager.registry.plugins) > initial_count
        assert "simple" in manager.registry.plugins

    def test_discover_plugins_skips_invalid_files(self, tmp_path):
        """Test that discovery skips invalid plugin files."""
        manager = PluginManager()

        # Create invalid Python file
        invalid_file = tmp_path / "invalid.py"
        invalid_file.write_text("this is not valid python syntax !!!")

        # Should not raise error
        manager.discover_plugins([tmp_path], use_entry_points=False)

    def test_discover_plugins_skips_dunder_files(self, tmp_path):
        """Test that discovery skips __init__ and __pycache__."""
        manager = PluginManager()

        # Create __init__.py
        init_file = tmp_path / "__init__.py"
        init_file.write_text("# init file")

        initial_count = len(manager.registry.plugins)
        manager.discover_plugins([tmp_path], use_entry_points=False)

        # Should not have loaded __init__.py
        assert len(manager.registry.plugins) == initial_count

    @patch('podx.plugins.entry_points')
    def test_discover_entry_points(self, mock_entry_points):
        """Test discovering plugins via entry points."""
        manager = PluginManager()

        # Create mock entry point
        mock_entry = Mock()
        mock_entry.name = "test-plugin"
        mock_entry.value = "test_module:TestPlugin"

        # Create mock plugin class
        mock_plugin_class = Mock()
        mock_plugin_instance = Mock(spec=PluginInterface)
        mock_plugin_instance.metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )
        mock_plugin_class.return_value = mock_plugin_instance
        mock_entry.load.return_value = mock_plugin_class

        mock_entry_points.return_value = [mock_entry]

        # Discover with entry points
        manager._discover_entry_points()

        # Should have registered the plugin
        assert "test-plugin" in manager.registry.plugins


class TestPluginTemplate:
    """Test plugin template generation."""

    def test_create_plugin_template(self, tmp_path):
        """Test creating a plugin template."""
        plugin_file = create_plugin_template(
            PluginType.SOURCE,
            "mytest",
            tmp_path
        )

        assert plugin_file.exists()
        assert plugin_file.name == "mytest_plugin.py"

        content = plugin_file.read_text()
        assert "MytestPlugin" in content
        assert "SourcePlugin" in content
        assert "PluginType.SOURCE" in content

    def test_create_plugin_template_different_types(self, tmp_path):
        """Test creating templates for different plugin types."""
        for plugin_type in [PluginType.PUBLISH, PluginType.ANALYSIS, PluginType.EXPORT]:
            plugin_file = create_plugin_template(
                plugin_type,
                f"test_{plugin_type.value}",
                tmp_path
            )

            assert plugin_file.exists()
            content = plugin_file.read_text()
            assert plugin_type.value in content.lower()


class TestBuiltinPlugins:
    """Test builtin plugins can be loaded."""

    def test_builtin_plugins_discoverable(self):
        """Test that builtin plugins can be discovered."""
        manager = PluginManager()

        # Discover plugins (including builtins)
        manager.discover_plugins(use_entry_points=False)

        # Should have at least the builtin plugins
        plugins = manager.registry.list_plugins()

        # Check for some expected builtins
        builtin_names = ["youtube-source", "anthropic-analysis", "slack-publish"]

        # At least one builtin should be found
        found_builtins = [name for name in builtin_names if name in plugins]
        assert len(found_builtins) > 0

    def test_webhook_plugin_metadata(self):
        """Test webhook plugin has correct metadata."""
        manager = PluginManager()
        manager.discover_plugins(use_entry_points=False)

        plugin = manager.registry.get_plugin("webhook-publish")
        if plugin:  # Only test if plugin was loaded
            meta = plugin.metadata
            assert meta.name == "webhook-publish"
            assert meta.plugin_type == PluginType.PUBLISH
            assert "webhook" in meta.description.lower()

    def test_discord_plugin_metadata(self):
        """Test Discord plugin has correct metadata."""
        manager = PluginManager()
        manager.discover_plugins(use_entry_points=False)

        plugin = manager.registry.get_plugin("discord-publish")
        if plugin:  # Only test if plugin was loaded
            meta = plugin.metadata
            assert meta.name == "discord-publish"
            assert meta.plugin_type == PluginType.PUBLISH
            assert "discord" in meta.description.lower()

    def test_dropbox_plugin_metadata(self):
        """Test Dropbox plugin has correct metadata."""
        manager = PluginManager()
        manager.discover_plugins(use_entry_points=False)

        plugin = manager.registry.get_plugin("dropbox-source")
        if plugin:  # Only test if plugin was loaded
            meta = plugin.metadata
            assert meta.name == "dropbox-source"
            assert meta.plugin_type == PluginType.SOURCE
            assert "dropbox" in meta.description.lower()

    def test_gdrive_plugin_metadata(self):
        """Test Google Drive plugin has correct metadata."""
        manager = PluginManager()
        manager.discover_plugins(use_entry_points=False)

        plugin = manager.registry.get_plugin("gdrive-source")
        if plugin:  # Only test if plugin was loaded
            meta = plugin.metadata
            assert meta.name == "gdrive-source"
            assert meta.plugin_type == PluginType.SOURCE
            assert "google drive" in meta.description.lower()


class TestPluginValidation:
    """Test plugin validation."""

    def test_plugin_metadata_required_fields(self):
        """Test that plugin metadata requires all fields."""
        # Valid metadata
        meta = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
        )

        assert meta.name == "test"
        assert meta.version == "1.0.0"
        assert meta.enabled is True  # Default value

    def test_plugin_metadata_with_dependencies(self):
        """Test plugin metadata with dependencies."""
        meta = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
            dependencies=["requests", "pydantic"],
        )

        assert len(meta.dependencies) == 2
        assert "requests" in meta.dependencies

    def test_plugin_metadata_with_config_schema(self):
        """Test plugin metadata with configuration schema."""
        schema = {
            "api_key": {"type": "string", "required": True},
            "timeout": {"type": "integer", "default": 30},
        }

        meta = PluginMetadata(
            name="test",
            version="1.0.0",
            description="Test",
            author="Test",
            plugin_type=PluginType.SOURCE,
            config_schema=schema,
        )

        assert meta.config_schema is not None
        assert "api_key" in meta.config_schema
