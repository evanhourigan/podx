# 🎯 Podx Usage Examples

Real-world examples of using podx for different podcast processing workflows.

## Quick Examples

### Basic Usage (No Configuration)

```bash
# Simple processing with manual flags
podx run --show "Lex Fridman Podcast" --date 2025-08-15 \
  --align --deepcast --extract-markdown --notion

# Process with specific model and temperature
podx run --show "The Tim Ferriss Show" --date 2025-08-10 \
  --deepcast --deepcast-model gpt-4.1 --deepcast-temp 0.1
```

### With YAML Configuration

```bash
# After setting up ~/.podx/config.yaml, these become simple:
podx run --show "Lenny's Podcast" --date 2025-08-17
podx run --show "Lex Fridman Podcast" --date 2025-08-15
podx run --show "Y Combinator Podcast" --date 2025-08-12

# All podcast-specific settings are applied automatically!
```

## Configuration Examples

### Product Manager Workflow

**Goal**: Process product management podcasts for work knowledge base

```yaml
# ~/.podx/config.yaml
version: "1.0"
environment: "production"

defaults:
  align: true
  deepcast: true
  extract_markdown: true
  notion: true

notion_databases:
  work:
    name: "Work Knowledge Base"
    database_id: "your-work-database-id"
    token: "your-work-notion-token"
    title_property: "Episode Title"
    date_property: "Published Date"
    tags_property: "Topics"

podcasts:
  product_management:
    names:
      - "Lenny's Podcast"
      - "Lenny's Newsletter"
      - "Product Hunt Radio"
      - "This is Product Management"
    analysis:
      type: "interview_guest_focused"
      temperature: 0.1  # Lower for factual content
      custom_prompts: |
        PRODUCT MANAGEMENT FOCUS:
        - Extract frameworks, methodologies, and best practices
        - Note specific metrics, KPIs, and success criteria
        - Include tool recommendations and resource mentions
        - Focus on career advice and growth strategies
        - Capture case studies and real-world examples
    pipeline:
      align: true
      deepcast: true
      extract_markdown: true
      notion: true
    notion_database: "work"
    description: "Product management content for work"
    tags: ["product", "growth", "strategy", "frameworks"]
```

**Usage**:
```bash
# All these automatically use the same configuration
podx run --show "Lenny's Podcast" --date 2025-08-17
podx run --show "Product Hunt Radio" --date 2025-08-15
podx run --show "This is Product Management" --date 2025-08-10
```

### Research & Learning Workflow

**Goal**: Process educational and research content for personal learning

```yaml
notion_databases:
  research:
    name: "Research & Learning"
    database_id: "research-database-id"
    token: "research-notion-token"
    title_property: "Research Topic"
    date_property: "Date Added"
    tags_property: "Research Areas"

  personal:
    name: "Personal Library"
    database_id: "personal-database-id"
    token: "personal-notion-token"

podcasts:
  deep_learning:
    names:
      - "Lex Fridman Podcast"
      - "The Knowledge Project"
      - "Conversations with Tyler"
      - "EconTalk"
    analysis:
      type: "interview_host_focused"  # Focus on thoughtful questions
      model: "gpt-4.1"  # Better model for complex topics
      temperature: 0.3   # Higher for creative insights
      custom_prompts: |
        RESEARCH & LEARNING FOCUS:
        - Extract academic insights and research findings
        - Note theoretical frameworks and methodologies
        - Include book/paper recommendations and citations
        - Focus on intellectual depth and novel ideas
        - Capture philosophical and ethical discussions
    pipeline:
      align: true
      diarize: true      # Often multiple speakers
      deepcast: true
      extract_markdown: true
      notion: false      # Manual review before upload
    notion_database: "research"
    tags: ["research", "learning", "academic"]

  entertainment:
    names:
      - "Conan O'Brien Needs a Friend"
      - "WTF with Marc Maron"
      - "Comedy Bang! Bang!"
    analysis:
      type: "comedy"
    pipeline:
      align: false       # Don't need precision for comedy
      deepcast: true
      extract_markdown: true
      notion: true
    notion_database: "personal"
    tags: ["entertainment", "comedy"]
```

### Multi-Environment Setup

**Goal**: Different settings for development vs production

```yaml
version: "1.0"
environment: "production"  # Change to "development" for dev settings

# Production settings
defaults:
  align: true
  deepcast: true
  extract_markdown: true
  notion: true
  clean: true  # Clean up files in production

analysis:
  model: "gpt-4.1"        # Better model for production
  temperature: 0.2        # Consistent results

# Development overrides (uncomment when environment: "development")
# defaults:
#   align: false           # Skip expensive alignment in dev
#   notion: false          # Don't upload to Notion in dev
#   clean: false           # Keep files for debugging
# 
# analysis:
#   model: "gpt-4.1-mini"  # Cheaper model for development
#   temperature: 0.5       # More creative for experimentation

notion_databases:
  production:
    database_id: "prod-database-id"
    token: "prod-notion-token"
  
  # development:
  #   database_id: "dev-database-id"
  #   token: "dev-notion-token"

podcasts:
  all_podcasts:
    names: ["*"]  # Catch-all pattern (future feature)
    notion_database: "production"  # or "development"
```

