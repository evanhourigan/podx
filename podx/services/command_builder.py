"""Fluent interface for building CLI commands.

Provides type-safe, testable command construction replacing inline list building.
"""

from typing import List, Optional


class CommandBuilder:
    """Fluent interface for building CLI commands.

    Provides chainable methods for constructing command-line arguments in a
    type-safe, testable manner. Replaces error-prone list construction with
    clear, self-documenting code.

    Example:
        >>> cmd = (CommandBuilder("podx-transcode")
        ...     .add_option("--to", "wav16")
        ...     .add_option("--outdir", "/tmp/output")
        ...     .add_flag("--verbose")
        ...     .build())
        >>> cmd
        ['podx-transcode', '--to', 'wav16', '--outdir', '/tmp/output', '--verbose']

    Example with conditional flags:
        >>> builder = CommandBuilder("podx-transcribe").add_option("--model", "large-v3")
        >>> if use_precision:
        ...     builder.add_option("--preset", "precision")
        >>> cmd = builder.build()
    """

    def __init__(self, command: str):
        """Initialize command builder with base command.

        Args:
            command: Base command name (e.g., "podx-transcode")
        """
        self.parts: List[str] = [command]

    def add_option(self, flag: str, value: Optional[str] = None) -> "CommandBuilder":
        """Add option flag with value to command.

        Args:
            flag: Option flag (e.g., "--model")
            value: Option value (e.g., "large-v3"). If None, only flag is added.

        Returns:
            Self for method chaining

        Example:
            >>> CommandBuilder("cmd").add_option("--model", "gpt-4").build()
            ['cmd', '--model', 'gpt-4']
        """
        self.parts.append(flag)
        if value is not None:
            self.parts.append(str(value))
        return self

    def add_flag(self, flag: str) -> "CommandBuilder":
        """Add boolean flag to command (no value).

        Args:
            flag: Boolean flag (e.g., "--verbose", "--dry-run")

        Returns:
            Self for method chaining

        Example:
            >>> CommandBuilder("cmd").add_flag("--verbose").build()
            ['cmd', '--verbose']
        """
        self.parts.append(flag)
        return self

    def add_positional(self, value: str) -> "CommandBuilder":
        """Add positional argument to command.

        Args:
            value: Positional argument value

        Returns:
            Self for method chaining

        Example:
            >>> CommandBuilder("rm").add_flag("-rf").add_positional("/tmp/file").build()
            ['rm', '-rf', '/tmp/file']
        """
        self.parts.append(value)
        return self

    def build(self) -> List[str]:
        """Return final command as list of strings.

        Returns:
            Command parts ready for subprocess execution

        Example:
            >>> CommandBuilder("echo").add_positional("hello").build()
            ['echo', 'hello']
        """
        return self.parts

    def __repr__(self) -> str:
        """Return string representation of command."""
        return f"CommandBuilder({' '.join(self.parts)})"
