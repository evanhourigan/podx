# 🔌 Podx Plugin Architecture

## Overview

Podx now features a comprehensive plugin architecture that allows users to extend the podcast processing pipeline with custom functionality. The plugin system provides standardized interfaces for different types of processing steps and includes built-in discovery, management, and CLI integration.

## Plugin Types

### 1. 🔍 Source Plugins (`PluginType.SOURCE`)

**Purpose**: Alternative content sources (replaces/extends `podx-fetch`)
**Interface**: `SourcePlugin`
**Examples**:

- YouTube downloader
- Spotify podcast fetcher
- Local file processor
- Live stream recorder

**Key Methods**:

- `fetch_episode(query)` → `EpisodeMeta`
- `supports_query(query)` → `bool`

### 2. 🎵 Audio Plugins (`PluginType.AUDIO`)

**Purpose**: Audio processing (replaces/extends `podx-transcode`)
**Interface**: `AudioPlugin`
**Examples**:

- Audio cleanup/enhancement
- Format converters beyond wav16/mp3/aac
- Audio compression/optimization

**Key Methods**:

- `process_audio(episode_meta, format, output_dir)` → `AudioMeta`
- `supported_formats()` → `List[str]`

### 3. 🎤 ASR Plugins (`PluginType.ASR`)

**Purpose**: Speech recognition (replaces/extends `podx-transcribe`)
**Interface**: `ASRPlugin`
**Examples**:

- Local Whisper variants
- Cloud ASR services (Azure, AWS)
- Specialized models (medical, legal)

**Key Methods**:

- `transcribe_audio(audio_meta, model, **kwargs)` → `Transcript`
- `available_models()` → `List[str]`

### 4. 🤖 Analysis Plugins (`PluginType.ANALYSIS`)

**Purpose**: AI analysis (replaces/extends `podx-deepcast`)
**Interface**: `AnalysisPlugin`
**Examples**:

- Anthropic Claude integration
- Local LLMs (Ollama, etc.)
- Specialized analysis (sentiment, topics)

**Key Methods**:

- `analyze_transcript(transcript, **kwargs)` → `DeepcastBrief`
- `supported_models()` → `List[str]`

### 5. 📤 Export Plugins (`PluginType.EXPORT`)

**Purpose**: Export formats (replaces/extends `podx-export`)
**Interface**: `ExportPlugin`
**Examples**:

- Custom subtitle formats
- Interactive transcripts
- PDF generation

**Key Methods**:

- `export_transcript(transcript, output_dir, formats)` → `Dict[str, Path]`
- `supported_formats()` → `List[str]`

### 6. 📢 Publish Plugins (`PluginType.PUBLISH`)

**Purpose**: Publishing destinations (replaces/extends `podx-notion`)
**Interface**: `PublishPlugin`
**Examples**:

- Slack integration
- Discord bot
- YouTube chapters
- Email summaries
- Custom webhooks

**Key Methods**:

- `publish_content(content, **kwargs)` → `Dict[str, Any]`
- `validate_credentials()` → `bool`

### 7. 🔧 Processing Plugins (`PluginType.PROCESSING`)

**Purpose**: Custom processing steps
**Interface**: `ProcessingPlugin`
**Examples**:

- Content moderation
- Language detection
- Custom data transformations

**Key Methods**:

- `process(data, **kwargs)` → `Dict[str, Any]`
- `input_schema()` → `Type`
- `output_schema()` → `Type`

## Plugin Discovery

Plugins are automatically discovered from:

1. **User plugins**: `~/.podx/plugins/`
2. **Project plugins**: `./plugins/`
3. **Built-in plugins**: `podx/builtin_plugins/`

## CLI Integration

### Plugin Management Commands

```bash
# List all available plugins
podx plugin list

# Filter by type
podx plugin list --type analysis

# Get detailed info about a plugin
podx plugin info anthropic-analysis

# Test plugin functionality
podx plugin test slack-publish

# Create new plugin template
podx plugin create my-plugin analysis --output-dir ./plugins

# Discover plugins from custom directories
podx plugin discover --dir /path/to/plugins
```