## Advanced Usage Patterns

### Batch Processing

```bash
# Process multiple episodes from the same show
for date in 2025-08-{10..17}; do
  podx run --show "Lenny's Podcast" --date "$date" || continue
done

# Process different shows with same date
for show in "Lenny's Podcast" "Lex Fridman Podcast" "Y Combinator Podcast"; do
  podx run --show "$show" --date "2025-08-15" || continue
done
```

### Pipeline Customization

```bash
# Just fetch and analyze (skip transcription)
podx fetch --show "Lenny's Podcast" --date 2025-08-17 | \
podx deepcast --output analysis.json --extract-markdown

# Custom pipeline with specific steps
podx run --show "Tech Podcast" --date 2025-08-15 \
  --align --deepcast --extract-markdown \
  --deepcast-model gpt-4.1 --deepcast-temp 0.1 \
  --no-notion  # Skip Notion upload
```

### RSS URL Processing

```bash
# Process from direct RSS URL
podx run --rss-url "https://feeds.example.com/podcast.rss" \
  --date 2025-08-15 --deepcast

# Private or unlisted feeds
podx run --rss-url "https://private-feed.com/secret-token/rss" \
  --title-contains "Episode 42"
```

## Plugin Usage Examples

### Using Alternative Analysis Plugins

```bash
# List available analysis plugins
podx plugin list --type analysis

# Use Anthropic Claude instead of OpenAI
podx run --show "Lex Fridman Podcast" --date 2025-08-15 \
  --plugin anthropic-analysis \
  --plugin-config model=claude-3-sonnet
```

### Custom Export Formats

```bash
# Use custom export plugin
podx plugin list --type export

# Export to custom format
podx run --show "Tech Podcast" --date 2025-08-15 \
  --plugin custom-export \
  --plugin-config format=interactive-transcript
```

## Troubleshooting Examples

### Configuration Issues

```bash
# Validate your configuration
podx config validate

# Check specific podcast mapping
podx podcast show "Lenny's Podcast"

# View all configured databases
podx config databases

# Test configuration without processing
podx run --show "Test Show" --date 2025-01-01 --dry-run  # Future feature
```

### Debug Processing

```bash
# Verbose output for debugging
podx run --show "Problematic Podcast" --date 2025-08-15 --verbose

# Keep intermediate files for inspection
podx run --show "Debug Show" --date 2025-08-15 --no-clean

# Process specific steps only
podx run --show "Test Show" --date 2025-08-15 --no-deepcast --no-notion
```

### Performance Optimization

```bash
# Use smaller model for faster processing
podx run --show "Long Podcast" --date 2025-08-15 \
  --model tiny.en --deepcast-model gpt-4.1-mini

# Skip expensive steps for quick testing
podx run --show "Test Show" --date 2025-08-15 \
  --no-align --no-diarize
```

## Integration Examples

### With External Tools

```bash
# Pipe to external analysis
podx run --show "Data Podcast" --date 2025-08-15 --deepcast | \
jq '.key_points[]' | \
while read -r point; do
  echo "Key Point: $point"
done

# Integration with note-taking apps
podx run --show "Learning Podcast" --date 2025-08-15 \
  --extract-markdown && \
cp "Learning Podcast/2025-08-15/brief.md" ~/Notes/
```

### Automation Scripts

```bash
#!/bin/bash
# daily-podcast-processor.sh

PODCASTS=(
  "Lenny's Podcast"
  "Y Combinator Podcast"
  "The Knowledge Project"
)

DATE=$(date -d "yesterday" +%Y-%m-%d)

for podcast in "${PODCASTS[@]}"; do
  echo "Processing $podcast for $DATE..."
  podx run --show "$podcast" --date "$DATE" || {
    echo "Failed to process $podcast"
    continue
  }
  echo "✅ Completed $podcast"
done

echo "🎉 Daily podcast processing complete!"
```

## Best Practices

### Configuration Management

1. **Start Simple**: Begin with basic YAML config, add complexity gradually
2. **Test Configurations**: Use `podx config validate` before processing
3. **Backup Configs**: Version control your `~/.podx/config.yaml`
4. **Environment Separation**: Use different configs for dev/prod

### Processing Workflow

1. **Batch Similar Content**: Group podcasts by type for consistent processing
2. **Monitor Costs**: Use smaller models for testing, larger for production
3. **Quality Control**: Review outputs before bulk Notion uploads
4. **Incremental Processing**: Process recent episodes first, backfill gradually

### Performance Tips

1. **Use Appropriate Models**: `tiny.en` for testing, `large-v2` for production
2. **Skip Expensive Steps**: Alignment and diarization add significant time
3. **Parallel Processing**: Process multiple episodes simultaneously (future feature)
4. **Clean Up**: Use `--clean` to manage disk space

---

For more detailed configuration options, see the [Configuration Guide](CONFIGURATION.md).
For plugin development, see the [Plugin Architecture Guide](PLUGIN_ARCHITECTURE.md).
