# Show Prompt Feature for podx-deepcast

## Overview

The `--show-prompt` flag allows you to inspect the exact prompts that would be sent to the LLM without actually making API calls. This is useful for:

- **Debugging**: Understanding what the system is sending to the LLM
- **Prompt tuning**: Iterating on prompt design without incurring API costs
- **Transparency**: Seeing exactly what data and instructions are being provided
- **Cost estimation**: Reviewing the prompt size before committing to API calls

## Usage

### Basic Usage

```bash
# Show all prompts (default)
podx-deepcast --input transcript.json --show-prompt

# Equivalent to:
podx-deepcast --input transcript.json --show-prompt all

# Show only the system prompt
podx-deepcast --input transcript.json --show-prompt system_only
```

Note: When using `--show-prompt`, the `--output` flag is not required (and will be ignored).

### Display Modes

The `--show-prompt` flag accepts an optional value:

- **`all`** (default): Shows all prompts including system prompt, map phase prompts with full transcript chunks, reduce phase structure, and JSON schema
- **`system_only`**: Shows only the system prompt that would be used for all API calls

### With Options

You can combine `--show-prompt` with other flags to see how they affect the prompts:

```bash
# Show all prompts for a specific podcast type
podx-deepcast --input transcript.json --show-prompt all --type interview

# Show only system prompt for a specific podcast type
podx-deepcast --input transcript.json --show-prompt system_only --type interview

# Show prompts with custom chunk size
podx-deepcast --input transcript.json --show-prompt --chunk-chars 10000

# Show prompts for guest-focused interview analysis
podx-deepcast --input transcript.json --show-prompt --type interview_guest_focused

# Show prompts with metadata
podx-deepcast --input transcript.json --meta episode_meta.json --show-prompt
```

### From stdin

```bash
# Show all prompts
cat transcript.json | podx-deepcast --show-prompt

# Show only system prompt
cat transcript.json | podx-deepcast --show-prompt system_only
```

## Output Format

### All Mode (default)

When using `--show-prompt` or `--show-prompt all`, the output includes all prompts:

```
================================================================================
SYSTEM PROMPT (used for all API calls)
================================================================================
[Full system prompt with role definition, instructions, and formatting rules]

================================================================================
MAP PHASE PROMPTS (N chunks)
================================================================================

--------------------------------------------------------------------------------
MAP PROMPT 1/N
--------------------------------------------------------------------------------
[Instructions for analyzing chunk 1]

Chunk 1/N:

[Actual transcript text for chunk 1]

[... repeated for each chunk ...]

================================================================================
REDUCE PHASE PROMPT
================================================================================

[Instructions for synthesizing all chunk analyses]

[NOTE: In actual execution, this would contain the LLM responses from all map phase calls]

JSON SCHEMA REQUEST:
--------------------------------------------------------------------------------
[JSON schema specification if --extract-json would be used]

================================================================================
END OF PROMPTS
================================================================================
```

### System Only Mode

When using `--show-prompt system_only`, the output includes only the system prompt:

```
================================================================================
SYSTEM PROMPT (used for all API calls)
================================================================================
[Full system prompt with role definition, instructions, and formatting rules]

================================================================================
END OF PROMPTS
================================================================================
```

This is useful when you only want to review how the system prompt changes based on podcast type, configuration, or other options, without seeing all the transcript chunks.

## Implementation Details

### What Happens When You Use `--show-prompt`

1. **Normal Processing**: The transcript is processed normally:

   - Segments are converted to plain text
   - Podcast type is detected or specified
   - Episode duration is calculated for adaptive scaling
   - Configuration overrides are applied
   - Text is chunked according to `--chunk-chars`

2. **Prompt Construction**: All prompts are built:

   - System prompt with role definition
   - Map phase prompts for each chunk
   - Reduce phase prompt structure
   - JSON schema if applicable

3. **Early Exit**: Instead of calling the OpenAI API:

   - Prompts are formatted for display
   - Output is printed to stdout
   - Command exits without making API calls

4. **No API Key Required**: Since no API calls are made, you don't need `OPENAI_API_KEY` set when using `--show-prompt`.

### Key Differences from Normal Execution

| Aspect      | Normal Execution              | With `--show-prompt` |
| ----------- | ----------------------------- | -------------------- |
| API calls   | Makes multiple API calls      | No API calls         |
| API key     | Required                      | Not required         |
| Output file | Required (`--output`)         | Optional (ignored)   |
| Output      | Markdown + JSON analysis      | Formatted prompts    |
| Cost        | Incurs API costs              | Free                 |
| Time        | Minutes (depending on length) | Seconds              |

## Use Cases

### 1. Prompt Development

When developing custom prompts or podcast configurations:

