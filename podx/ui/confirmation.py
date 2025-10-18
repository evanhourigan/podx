"""Confirmation and prompt utilities for interactive CLI."""


class Confirmation:
    """Reusable confirmation prompts."""

    @staticmethod
    def yes_no(prompt: str, current: bool) -> bool:
        """Ask yes/no question with strict validation.

        Accepts only y/Y, n/N, empty (keep current), or q/Q to cancel.

        Args:
            prompt: Question to ask
            current: Current value (shown as default)

        Returns:
            True for yes, False for no

        Raises:
            SystemExit: If user enters 'q' to cancel
        """
        while True:
            resp = input(
                f"{prompt} (y/n, current={'yes' if current else 'no'}; q cancel): "
            ).strip()

            if not resp:
                return current

            r = resp.lower()
            if r in {"q", "quit", "exit"}:
                raise SystemExit(0)

            if r in {"y", "n"}:
                return r == "y"

            print("Please enter 'y', 'n', or 'q'.")

    @staticmethod
    def yes_no_quit(prompt: str) -> bool:
        """Ask yes/no question, exit on quit.

        Args:
            prompt: Question to ask

        Returns:
            True for yes, False for no

        Raises:
            SystemExit: If user enters 'q' to cancel
        """
        while True:
            resp = input(f"{prompt} (y/n, q=cancel): ").strip().lower()

            if resp in {"q", "quit", "exit"}:
                raise SystemExit(0)

            if resp in {"y", "yes"}:
                return True
            elif resp in {"n", "no"}:
                return False

            print("Please enter 'y', 'n', or 'q'.")

    @staticmethod
    def proceed_or_exit(message: str) -> None:
        """Show message and ask to proceed or exit.

        Args:
            message: Message to display

        Raises:
            SystemExit: If user chooses not to proceed
        """
        print(message)
        resp = input("Proceed? (y/n): ").strip().lower()

        if resp not in {"y", "yes"}:
            raise SystemExit(0)
