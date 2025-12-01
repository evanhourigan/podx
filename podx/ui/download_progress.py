"""Download progress display for fetch operations."""

import sys
from typing import Optional


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class DownloadProgress:
    """Simple download progress display that updates in place.

    Shows: Downloading... 45.2 MB / 128.5 MB (35%)
    Or if total unknown: Downloading... 45.2 MB
    """

    def __init__(self, label: str = "Downloading"):
        self.label = label
        self.total_size: Optional[int] = None
        self.downloaded: int = 0
        self._last_line_len: int = 0

    def set_total(self, total_bytes: Optional[int]):
        """Set total size if known from Content-Length header."""
        if total_bytes and total_bytes > 0:
            self.total_size = total_bytes

    def update(self, chunk_size: int):
        """Update progress with new chunk downloaded."""
        self.downloaded += chunk_size
        self._display()

    def _display(self):
        """Display current progress, overwriting previous line."""
        downloaded_str = format_size(self.downloaded)

        if self.total_size:
            total_str = format_size(self.total_size)
            percent = (self.downloaded / self.total_size) * 100
            line = f"\r{self.label}... {downloaded_str} / {total_str} ({percent:.0f}%)"
        else:
            line = f"\r{self.label}... {downloaded_str}"

        # Pad to clear previous content
        padding = max(0, self._last_line_len - len(line))
        sys.stdout.write(line + " " * padding)
        sys.stdout.flush()
        self._last_line_len = len(line)

    def finish(self):
        """Clear the progress line."""
        # Clear the line
        sys.stdout.write("\r" + " " * (self._last_line_len + 10) + "\r")
        sys.stdout.flush()
