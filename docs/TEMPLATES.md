# Deepcast Templates Guide

**Version:** 3.2.0
**Feature:** Format-based podcast analysis templates with length-adaptive scaling

## Overview

PodX includes 10 specialized templates optimized for different podcast formats. Each template is designed to extract relevant information based on the podcast's structure (interview, panel, solo commentary, etc.) rather than content category.

### Key Features

- **Format-based organization** - Templates match podcast structure, not content theme
- **Length-adaptive scaling** - Output automatically adjusts to episode duration
- **Built-in cost estimation** - Preview mode shows token counts and API costs
- **Import/Export** - Share templates via YAML files or URLs
- **Dry-run mode** - Test templates without making LLM calls

## Template Formats

### 1. Solo Commentary (`solo-commentary`)

**Best for:** Single host sharing thoughts, analysis, or storytelling

**Example Podcasts:**
- Dan Carlin's Hardcore History
- Sam Harris: Making Sense (solo episodes)

**Output Sections:**
- Main Thesis
- Supporting Points
- Memorable Quotes
- Key Takeaways
- Episode Structure

**Variables:** `title`, `show`, `duration`, `transcript`

---

### 2. Interview 1-on-1 (`interview-1on1`)

**Best for:** Host interviewing a single guest

**Example Podcasts:**
- Lex Fridman Podcast
- Joe Rogan Experience
- Tim Ferriss Show
- The Knowledge Project

**Output Sections:**
- Guest Introduction
- Key Topics Discussed
- Best Questions
- Notable Quotes
- Key Takeaways
- Conversation Dynamics

**Variables:** `title`, `show`, `duration`, `transcript`, `speakers`

---

### 3. Panel Discussion (`panel-discussion`)

**Best for:** Multiple co-hosts or guests discussing topics

**Example Podcasts:**
- All-In Podcast
- The Talk Show
- Hard Fork (NYT)
- Recode Decode (multi-guest episodes)

**Output Sections:**
- Episode Overview
- Key Topics & Perspectives
- Best Exchanges
- Notable Quotes
- Panelist Contributions
- Key Takeaways

**Variables:** `title`, `show`, `duration`, `transcript`, `speakers`, `speaker_count`

---

### 4. Lecture/Presentation (`lecture-presentation`)

**Best for:** Educational content with structured teaching

**Example Podcasts:**
- MIT OpenCourseWare
- TED Talks Audio
- Freakonomics Radio (educational episodes)

**Output Sections:**
- Topic & Learning Objectives
- Key Concepts
- Examples & Case Studies
- Supporting Evidence
- Lecture Structure
- Key Takeaways

**Variables:** `title`, `show`, `duration`, `transcript`

---

### 5. Debate/Roundtable (`debate-roundtable`)

**Best for:** Structured debates with opposing viewpoints

**Example Podcasts:**
- Intelligence Squared
- The Munk Debates
- Uncommon Knowledge

**Output Sections:**
- Debate Topic & Positions
- Arguments For Each Position
- Rebuttals & Counterarguments
- Key Exchanges
- Common Ground & Disagreements
- Assessment

**Variables:** `title`, `show`, `duration`, `transcript`, `speakers`, `speaker_count`

---

### 6. News Analysis (`news-analysis`)

**Best for:** Analysis and discussion of current events

**Example Podcasts:**
- The Daily (NYT)
- Up First (NPR)
- Today, Explained (Vox)

**Output Sections:**
- News Story Overview
- Key Facts & Background
- Analysis & Interpretation
- Different Viewpoints
- Notable Quotes
- Key Takeaways

**Variables:** `title`, `show`, `duration`, `transcript`, `date`

---

### 7. Case Study (`case-study`)

**Best for:** Deep analysis of specific companies, events, or cases

**Example Podcasts:**
- Acquired
- How I Built This
- Revisionist History
- Business Wars

**Output Sections:**
- Case Study Subject
- Timeline & Key Events
- Critical Decisions
- Lessons Learned
- Broader Implications
- Notable Quotes & Anecdotes
- Key Takeaways

**Variables:** `title`, `show`, `duration`, `transcript`

---

### 8. Technical Deep Dive (`technical-deep-dive`)

**Best for:** In-depth technical discussions of technology, engineering, or science

**Example Podcasts:**
- Software Engineering Daily
- The Changelog
- a16z Podcast (technical episodes)
- Lex Fridman (technical interviews)

**Output Sections:**
- Technical Topic Overview
- Key Technical Concepts
- How It Works
- Challenges & Solutions
- Tradeoffs & Decisions
- Real-World Applications
- Key Takeaways

**Variables:** `title`, `show`, `duration`, `transcript`

---

