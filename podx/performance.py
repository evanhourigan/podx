#!/usr/bin/env python3
"""
Performance optimization utilities for podx.
"""

import asyncio
import concurrent.futures
import functools
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

import psutil

from .config import get_config
from .logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class ModelCache:
    """Cache for expensive model loading operations."""

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
        self._max_cache_size = 3  # Keep max 3 models in memory

    def get(self, key: str, loader_func: Callable[[], Any]) -> Any:
        """Get model from cache or load it."""
        if key in self._cache:
            self._access_times[key] = time.time()
            logger.debug("Model cache hit", model_key=key)
            return self._cache[key]

        logger.info("Loading model", model_key=key)
        start_time = time.time()
        model = loader_func()
        load_time = time.time() - start_time

        # Evict least recently used models if cache is full
        if len(self._cache) >= self._max_cache_size:
            lru_key = min(
                self._access_times.keys(), key=lambda k: self._access_times[k]
            )
            del self._cache[lru_key]
            del self._access_times[lru_key]
            logger.debug("Evicted model from cache", evicted_key=lru_key)

        self._cache[key] = model
        self._access_times[key] = time.time()

        logger.info(
            "Model loaded and cached",
            model_key=key,
            load_time=round(load_time, 2),
            cache_size=len(self._cache),
        )
        return model

    def clear(self) -> None:
        """Clear the model cache."""
        self._cache.clear()
        self._access_times.clear()
        logger.info("Model cache cleared")


# Global model cache instance
model_cache = ModelCache()


def with_model_cache(cache_key_func: Callable[..., str]) -> Callable[[F], F]:
    """
    Decorator to cache expensive model loading operations.

    Args:
        cache_key_func: Function that takes the same args as the decorated function
                       and returns a cache key string
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = cache_key_func(*args, **kwargs)
            return model_cache.get(cache_key, lambda: func(*args, **kwargs))

        return wrapper  # type: ignore[return-value]

    return decorator


class MemoryMonitor:
    """Monitor memory usage and provide warnings."""

    def __init__(self, warning_threshold_mb: int = 4000):
        self.warning_threshold = warning_threshold_mb * 1024 * 1024  # Convert to bytes

    def check_memory(self, operation: str = "operation") -> float:
        """Check current memory usage and log warnings if high."""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        if memory_info.rss > self.warning_threshold:
            logger.warning(
                "High memory usage detected",
                operation=operation,
                memory_mb=round(memory_mb, 1),
                threshold_mb=self.warning_threshold / (1024 * 1024),
            )
        else:
            logger.debug(
                "Memory usage check", operation=operation, memory_mb=round(memory_mb, 1)
            )

        return memory_mb


# Global memory monitor
memory_monitor = MemoryMonitor()


def with_memory_monitoring(operation_name: str) -> Callable[[F], F]:
    """Decorator to monitor memory usage during function execution."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            memory_monitor.check_memory(f"before_{operation_name}")
            result = func(*args, **kwargs)
            memory_monitor.check_memory(f"after_{operation_name}")
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


async def parallel_map_reduce(
    items: List[Any],
    map_func: Callable[[Any], Any],
    reduce_func: Callable[[List[Any]], Any],
    max_workers: Optional[int] = None,
) -> Any:
    """
    Perform parallel map-reduce operation.

    Args:
        items: List of items to process
        map_func: Function to apply to each item
        reduce_func: Function to combine results
        max_workers: Maximum number of worker threads

    Returns:
        Reduced result
    """
    if max_workers is None:
        max_workers = min(len(items), 4)  # Don't overwhelm the system

    logger.debug(
        "Starting parallel map-reduce", items_count=len(items), max_workers=max_workers
    )

    start_time = time.time()

    # Run map operations in parallel
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        map_results = await asyncio.gather(
            *[loop.run_in_executor(executor, map_func, item) for item in items]
        )

    # Reduce results
    result = reduce_func(map_results)

    total_time = time.time() - start_time
    logger.info(
        "Parallel map-reduce completed",
        items_count=len(items),
        workers=max_workers,
        total_time=round(total_time, 2),
    )

    return result


def optimize_chunk_size(total_chars: int, target_chunks: int = 4) -> int:
    """
    Calculate optimal chunk size for text processing.

    Args:
        total_chars: Total number of characters
        target_chunks: Target number of chunks

    Returns:
        Optimal chunk size
    """
    config = get_config()
    base_chunk_size = config.chunk_chars

    if total_chars <= base_chunk_size:
        return total_chars

    # Calculate chunk size that creates roughly target_chunks
    optimal_size = total_chars // target_chunks

    # Round to nearest 1000 for cleaner chunks
    optimal_size = round(optimal_size / 1000) * 1000

    # Ensure it's within reasonable bounds
    min_chunk = 5000
    max_chunk = base_chunk_size * 2

    optimal_size = max(min_chunk, min(optimal_size, max_chunk))

    logger.debug(
        "Optimized chunk size",
        total_chars=total_chars,
        target_chunks=target_chunks,
        optimal_size=optimal_size,
        estimated_chunks=total_chars // optimal_size,
    )

    return optimal_size


class StreamingProcessor:
    """Process large files in streaming fashion to reduce memory usage."""

    def __init__(self, chunk_size: int = 1024 * 1024):  # 1MB chunks
        self.chunk_size = chunk_size

    def process_large_file(
        self, file_path: Path, processor_func: Callable[[str], str]
    ) -> Path:
        """
        Process a large file in chunks to avoid loading it all into memory.

        Args:
            file_path: Path to the file to process
            processor_func: Function to process each chunk

        Returns:
            Path to the processed file
        """
        output_path = file_path.with_suffix(f"{file_path.suffix}.processed")

        logger.info(
            "Starting streaming file processing",
            input_file=str(file_path),
            output_file=str(output_path),
            chunk_size=self.chunk_size,
        )

        processed_chunks = 0
        with (
            open(file_path, "r", encoding="utf-8") as infile,
            open(output_path, "w", encoding="utf-8") as outfile,
        ):

            while True:
                chunk = infile.read(self.chunk_size)
                if not chunk:
                    break

                processed_chunk = processor_func(chunk)
                outfile.write(processed_chunk)
                processed_chunks += 1

                if processed_chunks % 10 == 0:
                    memory_monitor.check_memory("streaming_processing")

        logger.info(
            "Streaming processing completed",
            chunks_processed=processed_chunks,
            output_file=str(output_path),
        )

        return output_path


def batch_process(items: List[Any], batch_size: int = 10) -> List[List[Any]]:
    """
    Split items into batches for processing.

    Args:
        items: List of items to batch
        batch_size: Size of each batch

    Returns:
        List of batches
    """
    batches = []
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batches.append(batch)

    logger.debug(
        "Created batches",
        total_items=len(items),
        batch_size=batch_size,
        num_batches=len(batches),
    )

    return batches
