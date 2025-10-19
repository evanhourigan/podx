# Podx Plugin System

The Podx plugin system provides a flexible architecture for extending podcast processing capabilities. Plugins can add new content sources, analysis methods, export formats, and publishing destinations.

## Table of Contents

- [Overview](#overview)
- [Using Plugins](#using-plugins)
- [Creating Custom Plugins](#creating-custom-plugins)
- [Plugin Types](#plugin-types)
- [Builtin Plugins](#builtin-plugins)
- [Plugin CLI](#plugin-cli)
- [Advanced Topics](#advanced-topics)

---

## Overview

### What are Plugins?

Plugins are modular components that extend Podx's core functionality. Each plugin implements a specific interface based on its type (source, analysis, publish, etc.) and can be:

- **Discovered automatically** from directories or pip packages
- **Configured** via JSON or YAML files
- **Validated** before use to check dependencies and credentials
- **Developed** easily using templates and CLI tools

### Plugin Architecture

```
┌─────────────────────────────────────────────┐
│          Podx Plugin System                 │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐    ┌──────────────┐     │
│  │   Registry   │◄───┤   Manager    │     │
│  └──────────────┘    └──────────────┘     │
│         ▲                    │              │
│         │                    ▼              │
│    ┌────┴────────────────────────┐        │
│    │  Entry Points   Directory   │        │
│    │   Discovery     Discovery   │        │
│    └─────────────────────────────┘        │
│                                             │
│  ┌──────────────────────────────────────┐ │
│  │         Plugin Interfaces            │ │
│  ├──────────────────────────────────────┤ │
│  │  Source │ ASR │ Analysis │ Publish  │ │
│  │  Audio  │ Export │ Processing │...  │ │
│  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## Using Plugins

### Discovering Available Plugins

List all installed plugins:

```bash
podx plugin list
```

Filter by type:

```bash
podx plugin list --type source
podx plugin list --type publish
```

Get detailed information:

```bash
podx plugin list --verbose
```

### Validating a Plugin

Before using a plugin, validate it has all required dependencies:

```bash
podx plugin validate webhook-publish
```

With a configuration file:

```bash
podx plugin validate webhook-publish --config-file webhook-config.json
```

### Plugin Configuration

Most plugins require configuration. Create a JSON file with the required settings:

**webhook-config.json:**
```json
{
  "webhook_url": "https://example.com/webhook",
  "headers": {
    "Authorization": "Bearer YOUR_TOKEN"
  },
  "timeout": 30
}
```

### Installing Third-Party Plugins

Plugins can be installed via pip if they register the `podx.plugins` entry point:

```bash
pip install podx-plugin-custom-source
```

Podx will automatically discover them on next run.

---

## Creating Custom Plugins

### Quick Start

Create a plugin template:

```bash
podx plugin create my_custom source --output-dir ./plugins
```

This generates `my_custom_plugin.py` with the basic structure.

### Plugin Structure

Every plugin must:

1. Inherit from a plugin interface class
2. Implement required abstract methods
3. Provide metadata via the `metadata` property

**Example: Simple Source Plugin**

```python
from pathlib import Path
from typing import Dict, Any
from podx.plugins import SourcePlugin, PluginMetadata, PluginType
from podx.schemas import EpisodeMeta

class MyCustomSourcePlugin(SourcePlugin):
    """Download podcasts from my custom source."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my-custom-source",
            version="1.0.0",
            description="Download podcasts from custom API",
            author="Your Name",
            plugin_type=PluginType.SOURCE,
            dependencies=["requests"],
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration has required fields."""
        return "api_key" in config and "base_url" in config

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize with configuration."""
        self.api_key = config["api_key"]
        self.base_url = config["base_url"]
        self.initialized = True

    def fetch_episode(self, query: Dict[str, Any]) -> EpisodeMeta:
        """Fetch episode from custom source."""
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        # Your implementation here
        episode_id = query.get("episode_id")

        # Call your API, download audio, etc.
        # ...

        return {
            "show": "My Podcast",
            "episode_title": "Episode Title",
            "audio_path": "/path/to/downloaded/audio.mp3",
            # ... other metadata
        }

    def supports_query(self, query: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the query."""
        return "episode_id" in query
```

### Installing Your Plugin

**Option 1: Directory Installation**

Place your plugin in one of these directories:
- `~/.podx/plugins/` (user plugins)
- `./plugins/` (project-specific)
- Package installation directory

**Option 2: Pip Package with Entry Points**

Create a `setup.py`:

```python
from setuptools import setup

setup(
    name="podx-plugin-my-custom",
    version="1.0.0",
    py_modules=["my_custom_plugin"],
    install_requires=["podx", "requests"],
    entry_points={
        "podx.plugins": [
            "my-custom = my_custom_plugin:MyCustomSourcePlugin",
        ],
    },
)
```

Then install:

```bash
pip install -e .  # Development mode
# or
pip install .     # Install
```

---

## Plugin Types

### 1. SOURCE - Content Sources

Fetch podcast episodes from different platforms.

**Interface:** `SourcePlugin`

**Required Methods:**
- `fetch_episode(query) -> EpisodeMeta` - Download and return episode metadata
- `supports_query(query) -> bool` - Check if plugin can handle the query

**Examples:**
- YouTube downloader
- Dropbox file fetcher
- Google Drive downloader
- RSS feed with custom authentication

### 2. AUDIO - Audio Processing

Process and transcode audio files.

**Interface:** `AudioPlugin`

**Required Methods:**
- `process_audio(episode_meta, target_format, output_dir) -> AudioMeta`
- `supported_formats() -> List[str]`

**Examples:**
- Custom audio filters
- Noise reduction
- Audio normalization

### 3. ASR - Speech Recognition

Transcribe audio to text.

**Interface:** `ASRPlugin`

**Required Methods:**
- `transcribe_audio(audio_meta, model, **kwargs) -> Transcript`
- `available_models() -> List[str]`

**Examples:**
- Custom ASR service integration
- Cloud ASR providers (Azure, AWS)
- Specialized domain models

### 4. ANALYSIS - AI Analysis

Analyze transcripts and generate insights.

**Interface:** `AnalysisPlugin`

**Required Methods:**
- `analyze_transcript(transcript, **kwargs) -> DeepcastBrief`
- `supported_models() -> List[str]`

**Examples:**
- Custom LLM providers
- Domain-specific analysis
- Multi-model ensemble analysis

### 5. PUBLISH - Publishing Destinations

Publish processed content to various platforms.

**Interface:** `PublishPlugin`

**Required Methods:**
- `publish_content(content, **kwargs) -> Dict[str, Any]`
- `validate_credentials() -> bool`

**Examples:**
- Discord webhooks
- Slack channels
- Generic webhooks
- Custom CMS/blog platforms

### 6. EXPORT - Export Formats

Export transcripts to different formats.

**Interface:** `ExportPlugin`

**Required Methods:**
- `export_transcript(transcript, output_dir, formats) -> Dict[str, Path]`
- `supported_formats() -> List[str]`

**Examples:**
- DOCX exporter
- LaTeX exporter
- Custom XML formats

### 7. PROCESSING - Custom Processing

Generic processing steps.

**Interface:** `ProcessingPlugin`

**Required Methods:**
- `process(data, **kwargs) -> Dict[str, Any]`
- `input_schema() -> Type`
- `output_schema() -> Type`

**Examples:**
- Custom data transformations
- Quality checks
- Metadata enrichment

---

## Builtin Plugins

### Source Plugins

#### YouTube Source
Download podcasts from YouTube videos.

**Name:** `youtube-source`

**Configuration:**
```json
{
  "quality": "bestaudio",
  "format": "mp3",
  "output_template": "%(title)s.%(ext)s"
}
```

**Dependencies:** `yt-dlp`

#### Dropbox Source
Download audio files from Dropbox.

**Name:** `dropbox-source`

**Configuration:**
```json
{
  "access_token": "YOUR_DROPBOX_TOKEN"
}
```

**Dependencies:** `dropbox`

**Features:**
- OAuth authentication
- Folder listing
- Automatic sharing links

#### Google Drive Source
Download audio files from Google Drive.

**Name:** `gdrive-source`

**Configuration:**
```json
{
  "credentials_file": "path/to/credentials.json",
  "token_file": "~/.podx/gdrive_token.json"
}
```

**Dependencies:** `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

**Features:**
- OAuth and service account auth
- File ID and URL support
- Folder listing

### Publish Plugins

#### Slack Publisher
Publish to Slack channels.

**Name:** `slack-publish`

**Configuration:**
```json
{
  "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "channel": "#podcast-updates",
  "username": "Podx Bot"
}
```

**Dependencies:** `requests`

#### Discord Publisher
Publish to Discord channels via webhooks.

**Name:** `discord-publish`

**Configuration:**
```json
{
  "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK",
  "username": "Podx Bot",
  "format": "embed"
}
```

**Dependencies:** `requests`

**Features:**
- Rich embeds with metadata
- Text and file formats
- Custom bot avatar

#### Webhook Publisher
Generic webhook publisher.

**Name:** `webhook-publish`

**Configuration:**
```json
{
  "webhook_url": "https://example.com/webhook",
  "headers": {
    "Authorization": "Bearer TOKEN",
    "Custom-Header": "value"
  },
  "timeout": 30
}
```

**Dependencies:** `requests`

**Features:**
- Custom HTTP headers
- Configurable timeout
- Flexible payload structure

### Analysis Plugins

#### Anthropic Analysis
AI analysis using Claude models.

**Name:** `anthropic-analysis`

**Configuration:**
```json
{
  "api_key": "YOUR_ANTHROPIC_API_KEY",
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 8192
}
```

**Dependencies:** `anthropic`

---

## Plugin CLI

### List Plugins

```bash
# List all plugins
podx plugin list

# Filter by type
podx plugin list --type source
podx plugin list --type publish

# Show detailed info
podx plugin list --verbose
```

**Output:**
```
🔌 Available Podx Plugins
┌─────────────────────┬──────────┬─────────┬──────────────────────────────┐
│ Name                │ Type     │ Version │ Description                  │
├─────────────────────┼──────────┼─────────┼──────────────────────────────┤
│ youtube-source      │ source   │ 1.0.0   │ Download YouTube videos      │
│ dropbox-source      │ source   │ 1.0.0   │ Download from Dropbox        │
│ webhook-publish     │ publish  │ 1.0.0   │ Publish to webhooks          │
│ discord-publish     │ publish  │ 1.0.0   │ Publish to Discord channels  │
└─────────────────────┴──────────┴─────────┴──────────────────────────────┘
```

### Validate Plugin

```bash
# Basic validation
podx plugin validate webhook-publish

# With configuration
podx plugin validate webhook-publish --config-file config.json
```

**Output:**
```
🔍 Validating plugin: webhook-publish

📦 Type: publish
📌 Version: 1.0.0
👤 Author: Podx Team
📝 Description: Publish transcripts and analysis to custom webhooks

📚 Checking dependencies...
  ✅ requests

⚙️  Validating configuration from: config.json
  ✅ Configuration is valid
  ✅ Plugin initialized successfully
  🔐 Testing credentials...
  ✅ Credentials validated

✅ Validation complete
```

### Create Plugin

```bash
# Create new plugin
podx plugin create my_awesome source --output-dir ./plugins
```

**Output:**
```
✅ Plugin template created: ./plugins/my_awesome_plugin.py

📝 Next steps:
  1. Edit the plugin file: ./plugins/my_awesome_plugin.py
  2. Implement required methods for source plugin
  3. Test your plugin with: podx plugin validate my_awesome
  4. Install your plugin in ~/.podx/plugins/ or use it locally
```

### List Plugin Types

```bash
podx plugin types
```

**Output:**
```
🔌 Podx Plugin Types
┌─────────────┬─────────────┬────────────────────────────────────────────┐
│ Type        │ Value       │ Description                                │
├─────────────┼─────────────┼────────────────────────────────────────────┤
│ SOURCE      │ source      │ Alternative content sources                │
│ ASR         │ asr         │ Speech recognition / transcription         │
│ ANALYSIS    │ analysis    │ AI analysis and insights                   │
│ PUBLISH     │ publish     │ Publishing to different platforms          │
│ EXPORT      │ export      │ Export to different formats                │
└─────────────┴─────────────┴────────────────────────────────────────────┘
```

---

## Advanced Topics

### Plugin Configuration Schema

Define a schema to validate configuration:

```python
config_schema = {
    "api_key": {
        "type": "string",
        "required": True,
        "description": "API key for authentication"
    },
    "timeout": {
        "type": "integer",
        "default": 30,
        "description": "Request timeout in seconds"
    },
    "features": {
        "type": "object",
        "properties": {
            "retry": {"type": "boolean", "default": True},
            "max_retries": {"type": "integer", "default": 3}
        }
    }
}
```

### Dependency Management

Plugins can specify dependencies that will be checked during validation:

```python
PluginMetadata(
    name="my-plugin",
    dependencies=["requests", "beautifulsoup4", "lxml"],
    # ...
)
```

Users will be warned if dependencies are missing.

### Error Handling

Best practices for error handling in plugins:

```python
from podx.errors import ValidationError, NetworkError

def fetch_episode(self, query):
    try:
        # Your code here
        pass
    except requests.exceptions.Timeout:
        raise NetworkError("Request timed out")
    except KeyError as e:
        raise ValidationError(f"Missing required field: {e}")
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        raise
```

### Testing Plugins

Create tests for your plugin:

```python
import pytest
from my_custom_plugin import MyCustomSourcePlugin

def test_plugin_metadata():
    plugin = MyCustomSourcePlugin()
    meta = plugin.metadata

    assert meta.name == "my-custom-source"
    assert meta.plugin_type == PluginType.SOURCE

def test_validate_config():
    plugin = MyCustomSourcePlugin()

    # Valid config
    assert plugin.validate_config({"api_key": "test", "base_url": "https://api.example.com"})

    # Invalid config
    assert not plugin.validate_config({"api_key": "test"})  # Missing base_url

def test_fetch_episode(mocker):
    plugin = MyCustomSourcePlugin()
    plugin.initialize({"api_key": "test", "base_url": "https://api.example.com"})

    # Mock external API call
    mocker.patch("requests.get", return_value=mock_response)

    result = plugin.fetch_episode({"episode_id": "123"})
    assert result["episode_title"] == "Expected Title"
```

### Plugin Distribution

#### PyPI Distribution

Create a complete package:

```
my-podx-plugin/
├── setup.py
├── README.md
├── LICENSE
├── my_plugin/
│   ├── __init__.py
│   └── plugin.py
└── tests/
    └── test_plugin.py
```

**setup.py:**
```python
from setuptools import setup, find_packages

setup(
    name="podx-plugin-myname",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "podx>=0.2.0",
        "requests",
    ],
    entry_points={
        "podx.plugins": [
            "myname = my_plugin.plugin:MyPlugin",
        ],
    },
    author="Your Name",
    description="My custom Podx plugin",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/podx-plugin-myname",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
```

Publish to PyPI:

```bash
python setup.py sdist bdist_wheel
twine upload dist/*
```

Users can then install:

```bash
pip install podx-plugin-myname
```

---

## Examples

### Example: Custom RSS Source with Authentication

```python
import requests
from typing import Dict, Any
from podx.plugins import SourcePlugin, PluginMetadata, PluginType
from podx.schemas import EpisodeMeta

class AuthenticatedRSSPlugin(SourcePlugin):
    """Fetch podcasts from authenticated RSS feeds."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="auth-rss-source",
            version="1.0.0",
            description="Download podcasts from authenticated RSS feeds",
            author="Your Name",
            plugin_type=PluginType.SOURCE,
            dependencies=["requests", "feedparser"],
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return all(k in config for k in ["rss_url", "username", "password"])

    def initialize(self, config: Dict[str, Any]) -> None:
        self.rss_url = config["rss_url"]
        self.auth = (config["username"], config["password"])
        self.initialized = True

    def fetch_episode(self, query: Dict[str, Any]) -> EpisodeMeta:
        import feedparser

        # Fetch authenticated RSS feed
        response = requests.get(self.rss_url, auth=self.auth)
        feed = feedparser.parse(response.content)

        # Find episode by date or title
        episode = self._find_episode(feed, query)

        # Download audio
        audio_url = episode.enclosures[0].href
        audio_path = self._download_audio(audio_url)

        return {
            "show": feed.feed.title,
            "episode_title": episode.title,
            "audio_path": audio_path,
            "release_date": episode.published,
            # ... more metadata
        }

    def supports_query(self, query: Dict[str, Any]) -> bool:
        return "date" in query or "title" in query
```

### Example: Multi-Platform Publisher

```python
from typing import Dict, Any, Union
from podx.plugins import PublishPlugin, PluginMetadata, PluginType
from podx.schemas import Transcript, DeepcastBrief

class MultiPlatformPublisher(PublishPlugin):
    """Publish to multiple platforms simultaneously."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="multi-publish",
            version="1.0.0",
            description="Publish to multiple platforms at once",
            author="Your Name",
            plugin_type=PluginType.PUBLISH,
            dependencies=["requests"],
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        return "platforms" in config and len(config["platforms"]) > 0

    def initialize(self, config: Dict[str, Any]) -> None:
        self.platforms = config["platforms"]
        self.initialized = True

    def publish_content(
        self, content: Union[Transcript, DeepcastBrief], **kwargs
    ) -> Dict[str, Any]:
        results = {}

        for platform in self.platforms:
            try:
                if platform["type"] == "discord":
                    result = self._publish_to_discord(content, platform)
                elif platform["type"] == "slack":
                    result = self._publish_to_slack(content, platform)
                elif platform["type"] == "webhook":
                    result = self._publish_to_webhook(content, platform)

                results[platform["name"]] = {
                    "success": True,
                    "result": result
                }
            except Exception as e:
                results[platform["name"]] = {
                    "success": False,
                    "error": str(e)
                }

        return {
            "platforms": results,
            "total": len(self.platforms),
            "successful": sum(1 for r in results.values() if r["success"])
        }

    def validate_credentials(self) -> bool:
        # Test each platform
        for platform in self.platforms:
            if not self._test_platform(platform):
                return False
        return True
```

---

## Troubleshooting

### Plugin Not Found

**Issue:** Plugin doesn't appear in `podx plugin list`

**Solutions:**
1. Check plugin is in correct directory (`~/.podx/plugins/`, `./plugins/`, or builtin)
2. Ensure plugin file doesn't start with `__`
3. Verify plugin class inherits from correct interface
4. Check for syntax errors: `python -m py_compile your_plugin.py`

### Dependencies Missing

**Issue:** Plugin validation fails with missing dependencies

**Solution:**
```bash
pip install dependency-name
```

Or install all dependencies from plugin metadata:
```python
# In your plugin
dependencies=["requests", "beautifulsoup4"]
```

### Configuration Invalid

**Issue:** Plugin fails to initialize

**Solutions:**
1. Validate JSON syntax: `python -m json.tool config.json`
2. Check all required fields are present
3. Use `podx plugin validate` to see specific errors

### Entry Point Not Working

**Issue:** Pip-installed plugin not discovered

**Solutions:**
1. Ensure entry point is registered in setup.py
2. Reinstall package: `pip install --force-reinstall package-name`
3. Check entry point group is `podx.plugins`

---

## Contributing Plugins

We welcome community plugins! To contribute:

1. **Follow the guidelines** in this document
2. **Test thoroughly** with `pytest`
3. **Document** your plugin with README and examples
4. **Submit PR** or publish to PyPI with `podx-plugin-*` name

For questions or support, visit: https://github.com/your-org/podx/discussions
