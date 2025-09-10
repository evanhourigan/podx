#!/usr/bin/env python3
"""
Plugin system for podx - extensible podcast processing pipeline.

This module provides a flexible plugin architecture that allows users to extend
podx with custom processing steps, AI providers, output formats, and integrations.
"""

import importlib
import importlib.util
import inspect
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union

import click

from .config import get_config
from .logging import get_logger
from .schemas import AudioMeta, DeepcastBrief, EpisodeMeta, Transcript

logger = get_logger(__name__)


class PluginType(Enum):
    """Types of plugins in the podx pipeline."""

    SOURCE = "source"  # P1: Alternative content sources (fetch)
    AUDIO = "audio"  # P2: Audio processing (transcode)
    ASR = "asr"  # P3: Speech recognition (transcribe)
    ALIGNMENT = "alignment"  # P4: Timing alignment (align)
    DIARIZATION = "diarization"  # P5: Speaker identification (diarize)
    EXPORT = "export"  # P6: Export formats (export)
    ANALYSIS = "analysis"  # P7: AI analysis (deepcast)
    PUBLISH = "publish"  # P8: Publishing destinations (notion)
    PROCESSING = "processing"  # Custom processing steps


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""

    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    enabled: bool = True


class PluginInterface(ABC):
    """Base interface for all podx plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        pass

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        pass


class SourcePlugin(PluginInterface):
    """Plugin interface for content sources (replaces fetch)."""

    @abstractmethod
    def fetch_episode(self, query: Dict[str, Any]) -> EpisodeMeta:
        """
        Fetch episode metadata and download content.

        Args:
            query: Search parameters (show, date, url, etc.)

        Returns:
            EpisodeMeta with downloaded content information
        """
        pass

    @abstractmethod
    def supports_query(self, query: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the given query."""
        pass


class AudioPlugin(PluginInterface):
    """Plugin interface for audio processing (replaces transcode)."""

    @abstractmethod
    def process_audio(
        self, episode_meta: EpisodeMeta, target_format: str, output_dir: Path
    ) -> AudioMeta:
        """
        Process/convert audio to target format.

        Args:
            episode_meta: Episode metadata with audio file
            target_format: Target audio format
            output_dir: Output directory for processed audio

        Returns:
            AudioMeta with processed audio information
        """
        pass

    @abstractmethod
    def supported_formats(self) -> List[str]:
        """Return list of supported output formats."""
        pass


class ASRPlugin(PluginInterface):
    """Plugin interface for speech recognition (replaces transcribe)."""

    @abstractmethod
    def transcribe_audio(
        self, audio_meta: AudioMeta, model: str, **kwargs
    ) -> Transcript:
        """
        Transcribe audio to text.

        Args:
            audio_meta: Audio metadata
            model: Model name/identifier
            **kwargs: Additional parameters

        Returns:
            Transcript with segments and metadata
        """
        pass

    @abstractmethod
    def available_models(self) -> List[str]:
        """Return list of available models."""
        pass


class AnalysisPlugin(PluginInterface):
    """Plugin interface for AI analysis (replaces deepcast)."""

    @abstractmethod
    def analyze_transcript(self, transcript: Transcript, **kwargs) -> DeepcastBrief:
        """
        Analyze transcript and generate insights.

        Args:
            transcript: Transcript to analyze
            **kwargs: Analysis parameters (model, temperature, etc.)

        Returns:
            DeepcastBrief with analysis results
        """
        pass

    @abstractmethod
    def supported_models(self) -> List[str]:
        """Return list of supported models."""
        pass


class ExportPlugin(PluginInterface):
    """Plugin interface for export formats."""

    @abstractmethod
    def export_transcript(
        self, transcript: Transcript, output_dir: Path, formats: List[str]
    ) -> Dict[str, Path]:
        """
        Export transcript to specified formats.

        Args:
            transcript: Transcript to export
            output_dir: Output directory
            formats: List of format names

        Returns:
            Dict mapping format names to output file paths
        """
        pass

    @abstractmethod
    def supported_formats(self) -> List[str]:
        """Return list of supported export formats."""
        pass