### Plugin Integration in Workflows

The plugin system is designed to seamlessly integrate with existing workflows. Future versions will include options like:

```bash
# Use specific plugins
podx run --source-plugin youtube-source --analysis-plugin anthropic-analysis
```

## Built-in Plugins

### 1. Anthropic Analysis (`anthropic-analysis`)

- **Type**: Analysis
- **Description**: AI transcript analysis using Claude models
- **Dependencies**: `anthropic`
- **Configuration**: API key, model selection, temperature

### 2. YouTube Source (`youtube-source`)

- **Type**: Source
- **Description**: Download YouTube videos as podcast episodes
- **Dependencies**: `yt-dlp`
- **Configuration**: Quality, format, output template

### 3. Slack Publish (`slack-publish`)

- **Type**: Publish
- **Description**: Publish summaries to Slack channels
- **Dependencies**: `slack-sdk`
- **Configuration**: Bot token, channels, formatting

## Creating Custom Plugins

### 1. Generate Template

```bash
podx plugin create my-custom-plugin analysis --output-dir ./plugins
```

### 2. Implement Interface

```python
from podx.plugins import AnalysisPlugin, PluginMetadata, PluginType

class MyCustomPlugin(AnalysisPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my-custom-plugin",
            version="1.0.0",
            description="My custom analysis plugin",
            author="Me",
            plugin_type=PluginType.ANALYSIS
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        # Validate configuration
        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        # Initialize plugin
        pass

    def analyze_transcript(self, transcript: Transcript, **kwargs) -> DeepcastBrief:
        # Implement analysis logic
        pass

    def supported_models(self) -> List[str]:
        return ["my-model-1", "my-model-2"]
```

### 3. Test Plugin

```bash
podx plugin test my-custom-plugin
```

## Plugin Configuration

Plugins use a standardized configuration schema:

```python
config_schema = {
    "api_key": {"type": "string", "required": True},
    "model": {"type": "string", "default": "default-model"},
    "temperature": {"type": "number", "default": 0.2, "min": 0, "max": 1}
}
```

Configuration is loaded from:

1. Environment variables
2. Configuration files
3. CLI arguments

## Architecture Benefits

### 🔧 Extensibility

- Add new functionality without modifying core code
- Support for any AI provider or output destination
- Easy integration of specialized tools

### 🔌 Modularity

- Clean separation of concerns
- Standardized interfaces
- Independent plugin development

### 🚀 Performance

- Plugins loaded on demand
- Configurable plugin discovery
- Efficient resource usage

### 👥 Community

- Plugin ecosystem for sharing
- Standard interfaces for compatibility
- Template generation for quick development

## Future Enhancements

1. **Plugin Registry**: Online registry for community plugins
2. **Hot Reloading**: Dynamic plugin loading/unloading
3. **Dependency Management**: Automatic dependency resolution
4. **Plugin Pipelines**: Chain multiple plugins together
5. **Configuration UI**: Web interface for plugin configuration
6. **Performance Monitoring**: Plugin execution metrics
7. **Plugin Sandboxing**: Security isolation for untrusted plugins

## Examples in Action

### YouTube to Slack Workflow

```bash
# 1. Download YouTube video
podx run --source-plugin youtube-source --url "https://youtube.com/watch?v=..."

# 2. Analyze with Claude
podx analyze --analysis-plugin anthropic-analysis --type tech

# 3. Publish to Slack
podx publish --publish-plugin slack-publish --channel "#tech-updates"
```

### Custom Processing Pipeline

```bash
# 1. Fetch podcast
podx fetch --show "The Podcast" --date 2024-01-15

# 2. Process with custom audio plugin
podx transcode --audio-plugin audio-enhancer --format enhanced-wav

# 3. Transcribe with specialized ASR
podx transcribe --asr-plugin medical-asr --model medical-v2

# 4. Export to custom format
podx export --export-plugin interactive-transcript --format html
```

The plugin architecture transforms podx from a fixed pipeline into a flexible, extensible platform for podcast processing innovation! 🎉