### 9. Business Strategy (`business-strategy`)

**Best for:** Discussion of business strategy, market analysis, or corporate affairs

**Example Podcasts:**
- Invest Like the Best
- Masters of Scale
- a16z Podcast (business episodes)
- The Prof G Pod

**Output Sections:**
- Business Topic Overview
- Strategic Insights
- Market Analysis
- Business Decisions & Rationale
- Lessons & Frameworks
- Notable Quotes
- Key Takeaways

**Variables:** `title`, `show`, `duration`, `transcript`

---

### 10. Research Review (`research-review`)

**Best for:** Discussion and analysis of academic research papers

**Example Podcasts:**
- The TWIML AI Podcast
- Nature Podcast
- Science Magazine Podcast
- The Ezra Klein Show (research-heavy episodes)

**Output Sections:**
- Research Overview
- Methodology
- Key Findings
- Significance & Implications
- Limitations & Critiques
- Context & Related Work
- Notable Quotes
- Key Takeaways

**Variables:** `title`, `show`, `duration`, `transcript`

---

## Length-Adaptive Scaling

All templates automatically adjust their output based on episode duration:

| Duration | Analysis Level | Items per Section | Summary Length |
|----------|---------------|-------------------|----------------|
| <30 min | Brief | 2-3 items | 1-2 sentences |
| 30-60 min | Standard | 3-5 items | 2-3 sentences |
| 60-90 min | Comprehensive | 5-7 items | 3-4 sentences |
| 90+ min | Deep | 7-10 items | 4+ sentences |

The LLM automatically scales based on the `duration` variable provided.

## CLI Usage

### List Available Templates

```bash
# Table format (default)
podx templates list

# JSON format
podx templates list --format json
```

### Show Template Details

```bash
podx templates show interview-1on1
```

### Preview Template (Dry-run)

Preview template output without making LLM calls:

```bash
# Quick preview with sample data
podx templates preview interview-1on1 --sample

# Preview with sample data + cost estimation
podx templates preview interview-1on1 --sample --cost

# Preview with custom variables
podx templates preview interview-1on1 \
  --title "My Episode" \
  --show "Tech Podcast" \
  --duration 45 \
  --transcript transcript.txt \
  --speakers "Host, Guest Name"

# Preview with JSON variable file
podx templates preview interview-1on1 --vars-json variables.json --cost
```

**Example variables.json:**
```json
{
  "title": "The Future of AI",
  "show": "Tech Talk",
  "duration": 60,
  "transcript": "This is the transcript content...",
  "speakers": "Jane Doe, Dr. John Smith"
}
```

### Export Template

```bash
# Export to stdout
podx templates export interview-1on1

# Export to file
podx templates export interview-1on1 --output my-template.yaml
```

### Import Template

```bash
# Import from local file
podx templates import my-template.yaml

# Import from URL
podx templates import https://example.com/templates/custom-interview.yaml
```

### Delete User Template

```bash
# With confirmation prompt
podx templates delete my-custom-template

# Skip confirmation
podx templates delete my-custom-template --yes
```

**Note:** Built-in templates cannot be deleted.

## Using Templates in Deepcast

Specify a template when running deepcast analysis:

```bash
# Use specific template
podx deepcast --template interview-1on1 \
  --title "Episode Title" \
  --transcript transcript.txt \
  --output analysis.md

# With full pipeline
podx run episode.mp3 --template panel-discussion
```

## Creating Custom Templates

### Template Structure

Templates are YAML files with the following structure:

```yaml
name: my-custom-template
description: Custom template for my podcast format
format: custom  # Optional: format category
output_format: markdown
variables:
  - title
  - show
  - duration
  - transcript

system_prompt: |
  You are analyzing a podcast episode. Focus on...

  Adapt your analysis depth based on episode length:
  - Episodes <30 minutes: Brief analysis (2-3 items per section)
  - Episodes 30-60 minutes: Standard analysis (3-5 items per section)
  - Episodes 60-90 minutes: Comprehensive analysis (5-7 items per section)
  - Episodes 90+ minutes: Deep analysis (7-10 items per section)

user_prompt: |
  Analyze this episode:

  Title: {{title}}
  Show: {{show}}
  Duration: {{duration}} minutes

  Transcript:
  {{transcript}}

  Provide:
  1. **Summary** (scale with duration)
  2. **Key Points** (scale with duration)
  3. **Quotes** (scale with duration)
```

### Best Practices

1. **Include scaling guidance in system prompt** - Don't repeat tier ranges in every section
2. **Use clear section markers** - Make output easy to parse
3. **Test with preview mode** - Use `--sample --cost` to test before production
4. **Provide example podcasts** - Help users understand when to use your template
5. **Keep variables minimal** - Only require variables you actually use

