"""Text formatting and sanitization utilities."""

import re


def clean_cell(text: str) -> str:
    """Sanitize table cell text to avoid layout-breaking characters.

    Removes zero-width and control characters, replaces pipes with middle dots.

    Args:
        text: Text to clean

    Returns:
        Cleaned text safe for table display
    """
    try:
        import unicodedata

        # Remove zero-width and control characters
        cleaned = "".join(ch for ch in (text or "") if unicodedata.category(ch) not in {"Cf", "Cc"})
    except Exception:
        cleaned = text or ""

    # Replace table divider pipes with a middle dot so borders stay aligned
    return cleaned.replace("|", "·")


def sanitize_filename(name: str) -> str:
    """Sanitize a string for safe use in filenames.

    Args:
        name: String to sanitize

    Returns:
        Sanitized string safe for filenames
    """
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*\s]', "_", name)
    # Remove multiple consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    return sanitized.lower()
