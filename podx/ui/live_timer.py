"""Live timer display for long-running operations."""

import sys
import threading
import time
from typing import IO, Optional


class LiveTimer:
    """Display a live timer that updates every second in the console."""

    def __init__(self, message: str = "Running") -> None:
        self.message = message
        self.start_time: Optional[float] = None
        self.stop_flag = threading.Event()
        self.thread: Optional[threading.Thread] = None
        # Capture stdout at creation time to survive redirects
        self._stdout: IO[str] = sys.stdout
        # Track longest message length for proper line clearing
        self._max_line_length: int = 0
        # Substatus line (second line below timer)
        self._substatus: Optional[str] = None
        self._max_sub_length: int = 0
        self._showing_substatus: bool = False

    def _format_time(self, seconds: int) -> str:
        """Format seconds as M:SS."""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"

    def _run(self) -> None:
        """Run the timer loop."""
        while not self.stop_flag.is_set():
            elapsed = int(time.time() - (self.start_time or 0))
            line = f"\r{self.message} ({self._format_time(elapsed)})"
            # Pad with spaces to clear any leftover characters from longer messages
            line_length = len(line) - 1  # Don't count \r
            if line_length < self._max_line_length:
                line += " " * (self._max_line_length - line_length)
            self._max_line_length = max(self._max_line_length, line_length)

            # Build substatus line if present
            if self._substatus:
                sub_line = f"\n    {self._substatus}"
                sub_visible = len(sub_line) - 1  # Don't count \n
                if sub_visible < self._max_sub_length:
                    sub_line += " " * (self._max_sub_length - sub_visible)
                self._max_sub_length = max(self._max_sub_length, sub_visible)
                # Move cursor up if we already showed a substatus
                if self._showing_substatus:
                    self._stdout.write("\033[A")  # Move up one line
                self._stdout.write(line + sub_line)
                self._showing_substatus = True
            else:
                if self._showing_substatus:
                    # Clear substatus line and move back up
                    self._stdout.write("\033[A")
                    self._stdout.write(line)
                    self._stdout.write("\n" + " " * (self._max_sub_length + 4) + "\033[A")
                    self._showing_substatus = False
                    self._max_sub_length = 0
                else:
                    self._stdout.write(line)

            self._stdout.flush()
            time.sleep(1)

    def update_message(self, message: str) -> None:
        """Update the timer message (for step transitions)."""
        self.message = message

    def update_substatus(self, message: Optional[str]) -> None:
        """Update the substatus line below the timer.

        Args:
            message: Detail message to show, or None to clear.
        """
        self._substatus = message

    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.time()
        self.stop_flag.clear()
        self._max_line_length = 0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        elapsed = time.time() - (self.start_time or 0)
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=2)
        # Clear the substatus line if showing
        clear_length = max(self._max_line_length + 10, 80)
        if self._showing_substatus:
            # Clear substatus line, move up, clear main line
            sub_clear = max(self._max_sub_length + 10, 80)
            self._stdout.write("\033[A")  # Move up
            self._stdout.write("\r" + " " * clear_length)  # Clear main line
            self._stdout.write("\n" + " " * sub_clear)  # Clear sub line
            self._stdout.write("\033[A\r")  # Move back up to start
            self._showing_substatus = False
        else:
            self._stdout.write("\r" + " " * clear_length + "\r")
        self._stdout.flush()
        self._substatus = None
        self._max_sub_length = 0
        return elapsed
