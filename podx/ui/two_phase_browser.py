"""Base class for two-phase episode → transcript selection browsers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..domain.constants import (
    COLUMN_WIDTH_ASR,
    COLUMN_WIDTH_DATE,
    COLUMN_WIDTH_DEEP,
    COLUMN_WIDTH_DIAR,
    COLUMN_WIDTH_EPISODE_NUM,
    COLUMN_WIDTH_LAST_RUN,
    COLUMN_WIDTH_PROC,
    COLUMN_WIDTH_SHOW,
    EPISODES_PER_PAGE,
    MIN_TITLE_COLUMN_WIDTH,
    TABLE_BORDER_PADDING,
)
from ..ui_styles import (
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    make_console,
)
from .episode_selector import scan_episode_status
from .formatters import clean_cell
from .interactive_browser import InteractiveBrowser


class EpisodeBrowser(InteractiveBrowser):
    """Browser for selecting episodes from scanned directory."""

    def __init__(
        self, episodes: List[Dict[str, Any]], items_per_page: int = EPISODES_PER_PAGE
    ):
        super().__init__(episodes, items_per_page, item_name="episode")

    def _get_item_title(self, item: Dict[str, Any]) -> str:
        """Get title of episode for selection confirmation."""
        return item.get("title", "Unknown")

    def display_page(self) -> None:
        """Display current page with episodes table."""
        if not self.console:
            return

        # Calculate page bounds
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.items))
        page_items = self.items[start_idx:end_idx]

        # Compute dynamic Title width
        try:
            console_width = self.console.size.width
        except Exception:
            console_width = 120

        fixed_cols = (
            COLUMN_WIDTH_EPISODE_NUM
            + COLUMN_WIDTH_SHOW
            + COLUMN_WIDTH_DATE
            + COLUMN_WIDTH_ASR
            + COLUMN_WIDTH_DIAR
            + COLUMN_WIDTH_DEEP
            + COLUMN_WIDTH_PROC
            + COLUMN_WIDTH_LAST_RUN
        )

        borders_allowance = TABLE_BORDER_PADDING
        title_width = max(
            MIN_TITLE_COLUMN_WIDTH, console_width - fixed_cols - borders_allowance
        )

        # Create table
        table = Table(
            show_header=True,
            header_style=TABLE_HEADER_STYLE,
            title=f"🎙️ Episodes (Page {self.current_page + 1}/{self.total_pages})",
            expand=True,
            border_style=TABLE_BORDER_STYLE,
            pad_edge=False,
        )

        table.add_column(
            "#",
            style=TABLE_NUM_STYLE,
            width=COLUMN_WIDTH_EPISODE_NUM,
            justify="right",
            no_wrap=True,
        )
        table.add_column("Show", style="green", width=COLUMN_WIDTH_SHOW, no_wrap=True)
        table.add_column(
            "Date",
            style="blue",
            width=COLUMN_WIDTH_DATE,
            no_wrap=True,
            overflow="ellipsis",
        )
        table.add_column(
            "Title", style="white", width=title_width, no_wrap=True, overflow="ellipsis"
        )
        table.add_column(
            "ASR", style="yellow", width=COLUMN_WIDTH_ASR, no_wrap=True, justify="right"
        )
        table.add_column(
            "Diar",
            style="yellow",
            width=COLUMN_WIDTH_DIAR,
            no_wrap=True,
            justify="center",
        )
        table.add_column(
            "Deep",
            style="yellow",
            width=COLUMN_WIDTH_DEEP,
            no_wrap=True,
            justify="right",
        )
        table.add_column("Proc", style="yellow", width=COLUMN_WIDTH_PROC, no_wrap=True)
        table.add_column(
            "Last Run", style="white", width=COLUMN_WIDTH_LAST_RUN, no_wrap=True
        )

        # Add rows
        for idx, e in enumerate(page_items, start=start_idx + 1):
            asr_count_val = len(e["transcripts"]) if e["transcripts"] else 0
            asr_count = "-" if asr_count_val == 0 else str(asr_count_val)
            diar_ok = "✓" if e["diarized"] else "○"
            dc_count_val = len(e["deepcasts"]) if e["deepcasts"] else 0
            dc_count = "[dim]-[/dim]" if dc_count_val == 0 else str(dc_count_val)
            proc = e.get("processing_flags", "")

            # Sanitize problematic characters
            title_cell = clean_cell(e["title"] or "")
            show_cell = clean_cell(e["show"]) if e.get("show") else ""

            table.add_row(
                str(idx),
                show_cell,
                e["date"],
                title_cell,
                asr_count,
                diar_ok,
                dc_count,
                proc,
                e["last_run"],
            )

        self.console.print(table)

        # Footer
        total = len(self.items)
        footer = f"[dim]Enter 1-{end_idx} of {total} to select • N next • P prev • Q quit[/dim]"
        self.console.print(footer)


class TranscriptBrowser(InteractiveBrowser):
    """Browser for selecting transcripts within an episode."""

    def __init__(
        self,
        transcripts: List[Dict[str, Any]],
        title_fn,
        display_fn,
        items_per_page: int = 10,
    ):
        """Initialize transcript browser.

        Args:
            transcripts: List of transcript items to browse
            title_fn: Function to extract title from transcript for confirmation
            display_fn: Function to display the transcript table
            items_per_page: Number of items per page
        """
        super().__init__(transcripts, items_per_page, item_name="transcript")
        self.title_fn = title_fn
        self.display_fn = display_fn

    def _get_item_title(self, item: Dict[str, Any]) -> str:
        """Get title of transcript for selection confirmation."""
        return self.title_fn(item)

    def display_page(self) -> None:
        """Display current page using custom display function."""
        self.display_fn(self)


class TwoPhaseTranscriptBrowser(ABC):
    """Base class for two-phase episode → transcript selection.

    Provides a reusable pattern for:
    1. Phase 1: Browse and select an episode
    2. Phase 2: Browse and select a specific transcript variant for that episode

    Subclasses must implement:
    - scan_transcripts(episode_dir) - scan for transcripts in episode directory
    - get_transcript_title(transcript) - get display title for transcript
    - display_transcript_page(browser) - display transcript table for current page
    """

    def __init__(self, scan_dir: Path, show_filter: Optional[str] = None):
        """Initialize two-phase browser.

        Args:
            scan_dir: Directory to scan for episodes
            show_filter: Optional show name filter
        """
        self.scan_dir = scan_dir
        self.show_filter = show_filter
        self.console = make_console() if RICH_AVAILABLE else None

    @abstractmethod
    def scan_transcripts(self, episode_dir: Path) -> List[Dict[str, Any]]:
        """Scan episode directory for transcripts.

        Args:
            episode_dir: Episode directory to scan

        Returns:
            List of transcript dictionaries with metadata
        """
        pass

    @abstractmethod
    def get_transcript_title(self, transcript: Dict[str, Any]) -> str:
        """Get display title for transcript selection confirmation.

        Args:
            transcript: Transcript dictionary

        Returns:
            Title string to display
        """
        pass

    @abstractmethod
    def display_transcript_page(self, browser: "TranscriptBrowser") -> None:
        """Display transcript table for current page.

        Args:
            browser: TranscriptBrowser instance with pagination info
        """
        pass

    def browse(self) -> Optional[Dict[str, Any]]:
        """Run two-phase selection: episode → transcript.

        Returns:
            Selected transcript dictionary, or None if cancelled
        """
        # Phase 1: Select episode
        episode = self._select_episode()
        if not episode:
            return None

        # Phase 2: Select transcript
        transcripts = self.scan_transcripts(episode["directory"])

        if not transcripts:
            if self.console:
                self.console.print(
                    f"[red]❌ No transcripts found in episode: {episode['title']}[/red]"
                )
            return None

        transcript = self._select_transcript(transcripts)
        return transcript

    def _select_episode(self) -> Optional[Dict[str, Any]]:
        """Phase 1: Select episode using episode browser.

        Returns:
            Selected episode dictionary, or None if cancelled
        """
        # Scan episodes
        episodes = scan_episode_status(self.scan_dir)

        # Apply show filter if provided
        if self.show_filter:
            s_l = self.show_filter.lower()
            episodes = [e for e in episodes if s_l in (e.get("show", "").lower())]

        if not episodes:
            if self.console:
                if self.show_filter:
                    self.console.print(
                        f"[red]❌ No episodes found for show '{self.show_filter}' in {self.scan_dir}[/red]"
                    )
                else:
                    self.console.print(
                        f"[red]❌ No episodes found in {self.scan_dir}[/red]"
                    )
            return None

        # Sort newest first
        episodes_sorted = sorted(
            episodes, key=lambda x: (x["date"], x["show"]), reverse=True
        )

        # Create browser and select
        browser = EpisodeBrowser(episodes_sorted)
        return browser.browse()

    def _select_transcript(
        self, transcripts: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Phase 2: Select transcript using transcript browser.

        Args:
            transcripts: List of transcript dictionaries

        Returns:
            Selected transcript dictionary, or None if cancelled
        """
        browser = TranscriptBrowser(
            transcripts,
            title_fn=self.get_transcript_title,
            display_fn=self.display_transcript_page,
        )
        return browser.browse()
