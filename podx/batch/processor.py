"""Batch processor for parallel episode processing."""

import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from podx.domain.exit_codes import ExitCode
from podx.logging import get_logger

logger = get_logger(__name__)
console = Console()


@dataclass
class BatchResult:
    """Result of batch processing operation."""

    episode: Dict[str, Any]
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    duration: Optional[float] = None
    retries: int = 0


class BatchProcessor:
    """Process multiple episodes in parallel."""

    def __init__(
        self,
        parallel_workers: int = 1,
        continue_on_error: bool = True,
        max_retries: int = 0,
        retry_delay: int = 5,
    ):
        """Initialize batch processor.

        Args:
            parallel_workers: Number of parallel workers
            continue_on_error: Continue processing if one fails
            max_retries: Maximum retry attempts per episode
            retry_delay: Delay between retries (seconds)
        """
        self.parallel_workers = parallel_workers
        self.continue_on_error = continue_on_error
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def process_batch(
        self,
        episodes: List[Dict[str, Any]],
        process_fn: Callable[[Dict[str, Any]], Any],
        operation_name: str = "Processing",
    ) -> List[BatchResult]:
        """Process batch of episodes in parallel.

        Args:
            episodes: List of episodes to process
            process_fn: Function to process each episode
            operation_name: Name of operation for progress display

        Returns:
            List of BatchResult objects
        """
        if not episodes:
            console.print("[yellow]No episodes to process[/yellow]")
            return []

        console.print(
            f"\n[bold blue]{operation_name}:[/bold blue] {len(episodes)} episodes"
        )
        console.print(f"[dim]Workers: {self.parallel_workers}[/dim]\n")

        results: List[BatchResult] = []

        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]{operation_name}...", total=len(episodes)
            )

            # Process in parallel
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                # Submit all jobs
                future_to_episode: Dict[Future, Dict[str, Any]] = {}

                for episode in episodes:
                    future = executor.submit(
                        self._process_with_retry, episode, process_fn
                    )
                    future_to_episode[future] = episode

                # Collect results as they complete
                for future in as_completed(future_to_episode):
                    episode = future_to_episode[future]
                    result = future.result()

                    results.append(result)

                    # Update progress
                    if result.success:
                        status = f"✓ {episode.get('title', 'unknown')}"
                        progress.update(task, advance=1, description=status)
                    else:
                        status = f"✗ {episode.get('title', 'unknown')}"
                        progress.update(task, advance=1, description=status)
                        logger.error(
                            f"Failed to process {episode.get('title')}: {result.error}"
                        )

                        # Stop on error if configured
                        if not self.continue_on_error:
                            console.print(
                                f"\n[red]Stopping batch: {result.error}[/red]"
                            )
                            # Cancel remaining futures
                            for f in future_to_episode:
                                f.cancel()
                            break

        # Print summary
        self._print_summary(results, operation_name)

        return results

    def _process_with_retry(
        self,
        episode: Dict[str, Any],
        process_fn: Callable[[Dict[str, Any]], Any],
    ) -> BatchResult:
        """Process episode with retry logic.

        Args:
            episode: Episode to process
            process_fn: Processing function

        Returns:
            BatchResult
        """
        retries = 0
        last_error = None

        while retries <= self.max_retries:
            try:
                start_time = time.time()
                result = process_fn(episode)
                duration = time.time() - start_time

                return BatchResult(
                    episode=episode,
                    success=True,
                    result=result,
                    duration=duration,
                    retries=retries,
                )

            except Exception as e:
                last_error = str(e)
                retries += 1

                if retries <= self.max_retries:
                    logger.warning(
                        f"Retry {retries}/{self.max_retries} for {episode.get('title')}: {e}"
                    )
                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"Failed after {retries} retries: {episode.get('title')}"
                    )

        # All retries exhausted
        return BatchResult(
            episode=episode, success=False, error=last_error, retries=retries
        )

    def _print_summary(
        self, results: List[BatchResult], operation_name: str
    ) -> None:
        """Print batch processing summary.

        Args:
            results: Processing results
            operation_name: Name of operation
        """
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful

        console.print(f"\n[bold]{'=' * 60}[/bold]")
        console.print(f"[bold]{operation_name} Summary:[/bold]\n")
        console.print(f"Total Episodes: {total}")
        console.print(f"[green]Successful: {successful}[/green]")

        if failed > 0:
            console.print(f"[red]Failed: {failed}[/red]")

        # Show failed episodes
        if failed > 0:
            console.print("\n[bold red]Failed Episodes:[/bold red]")
            for result in results:
                if not result.success:
                    title = result.episode.get("title", "unknown")
                    error = result.error or "Unknown error"
                    console.print(f"  ✗ {title}: {error}")

        # Performance stats
        if successful > 0:
            total_time = sum(r.duration or 0 for r in results if r.success)
            avg_time = total_time / successful

            console.print(f"\n[dim]Total Time: {total_time:.1f}s[/dim]")
            console.print(f"[dim]Average Time: {avg_time:.1f}s per episode[/dim]")

        console.print(f"[bold]{'=' * 60}[/bold]\n")

    def get_exit_code(self, results: List[BatchResult]) -> ExitCode:
        """Get appropriate exit code from results.

        Args:
            results: Processing results

        Returns:
            Exit code
        """
        if not results:
            return ExitCode.USER_ERROR

        if all(r.success for r in results):
            return ExitCode.SUCCESS

        # Partial success or all failed = PROCESSING_ERROR
        return ExitCode.PROCESSING_ERROR
