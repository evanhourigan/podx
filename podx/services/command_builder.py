"""Command builder for constructing CLI commands."""

from typing import List, Optional


class CommandBuilder:
    """Fluent interface for building CLI commands.

    Examples:
        >>> cmd = (CommandBuilder("podx-fetch")
        ...        .add_option("--show", "The Podcast")
        ...        .add_option("--date", "2024-10-02")
        ...        .add_flag("--interactive")
        ...        .build())
        >>> cmd
        ['podx-fetch', '--show', 'The Podcast', '--date', '2024-10-02', '--interactive']
    """

    def __init__(self, base_cmd: str):
        """Initialize command builder.

        Args:
            base_cmd: Base command name (e.g., "podx-fetch")
        """
        self.cmd: List[str] = [base_cmd]

    def add_option(self, flag: str, value: Optional[str] = None) -> "CommandBuilder":
        """Add option with value to command.

        Args:
            flag: Option flag (e.g., "--show")
            value: Option value (if None, skipped)

        Returns:
            Self for method chaining
        """
        if value is not None:
            self.cmd.extend([flag, value])
        return self

    def add_flag(self, flag: str) -> "CommandBuilder":
        """Add boolean flag to command.

        Args:
            flag: Flag to add (e.g., "--interactive")

        Returns:
            Self for method chaining
        """
        self.cmd.append(flag)
        return self

    def add_options(self, **kwargs: Optional[str]) -> "CommandBuilder":
        """Add multiple options from keyword arguments.

        Args:
            **kwargs: Option name-value pairs (None values skipped)

        Returns:
            Self for method chaining
        """
        for key, value in kwargs.items():
            if value is not None:
                flag = f"--{key.replace('_', '-')}"
                self.cmd.extend([flag, value])
        return self

    def build(self) -> List[str]:
        """Return final command list.

        Returns:
            List of command parts ready for subprocess
        """
        return self.cmd