class PublishPlugin(PluginInterface):
    """Plugin interface for publishing destinations."""

    @abstractmethod
    def publish_content(
        self, content: Union[Transcript, DeepcastBrief], **kwargs
    ) -> Dict[str, Any]:
        """
        Publish content to destination.

        Args:
            content: Content to publish
            **kwargs: Publishing parameters

        Returns:
            Dict with publishing results (URLs, IDs, etc.)
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate credentials/access for publishing."""
        pass


class ProcessingPlugin(PluginInterface):
    """Plugin interface for custom processing steps."""

    @abstractmethod
    def process(self, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Process data with custom logic.

        Args:
            data: Input data
            **kwargs: Processing parameters

        Returns:
            Processed data
        """
        pass

    @abstractmethod
    def input_schema(self) -> Type:
        """Return expected input data schema."""
        pass

    @abstractmethod
    def output_schema(self) -> Type:
        """Return output data schema."""
        pass


@dataclass
class PluginRegistry:
    """Registry for managing plugins."""

    plugins: Dict[str, PluginInterface] = field(default_factory=dict)
    metadata: Dict[str, PluginMetadata] = field(default_factory=dict)

    def register(self, plugin: PluginInterface) -> None:
        """Register a plugin."""
        meta = plugin.metadata
        self.plugins[meta.name] = plugin
        self.metadata[meta.name] = meta
        logger.info("Plugin registered", name=meta.name, type=meta.plugin_type.value)

    def get_plugin(self, name: str) -> Optional[PluginInterface]:
        """Get plugin by name."""
        return self.plugins.get(name)

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInterface]:
        """Get all plugins of specified type."""
        return [
            plugin
            for plugin in self.plugins.values()
            if plugin.metadata.plugin_type == plugin_type
        ]

    def list_plugins(self) -> Dict[str, PluginMetadata]:
        """List all registered plugins."""
        return self.metadata.copy()

    def unregister(self, name: str) -> bool:
        """Unregister a plugin."""
        if name in self.plugins:
            del self.plugins[name]
            del self.metadata[name]
            logger.info("Plugin unregistered", name=name)
            return True
        return False


# Global plugin registry
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return _registry


class PluginManager:
    """Manages plugin discovery, loading, and execution."""

    def __init__(self, registry: PluginRegistry = None):
        self.registry = registry or get_registry()
        self.config = get_config()

    def discover_plugins(self, plugin_dirs: List[Path] = None) -> None:
        """
        Discover and load plugins from specified directories.

        Args:
            plugin_dirs: List of directories to search for plugins
        """
        if plugin_dirs is None:
            plugin_dirs = self._get_default_plugin_dirs()

        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists():
                continue

            logger.debug("Scanning for plugins", directory=str(plugin_dir))

            for plugin_file in plugin_dir.glob("*.py"):
                if plugin_file.name.startswith("__"):
                    continue

                try:
                    self._load_plugin_file(plugin_file)
                except Exception as e:
                    logger.warning(
                        "Failed to load plugin", file=str(plugin_file), error=str(e)
                    )

    def _get_default_plugin_dirs(self) -> List[Path]:
        """Get default plugin directories."""
        dirs = []

        # User plugins directory
        user_dir = Path.home() / ".podx" / "plugins"
        dirs.append(user_dir)

        # Project plugins directory
        project_dir = Path.cwd() / "plugins"
        dirs.append(project_dir)

        # System plugins directory (relative to podx installation)
        system_dir = Path(__file__).parent / "builtin_plugins"
        dirs.append(system_dir)

        return dirs

    def _load_plugin_file(self, plugin_file: Path) -> None:
        """Load a plugin from a Python file."""
        module_name = f"podx_plugin_{plugin_file.stem}"

        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {plugin_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find plugin classes in the module
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, PluginInterface)
                and obj != PluginInterface
                and not inspect.isabstract(obj)
            ):

                # Instantiate and register the plugin
                try:
                    plugin = obj()
                    self.registry.register(plugin)
                except Exception as e:
                    logger.warning(
                        "Failed to instantiate plugin", class_name=name, error=str(e)
                    )

    def get_available_plugins(
        self, plugin_type: PluginType = None
    ) -> Dict[str, PluginMetadata]:
        """Get available plugins, optionally filtered by type."""
        all_plugins = self.registry.list_plugins()

        if plugin_type is None:
            return all_plugins

        return {
            name: meta
            for name, meta in all_plugins.items()
            if meta.plugin_type == plugin_type
        }

    def execute_plugin(self, plugin_name: str, method: str, *args, **kwargs) -> Any:
        """
        Execute a method on a plugin.

        Args:
            plugin_name: Name of the plugin
            method: Method name to call
            *args, **kwargs: Arguments to pass to the method

        Returns:
            Method result
        """
        plugin = self.registry.get_plugin(plugin_name)
        if plugin is None:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        if not hasattr(plugin, method):
            raise ValueError(f"Plugin '{plugin_name}' does not have method '{method}'")

        try:
            return getattr(plugin, method)(*args, **kwargs)
        except Exception as e:
            logger.error(
                "Plugin execution failed",
                plugin=plugin_name,
                method=method,
                error=str(e),
            )
            raise

    def select_plugin(
        self, plugin_type: PluginType, criteria: Dict[str, Any] = None
    ) -> Optional[PluginInterface]:
        """
        Select the best plugin for a given type and criteria.

        Args:
            plugin_type: Type of plugin needed
            criteria: Selection criteria (e.g., supported formats, models)

        Returns:
            Selected plugin or None if no suitable plugin found
        """
        available = self.registry.get_plugins_by_type(plugin_type)

        if not available:
            return None

        # If no criteria, return the first available plugin
        if not criteria:
            return available[0]

        # Apply selection logic based on criteria
        for plugin in available:
            if self._matches_criteria(plugin, criteria):
                return plugin

        return None

    def _matches_criteria(
        self, plugin: PluginInterface, criteria: Dict[str, Any]
    ) -> bool:
        """Check if a plugin matches the given criteria."""
        # This can be extended with more sophisticated matching logic
        return True


# CLI integration helper
def plugin_option(plugin_type: PluginType, help_text: str = None):
    """
    Click option decorator for plugin selection.

    Args:
        plugin_type: Type of plugin to select from
        help_text: Help text for the option
    """

    def decorator(f):
        manager = PluginManager()
        available = manager.get_available_plugins(plugin_type)
        choices = list(available.keys()) if available else []

        if not help_text:
            help_text = f"Select {plugin_type.value} plugin"

        return click.option(
            f"--{plugin_type.value}-plugin",
            type=click.Choice(choices) if choices else str,
            help=help_text,
        )(f)

    return decorator


# Utility functions for plugin development
def create_plugin_template(
    plugin_type: PluginType, name: str, output_dir: Path
) -> Path:
    """
    Create a plugin template file.

    Args:
        plugin_type: Type of plugin to create
        name: Plugin name
        output_dir: Directory to create the plugin file

    Returns:
        Path to created template file
    """
    # Template content will be generated based on plugin type
    template_content = _generate_plugin_template(plugin_type, name)

    plugin_file = output_dir / f"{name}_plugin.py"
    plugin_file.write_text(template_content)

    return plugin_file


def _generate_plugin_template(plugin_type: PluginType, name: str) -> str:
    """Generate plugin template content."""
    base_template = f'''"""
{name} plugin for podx.

This plugin provides {plugin_type.value} functionality.
"""

from pathlib import Path
from typing import Dict, List, Any
from podx.plugins import {plugin_type.value.title()}Plugin, PluginMetadata, PluginType


class {name.title()}Plugin({plugin_type.value.title()}Plugin):
    """Custom {plugin_type.value} plugin."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="{name}",
            version="1.0.0",
            description="{name} {plugin_type.value} plugin",
            author="Your Name",
            plugin_type=PluginType.{plugin_type.name}
        )
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        # Implement configuration validation
        return True
    
    def initialize(self, config: Dict[str, Any]) -> None:
        # Initialize plugin with configuration
        pass
    
    # Implement required methods for {plugin_type.value} plugin
    # See documentation for specific method signatures
'''

    return base_template


if __name__ == "__main__":
    # Simple test
    manager = PluginManager()
    manager.discover_plugins()

    for name, meta in manager.get_available_plugins().items():
        print(f"Plugin: {name} ({meta.plugin_type.value}) - {meta.description}")
