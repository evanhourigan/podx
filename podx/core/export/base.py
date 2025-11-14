"""Base classes for export format Strategy pattern."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type


class ExportFormatter(ABC):
    """Abstract base class for export formatters.

    Each format (TXT, SRT, VTT, MD) implements this interface,
    enabling them to be used interchangeably via Strategy pattern.
    """

    @property
    @abstractmethod
    def extension(self) -> str:
        """Get file extension for this format (e.g., 'txt', 'srt')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get human-readable format name (e.g., 'Plain Text', 'SubRip')."""
        pass

    @abstractmethod
    def format(self, segments: List[Dict[str, Any]]) -> str:
        """Format transcript segments to this format.

        Args:
            segments: List of transcript segments with text, start, end, speaker

        Returns:
            Formatted string ready to write to file
        """
        pass


class FormatRegistry:
    """Registry for managing available export formats.

    Implements a registry pattern to allow dynamic format registration.
    """

    _formats: Dict[str, Type[ExportFormatter]] = {}

    @classmethod
    def register(cls, format_id: str, formatter_class: Type[ExportFormatter]) -> None:
        """Register a new export format.

        Args:
            format_id: Format identifier (e.g., 'txt', 'srt', 'custom')
            formatter_class: Formatter class implementing ExportFormatter

        Example:
            >>> class CustomFormatter(ExportFormatter):
            ...     extension = "custom"
            ...     name = "Custom Format"
            ...     def format(self, segments):
            ...         return "custom output"
            >>>
            >>> FormatRegistry.register("custom", CustomFormatter)
        """
        if not issubclass(formatter_class, ExportFormatter):
            raise ValueError(
                f"Formatter class must inherit from ExportFormatter: {formatter_class}"
            )
        cls._formats[format_id] = formatter_class

    @classmethod
    def get(cls, format_id: str) -> Type[ExportFormatter]:
        """Get formatter class by ID.

        Args:
            format_id: Format identifier

        Returns:
            Formatter class

        Raises:
            KeyError: If format not found
        """
        if format_id not in cls._formats:
            available = ", ".join(cls._formats.keys())
            raise KeyError(
                f"Unknown export format: {format_id}. Available: {available}"
            )
        return cls._formats[format_id]

    @classmethod
    def list_formats(cls) -> Dict[str, Type[ExportFormatter]]:
        """Get all registered formats.

        Returns:
            Dictionary mapping format IDs to formatter classes
        """
        return cls._formats.copy()
