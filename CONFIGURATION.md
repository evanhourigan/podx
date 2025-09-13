# 🎛️ Podx Configuration Guide

Comprehensive guide to configuring podx for optimal podcast processing workflows.

## Table of Contents

- [Quick Start](#quick-start)
- [YAML Configuration System](#yaml-configuration-system)
- [Podcast-Specific Mappings](#podcast-specific-mappings)
- [Multiple Notion Databases](#multiple-notion-databases)
- [Advanced Prompt Engineering](#advanced-prompt-engineering)
- [CLI Configuration Management](#cli-configuration-management)
- [Migration from JSON](#migration-from-json)
- [Real-World Examples](#real-world-examples)

## Quick Start

### 1. Initialize Configuration

```bash
# Create example YAML configuration
podx config init

# Validate your configuration
podx config validate

# View your configuration
podx config show
```

### 2. Basic Usage

```bash
# Simple command - auto-applies podcast-specific settings
podx run --show "Lenny's Podcast" --date 2025-08-17

# The above automatically applies:
# --align --deepcast --extract-markdown --notion
# Routes to "work" Notion database
# Uses interview_guest_focused analysis
# Applies custom product management prompts
```

## YAML Configuration System

### Configuration File Location

- **Global**: `~/.podx/config.yaml`
- **Project**: `./podx-config.yaml` (future feature)

### Configuration Hierarchy

1. **CLI Arguments** (highest priority)
2. **YAML Configuration**
3. **JSON Configuration** (legacy)
4. **Environment Variables**
5. **Built-in Defaults** (lowest priority)

### Basic Structure

```yaml
version: "1.0"
environment: "production" # or "development", "staging"

# Global pipeline defaults
defaults:
  align: true
  deepcast: true
  extract_markdown: true
  notion: false
  clean: false

# Global analysis settings
analysis:
  type: "general"
  model: "gpt-4.1-mini"
  temperature: 0.2
  chunk_size: 24000

# Multiple Notion databases
notion_databases:
  personal:
    name: "Personal Library"
    database_id: "your-personal-db-id"
    token: "your-personal-token"
    title_property: "Episode"
    date_property: "Date"

  work:
    name: "Work Knowledge Base"
    database_id: "your-work-db-id"
    token: "your-work-token"
    title_property: "Title"
    date_property: "Published"

# Podcast-specific mappings
podcasts:
  lenny:
    names: ["Lenny's Podcast", "Lenny Rachitsky"]
    analysis:
      type: "interview_guest_focused"
      custom_prompts: |
        Focus on product management insights...
    pipeline:
      align: true
      deepcast: true
      notion: true
    notion_database: "work"
```

## Podcast-Specific Mappings

### Supported Analysis Types

| Type                      | Focus                        | Best For                      |
| ------------------------- | ---------------------------- | ----------------------------- |
| `interview_guest_focused` | Guest insights & responses   | Lenny's Podcast, Tim Ferriss  |
| `interview_host_focused`  | Host questions & frameworks  | Lex Fridman                   |
| `interview`               | Balanced host-guest          | General interviews            |
| `business`                | Business strategy & insights | Y Combinator, startup content |
| `tech`                    | Technical depth & tools      | Developer podcasts            |
| `educational`             | Learning & concepts          | Academic content              |
| `news`                    | Facts & current events       | News podcasts                 |
| `solo_commentary`         | Host thoughts & opinions     | Solo shows                    |
| `panel_discussion`        | Multiple perspectives        | Panel formats                 |

### Example Podcast Configurations

#### Product Management Focus (Lenny's Podcast)

```yaml
lenny:
  names:
    - "Lenny's Podcast"
    - "Lenny's Newsletter"
    - "Lenny Rachitsky"
  analysis:
    type: "interview_guest_focused"
    temperature: 0.1 # Lower for factual content
    custom_prompts: |
      SPECIAL FOCUS for Lenny's Podcast:
      - Product management interview format
      - Prioritize guest insights about strategy, growth tactics, and career advice
      - Extract specific frameworks, metrics, and methodologies
      - Include concrete examples and case studies
      - Note tools, books, and resources mentioned
  pipeline:
    align: true
    deepcast: true
    extract_markdown: true
    notion: true
  notion_database: "work"
  description: "Product management interviews"
  tags: ["product", "growth", "strategy"]
```

#### Intellectual Interviews (Lex Fridman)

```yaml
lex:
  names:
    - "Lex Fridman Podcast"
    - "Lex Fridman"
    - "Artificial Intelligence Podcast"
  analysis:
    type: "interview_host_focused"
    temperature: 0.3 # Higher for creative insights
    model: "gpt-4.1" # Larger model for complex topics
    custom_prompts: |
      SPECIAL FOCUS for Lex Fridman Podcast:
      - Capture Lex's thoughtful questions and philosophical frameworks
      - Balance technical discussions with human elements
      - Note both technical insights and personal reflections
      - Include mathematical concepts and research references
  pipeline:
    align: true
    diarize: true # Multiple speakers
    deepcast: true
    extract_markdown: true
    notion: false # Too long for regular upload
  notion_database: "research"
  tags: ["ai", "philosophy", "science"]
```

#### Business & Startup Content

```yaml
business:
  names:
    - "Y Combinator Podcast"
    - "YC Podcast"
    - "The Tim Ferriss Show"
  analysis:
    type: "business"
    custom_prompts: |
      BUSINESS FOCUS:
      - Extract specific business advice and funding insights
      - Note market analysis and competitive intelligence
      - Include metrics, funding amounts, and growth numbers
      - Focus on actionable business strategies
  pipeline:
    align: true
    deepcast: true
    extract_markdown: true
    notion: true
  notion_database: "work"
  tags: ["business", "startup", "entrepreneurship"]
```

## Multiple Notion Databases

### Database Configuration

```yaml
notion_databases:
  # Personal learning and entertainment
  personal:
    name: "Personal Podcast Library"
    database_id: "12345678-1234-1234-1234-123456789abc"
    token: "secret_your_personal_notion_token"
    title_property: "Episode"
    date_property: "Published"
    tags_property: "Tags"
    description: "Personal podcast collection"

  # Work-related content
  work:
    name: "Work Knowledge Base"
    database_id: "87654321-4321-4321-4321-cba987654321"
    token: "secret_your_work_notion_token"
    title_property: "Title"
    date_property: "Date Added"
    tags_property: "Keywords"
    description: "Professional development and work insights"

  # Research and academic content
  research:
    name: "Research Database"
    database_id: "abcdef12-3456-7890-abcd-ef1234567890"
    token: "secret_your_research_notion_token"
    title_property: "Research Topic"
    date_property: "Date"
    tags_property: "Research Areas"
    description: "Academic and research content"
```

### Automatic Database Routing

Podcasts automatically route to the specified database:

```yaml
podcasts:
  lenny:
    notion_database: "work" # → Work Knowledge Base
  lex:
    notion_database: "research" # → Research Database
  entertainment:
    notion_database: "personal" # → Personal Library
```

### Security Features

- **Masked IDs**: Database IDs are masked in CLI output (`12345678...89abc`)
- **Environment Injection**: Tokens are automatically set as environment variables
- **Separate Tokens**: Each database can have its own API token

## Advanced Prompt Engineering

### Length-Adaptive Extraction

Content extraction automatically scales with episode length:

| Episode Length | Key Insights | Gold Nuggets | Quotes | Outline Sections |
| -------------- | ------------ | ------------ | ------ | ---------------- |
| < 30 min       | 8-15         | 4-8          | 3-6    | 6-12             |
| 30-60 min      | 12-20        | 6-12         | 4-8    | 10-15            |
| 60-90 min      | 15-25        | 8-15         | 6-10   | 12-18            |
| 90+ min        | 20-30+       | 10-18+       | 8-12+  | 15-22+           |

### Custom Prompt Templates

```yaml
podcasts:
  custom_show:
    analysis:
      custom_prompts: |
        CUSTOM ANALYSIS INSTRUCTIONS:
        - Focus on specific domain expertise
        - Extract technical implementation details
        - Note industry-specific terminology
        - Include regulatory or compliance mentions
        - Prioritize quantitative data and metrics

        EXTRACTION PRIORITIES:
        1. Technical specifications and requirements
        2. Implementation strategies and best practices
        3. Common pitfalls and lessons learned
        4. Tools, frameworks, and resources mentioned
        5. Future trends and predictions
```

### Podcast Type Specialization

Each podcast type has specialized analysis focus:

```yaml
# Interview types
interview_guest_focused: # Focus on guest expertise
interview_host_focused: # Focus on host questions
interview: # Balanced approach

# Content types
business: # Strategy, metrics, market analysis
tech: # Tools, implementation, trends
educational: # Concepts, frameworks, learning
news: # Facts, implications, analysis
narrative: # Story arc, themes, revelations
comedy: # Humor, social commentary
```

## CLI Configuration Management

### Essential Commands

```bash
# Initialize configuration
podx config init

# View configuration (syntax highlighted)
podx config show

# Validate configuration
podx config validate

# List Notion databases
podx config databases

# View podcast configurations
podx podcast list

# Show specific podcast config
podx podcast show "Lenny's Podcast"
```

### Configuration Validation

```bash
$ podx config validate
✅ Configuration is valid!
📋 Found 3 podcast mappings
🗃️  Found 2 Notion databases
⚙️  Global defaults configured
```

### Database Management

```bash
$ podx config databases
                    🗃️ Configured Notion Databases
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name     ┃ Database ID         ┃ Title Property ┃ Description                   ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ personal │ 12345678...456789abc │ Episode        │ Personal podcast collection   │
│ work     │ 87654321...ba987654321 │ Title          │ Work knowledge base          │
└──────────┴─────────────────────┴────────────────┴───────────────────────────────┘
```

## Migration from JSON

### Backward Compatibility

- **Existing JSON configs continue to work**
- **YAML takes precedence** when both exist
- **Gradual migration** - no breaking changes

### Migration Steps

1. **Keep existing JSON configs** (they still work)
2. **Create YAML config**: `podx config init`
3. **Migrate settings** to YAML format
4. **Test with**: `podx config validate`
5. **Optional**: Remove JSON configs when ready

### JSON vs YAML Comparison

| Feature                 | JSON Config      | YAML Config                 |
| ----------------------- | ---------------- | --------------------------- |
| **Readability**         | ❌ Verbose       | ✅ Clean, human-readable    |
| **Comments**            | ❌ Not supported | ✅ Full comment support     |
| **Multi-line strings**  | ❌ Escaped       | ✅ Natural `\|` syntax      |
| **Multiple databases**  | ❌ Single DB     | ✅ Multiple with routing    |
| **Environment support** | ❌ Limited       | ✅ Full environment configs |
| **Validation**          | ❌ Basic         | ✅ Rich validation & errors |

## Real-World Examples

### Scenario 1: Product Manager Workflow

**Setup**: Process product management podcasts for work knowledge base

```yaml
# ~/.podx/config.yaml
defaults:
  align: true
  deepcast: true
  extract_markdown: true
  notion: true

notion_databases:
  work:
    database_id: "your-work-db-id"
    token: "your-work-token"

podcasts:
  product_podcasts:
    names:
      - "Lenny's Podcast"
      - "Product Hunt Radio"
      - "This is Product Management"
    analysis:
      type: "interview_guest_focused"
      custom_prompts: |
        PRODUCT MANAGEMENT FOCUS:
        - Extract frameworks, methodologies, and best practices
        - Note specific metrics and KPIs mentioned
        - Include tool recommendations and resources
        - Focus on career advice and growth strategies
    notion_database: "work"
```

**Usage**:

```bash
# Simple commands that auto-apply all settings
podx run --show "Lenny's Podcast" --date 2025-08-17
podx run --show "Product Hunt Radio" --date 2025-08-15
```

### Scenario 2: Multi-Environment Setup

**Setup**: Different configs for development vs production

```yaml
version: "1.0"
environment: "production"

defaults:
  align: true
  deepcast: true
  extract_markdown: true
  notion: true

analysis:
  model: "gpt-4.1" # Production: better model
  temperature: 0.2 # Production: consistent results

notion_databases:
  prod_db:
    database_id: "prod-db-id"
    token: "prod-token"
# Development overrides (when environment: "development")
# analysis:
#   model: "gpt-4.1-mini"  # Development: cheaper model
#   temperature: 0.5       # Development: more creative
```

### Scenario 3: Research Workflow

**Setup**: Academic and research podcast processing

```yaml
notion_databases:
  research:
    database_id: "research-db-id"
    token: "research-token"
    title_property: "Research Topic"
    tags_property: "Research Areas"

podcasts:
  academic:
    names:
      - "Lex Fridman Podcast"
      - "The Knowledge Project"
      - "Conversations with Tyler"
    analysis:
      type: "interview_host_focused"
      model: "gpt-4.1" # Better for complex topics
      custom_prompts: |
        RESEARCH FOCUS:
        - Extract academic insights and research findings
        - Note theoretical frameworks and methodologies
        - Include citations and references mentioned
        - Focus on intellectual depth and novel ideas
    pipeline:
      align: true
      diarize: true
      deepcast: true
      extract_markdown: true
      notion: false # Manual review before upload
    notion_database: "research"
```

## Environment Variables

### Supported Variables

```bash
# Global pipeline defaults
export PODX_DEFAULT_ALIGN=true
export PODX_DEFAULT_DEEPCAST=true
export PODX_DEFAULT_EXTRACT_MARKDOWN=true
export PODX_DEFAULT_NOTION=false

# Analysis defaults
export PODX_DEFAULT_PODCAST_TYPE=interview_guest_focused
export OPENAI_MODEL=gpt-4.1-mini
export OPENAI_TEMPERATURE=0.2

# Notion (auto-set by YAML config)
export NOTION_TOKEN=your-token
export NOTION_DB_ID=your-db-id
export NOTION_TITLE_PROP=Title
export NOTION_DATE_PROP=Date
```

## Troubleshooting

### Common Issues

#### 1. Configuration Not Found

```bash
❌ No YAML configuration found.
💡 Create one with podx config init
```

#### 2. Invalid YAML Syntax

```bash
❌ Configuration validation failed: yaml.scanner.ScannerError
💡 Check your YAML syntax and fix any errors
```

#### 3. Missing Notion Database

```bash
❌ Notion database 'work' not found in configuration
💡 Add database to notion_databases section
```

### Validation Commands

```bash
# Check configuration syntax
podx config validate

# Test podcast mapping
podx podcast show "Your Podcast Name"

# Verify database setup
podx config databases

# Test with dry run (future feature)
podx run --show "Test" --date 2025-01-01 --dry-run
```

## Best Practices

### 1. Configuration Organization

- **Use descriptive names** for databases and podcast mappings
- **Group similar podcasts** under common configurations
- **Add descriptions** to document your setup
- **Use tags** for organization and filtering

### 2. Security

- **Never commit tokens** to version control
- **Use environment variables** for sensitive data
- **Mask database IDs** in shared configurations
- **Separate tokens** for different environments

### 3. Workflow Optimization

- **Set global defaults** for your most common settings
- **Use podcast-specific overrides** for special cases
- **Leverage database routing** for automatic organization
- **Test configurations** before processing long episodes

### 4. Maintenance

- **Validate regularly**: `podx config validate`
- **Update podcast mappings** as shows evolve
- **Review and optimize** custom prompts periodically
- **Backup configurations** before major changes

---

## Next Steps

1. **Initialize your configuration**: `podx config init`
2. **Customize for your workflow**: Edit `~/.podx/config.yaml`
3. **Test with a short episode**: `podx run --show "Your Podcast" --date YYYY-MM-DD`
4. **Iterate and optimize**: Refine prompts and settings based on results

For more advanced features and examples, see the [Plugin Architecture Guide](PLUGIN_ARCHITECTURE.md) and [Advanced Usage Examples](EXAMPLES.md).