### Sharing Templates

Export your template and share it:

```bash
# Export
podx templates export my-custom-template --output my-template.yaml

# Share the YAML file or host it at a URL
# Others can import with:
# podx templates import https://your-site.com/my-template.yaml
```

## Cost Estimation

Use preview mode with `--cost` to estimate API costs:

```bash
podx templates preview interview-1on1 --sample --cost
```

**Output:**
```
System prompt tokens: 176
User prompt tokens:   1,492
Total input tokens:   1,668
Estimated output:     ~834

Estimated cost (GPT-4o rates):
  Input:  $0.0042
  Output: $0.0083 (estimated)
  Total:  $0.0125

Note: Actual costs vary by model and provider
```

## Template Selection Guide

### Decision Tree

1. **Single speaker, no guests?** → `solo-commentary`
2. **One host + one guest?** → `interview-1on1`
3. **Multiple people discussing?**
   - Opposing views? → `debate-roundtable`
   - Collaborative discussion? → `panel-discussion`
4. **Teaching/educational?** → `lecture-presentation`
5. **Current events/news?** → `news-analysis`
6. **Deep dive into a specific company/event?** → `case-study`
7. **Technical/engineering content?** → `technical-deep-dive`
8. **Business/strategy focus?** → `business-strategy`
9. **Academic research discussion?** → `research-review`

### Format vs Category

**Format** = Structure (how the podcast is organized)
**Category** = Content (what the podcast is about)

Templates are organized by **format**, not category. For example:
- A tech podcast can be an interview, panel, or solo commentary
- A business podcast can use debate, case study, or strategy templates
- Choose based on how the content is delivered, not what it's about

## API Reference

### Python Usage

```python
from podx.templates.manager import TemplateManager

# Load template
manager = TemplateManager()
template = manager.load("interview-1on1")

# Render with variables
context = {
    "title": "My Episode",
    "show": "Tech Podcast",
    "duration": 45,
    "transcript": "...",
    "speakers": "Host, Guest",
}

system_prompt, user_prompt = template.render(context)

# Use with LLM
# response = llm.complete(system=system_prompt, user=user_prompt)
```

### Template Properties

- `name` (str) - Template identifier
- `description` (str) - Human-readable description with format and examples
- `format` (Optional[str]) - Format category (solo, interview, panel, etc.)
- `system_prompt` (str) - System prompt with role and scaling guidance
- `user_prompt` (str) - User prompt with variable placeholders `{{var}}`
- `variables` (List[str]) - Required variable names
- `output_format` (str) - Output format (default: "markdown")

### Available Variables

- `title` - Episode title
- `show` - Show/podcast name
- `duration` - Episode duration in minutes (used for scaling)
- `transcript` - Full transcript text
- `speakers` - Speaker names/info (comma-separated or formatted)
- `speaker_count` - Number of speakers (integer)
- `date` - Episode date
- `description` - Episode description

## Troubleshooting

### Template Not Found

```bash
# List available templates
podx templates list

# Check if template exists
podx templates show template-name
```

### Missing Variables

Preview mode will show missing variables and use placeholders:

```bash
podx templates preview interview-1on1 --title "Test"
# Warning: Missing required variables: show, duration, transcript, speakers
# Using placeholder values for missing variables...
```

### Import Errors

- Check YAML syntax is valid
- Ensure all required fields are present (`name`, `description`, `system_prompt`, `user_prompt`, `variables`)
- Verify URL is accessible (for URL imports)

### Cost Estimation Unavailable

Cost estimation requires `tiktoken` package (included in `llm` extras):

```bash
pip install 'podx[llm]'
```

## Migration from v3.1.0

The old 5 templates have been replaced with 10 new format-based templates:

| Old Template | New Template(s) |
|-------------|----------------|
| `default` | Use `interview-1on1` or `solo-commentary` |
| `interview` | `interview-1on1` |
| `tech-talk` | `technical-deep-dive` |
| `storytelling` | `solo-commentary` or `case-study` |
| `minimal` | Use any template with short episodes (<30 min) |

The old templates are no longer available. Update your scripts to use the new template names.

## Future Enhancements (v3.2.1+)

Planned features for future versions:

- **Rich variables** - Jinja2 conditionals for advanced logic
- **Template versioning** - Track template changes over time
- **Community templates** - Curated collection of user-submitted templates
- **Multi-language support** - Templates for non-English podcasts
- **Custom output formats** - JSON, structured data, etc.

## See Also

- [Configuration Guide](CONFIG.md) - Configure API keys and providers
- [Core API](CORE_API.md) - Programmatic API usage
- [Examples](EXAMPLES.md) - Complete workflow examples
