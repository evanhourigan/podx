"""Constants for PodX application.

This module contains all magic numbers and hardcoded values used throughout the
application, extracted for better maintainability and configurability.
"""

# ============================================================================
# Display & Output Constants
# ============================================================================

# Preview lengths
PREVIEW_MAX_LENGTH = 400  # Max characters to show in CLI preview
TITLE_MAX_LENGTH = 80  # Max characters for episode title display

# JSON formatting
JSON_INDENT = 2  # Indentation level for JSON output

# ============================================================================
# Validation Constants
# ============================================================================

# Notion database ID validation
MIN_NOTION_DB_ID_LENGTH = 16  # Minimum expected length for Notion database IDs

# ============================================================================
# Model Provider Detection
# ============================================================================

# Model name prefixes for provider detection
OPENAI_MODEL_PREFIX = "gpt"  # OpenAI models start with "gpt"
ANTHROPIC_MODEL_SEPARATOR = "-"  # Anthropic models contain hyphens

# ============================================================================
# File Encoding
# ============================================================================

DEFAULT_ENCODING = "utf-8"  # Default file encoding for all read/write operations