```bash
# Check how your custom prompts are integrated
podx-deepcast --input transcript.json --show-prompt --type tech

# Quickly review just the system prompt changes
podx-deepcast --input transcript.json --show-prompt system_only --type tech
```

### 2. Cost Estimation

Before processing a long episode, check the prompt size:

```bash
# See how many chunks and what prompt size
podx-deepcast --input long_episode.json --show-prompt | wc -l
```

### 3. Debugging Issues

If the analysis isn't capturing what you expect:

```bash
# Review what instructions the LLM is receiving
podx-deepcast --input transcript.json --show-prompt > prompts.txt
# Then review prompts.txt
```

### 4. Learning the System

Understanding how deepcast works:

```bash
# Compare prompts for different podcast types
podx-deepcast --input transcript.json --show-prompt --type interview > interview_prompts.txt
podx-deepcast --input transcript.json --show-prompt --type tech > tech_prompts.txt
diff interview_prompts.txt tech_prompts.txt

# Compare just the system prompts (faster and more focused)
podx-deepcast --input transcript.json --show-prompt system_only --type interview > interview_system.txt
podx-deepcast --input transcript.json --show-prompt system_only --type tech > tech_system.txt
diff interview_system.txt tech_system.txt
```

### 5. Configuration Validation

Verify that podcast-specific configurations are being applied correctly:

```bash
# Check if custom prompts from YAML config are being used
podx-deepcast --input transcript.json --show-prompt system_only --type interview_guest_focused
```

## Technical Implementation

The feature is implemented in `podx/deepcast.py`:

1. **CLI Flag**: Added `--show-prompt` option to the Click command that accepts "all" or "system_only"
2. **Function Parameter**: Added `show_prompt_only` parameter to the `deepcast()` function (accepts Optional[str])
3. **Early Return**: When `show_prompt_only` is not None, prompts are formatted and returned before API calls
4. **Helper Function**: `_build_prompt_display()` formats prompts based on the mode parameter

### Code Flow

```python
# In main()
if show_prompt is not None:
    prompt_display, _ = deepcast(
        transcript, model, temperature, chunk_chars, want_json, podcast_type,
        show_prompt_only=show_prompt  # "all" or "system_only"
    )
    print(prompt_display)
    return

# In deepcast()
if show_prompt_only is not None:
    prompt_display = _build_prompt_display(
        system, template, chunks, want_json, show_prompt_only
    )
    return prompt_display, None

# In _build_prompt_display()
def _build_prompt_display(system, template, chunks, want_json, mode="all"):
    # Always show system prompt
    # ...

    if mode == "system_only":
        return system_prompt_only

    # Otherwise show all prompts
    # ...
```

## Examples

### Example 1: Quick System Prompt Check

```bash
$ podx-deepcast --input short_episode.json --show-prompt system_only

================================================================================
SYSTEM PROMPT (used for all API calls)
================================================================================
You are an expert editorial assistant specializing in podcast content analysis...

[... rest of system prompt ...]

================================================================================
END OF PROMPTS
================================================================================
```

### Example 2: Full Prompts with Single Chunk

```bash
$ podx-deepcast --input short_episode.json --show-prompt | head -50

================================================================================
SYSTEM PROMPT (used for all API calls)
================================================================================
You are an expert editorial assistant specializing in podcast content analysis...

[... rest of system prompt ...]

================================================================================
MAP PHASE PROMPTS (1 chunks)
================================================================================

--------------------------------------------------------------------------------
MAP PROMPT 1/1
--------------------------------------------------------------------------------
Extract key information from this transcript CHUNK...
```

### Example 3: Multiple Chunks

For a longer episode that will be split into multiple chunks:

```bash
$ podx-deepcast --input long_episode.json --show-prompt all --chunk-chars 5000

[Shows system prompt, then multiple MAP PROMPTs with the full text of each chunk]
```

### Example 4: Comparing System Prompts Across Types

```bash
$ podx-deepcast --input interview.json --show-prompt system_only --type interview_host_focused

[Shows prompts specifically tailored for host-focused interview analysis]

$ podx-deepcast --input interview.json --show-prompt system_only --type interview_guest_focused

[Shows prompts specifically tailored for guest-focused interview analysis]
```

## Related Files

- **Implementation**: `podx/deepcast.py` (main implementation)
- **Templates**: `podx/prompt_templates.py` (prompt templates for different podcast types)
- **Tests**: `tests/test_deepcast_show_prompt.py` (test coverage)

## Future Enhancements

Possible improvements to this feature:

1. **Token counting**: Show estimated token count for each prompt
2. **Cost estimation**: Calculate and display estimated API cost
3. **Diff mode**: Compare prompts between different configurations
4. **Export formats**: Save prompts in JSON or YAML format
5. **Prompt validation**: Check for common issues or improvements
