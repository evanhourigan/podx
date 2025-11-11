#!/usr/bin/env python3
"""
Example: Using the Async PodX Service Layer

This example demonstrates async/await support for non-blocking pipeline
execution and concurrent processing. Perfect for:
- Web applications (FastAPI, aiohttp)
- WebSocket streaming with real-time progress
- Batch processing multiple episodes
- Any async Python application
"""

import asyncio

from podx.services import AsyncPipelineService, AsyncStepExecutor, PipelineConfig


async def basic_async_example():
    """Run a basic async pipeline."""
    print("=" * 60)
    print("Example 1: Basic Async Pipeline")
    print("=" * 60)

    config = PipelineConfig(
        show="Lex Fridman Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        deepcast=True,
    )

    service = AsyncPipelineService(config)

    async def progress_callback(step: str, status: str):
        """Print progress updates."""
        print(f"  [{step}] {status}")

    result = await service.execute(progress_callback=progress_callback)

    print(f"\nCompleted in {result.duration:.2f}s")
    print(f"Artifacts: {len(result.artifacts)}")


async def concurrent_steps_example():
    """Run alignment and diarization concurrently."""
    print("\n" + "=" * 60)
    print("Example 2: Concurrent Enhancement Steps")
    print("=" * 60)

    config = PipelineConfig(
        show="All-In Podcast",
        date="2024-10",
        model="large-v3-turbo",
        align=True,  # Run concurrently with diarize
        diarize=True,  # Run concurrently with align
    )

    service = AsyncPipelineService(config)
    result = await service.execute()

    print(f"\nCompleted in {result.duration:.2f}s")
    print("Both align and diarize ran concurrently!")
    print(f"Steps: {', '.join(result.steps_completed)}")


async def batch_processing_example():
    """Process multiple episodes concurrently."""
    print("\n" + "=" * 60)
    print("Example 3: Batch Processing (3 episodes, max 2 concurrent)")
    print("=" * 60)

    configs = [
        PipelineConfig(show="Lex Fridman Podcast", date="2024-10-01", deepcast=True),
        PipelineConfig(show="All-In Podcast", date="2024-10-01", deepcast=True),
        PipelineConfig(show="Acquired", date="2024-10-01", deepcast=True),
    ]

    def batch_progress(idx: int, step: str, status: str):
        """Print batch progress."""
        podcast = configs[idx].show[:20]
        print(f"  [{idx}] {podcast:20s} | {step:15s} | {status}")

    results = await AsyncPipelineService.process_batch(
        configs, max_concurrent=2, progress_callback=batch_progress
    )

    print(f"\nProcessed {len(results)} episodes")
    for i, result in enumerate(results):
        print(f"  {i+1}. {configs[i].show[:30]:30s} - {result.duration:.2f}s")


async def fastapi_integration_example():
    """Example integration with FastAPI for async web API."""
    print("\n" + "=" * 60)
    print("Example 4: FastAPI Integration Pattern")
    print("=" * 60)

    # This demonstrates the pattern (not a runnable FastAPI server)
    print(
        """
    from fastapi import FastAPI, BackgroundTasks, WebSocket
    from podx.services import AsyncPipelineService, PipelineConfig

    app = FastAPI()

    @app.post("/process")
    async def process_podcast(show: str, deepcast: bool = False):
        '''Process podcast asynchronously'''
        config = PipelineConfig(show=show, deepcast=deepcast)
        service = AsyncPipelineService(config)
        result = await service.execute()

        return {
            "workdir": str(result.workdir),
            "duration": result.duration,
            "artifacts": result.artifacts,
        }

    @app.websocket("/process-stream")
    async def process_with_progress(websocket: WebSocket):
        '''Stream progress updates via WebSocket'''
        await websocket.accept()
        show = await websocket.receive_text()

        async def send_progress(step: str, status: str):
            await websocket.send_json({"step": step, "status": status})

        config = PipelineConfig(show=show, deepcast=True)
        service = AsyncPipelineService(config)

        try:
            result = await service.execute(progress_callback=send_progress)
            await websocket.send_json({"type": "complete", "result": result.to_dict()})
        except Exception as e:
            await websocket.send_json({"type": "error", "error": str(e)})
        finally:
            await websocket.close()
    """
    )

    print("\nThis pattern enables:")
    print("  - Non-blocking API endpoints")
    print("  - Real-time progress via WebSockets")
    print("  - Concurrent request handling")


async def concurrent_fetch_example():
    """Fetch metadata for multiple podcasts concurrently."""
    print("\n" + "=" * 60)
    print("Example 5: Concurrent Metadata Fetching")
    print("=" * 60)

    executor = AsyncStepExecutor(verbose=False)

    # Fetch 3 different podcasts concurrently
    results = await executor.run_concurrent(
        executor.fetch(show="Lex Fridman Podcast", date="2024-10-01"),
        executor.fetch(show="All-In Podcast", date="2024-10-01"),
        executor.fetch(show="Acquired", date="2024-10-01"),
    )

    print(f"\nFetched {len(results)} episodes concurrently:")
    for meta in results:
        print(f"  - {meta['show']}: {meta['episode_title']}")


async def custom_progress_tracking_example():
    """Custom progress tracking with rich progress bar."""
    print("\n" + "=" * 60)
    print("Example 6: Custom Progress Tracking")
    print("=" * 60)

    config = PipelineConfig(
        show="Lex Fridman Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        align=True,
        diarize=True,
        deepcast=True,
    )

    # Track progress state
    progress_state = {"current_step": "", "steps_completed": []}

    async def track_progress(step: str, status: str):
        if step != progress_state["current_step"]:
            if progress_state["current_step"]:
                progress_state["steps_completed"].append(progress_state["current_step"])
            progress_state["current_step"] = step

        completed = len(progress_state["steps_completed"])
        print(f"  [{completed} completed] {step:15s} | {status}")

    service = AsyncPipelineService(config)
    result = await service.execute(progress_callback=track_progress)

    print(f"\nCompleted all steps in {result.duration:.2f}s")


async def cancellation_example():
    """Demonstrate graceful cancellation support."""
    print("\n" + "=" * 60)
    print("Example 7: Graceful Cancellation")
    print("=" * 60)

    config = PipelineConfig(
        show="Lex Fridman Podcast",
        date="2024-10-01",
        model="large-v3-turbo",
        deepcast=True,
    )

    service = AsyncPipelineService(config)

    # Create task that we can cancel
    task = asyncio.create_task(service.execute())

    # Simulate cancellation after 5 seconds (uncomment to test)
    # await asyncio.sleep(5)
    # task.cancel()

    try:
        result = await task
        print(f"Completed: {result.duration:.2f}s")
    except asyncio.CancelledError:
        print("Pipeline was cancelled gracefully")


async def mixed_sync_async_example():
    """Demonstrate using both sync and async APIs together."""
    print("\n" + "=" * 60)
    print("Example 8: Mixed Sync/Async Usage")
    print("=" * 60)

    # Use async for I/O-bound operations
    executor = AsyncStepExecutor()
    meta = await executor.fetch(show="Lex Fridman Podcast", date="2024-10-01")

    print(f"Fetched: {meta['episode_title']}")

    # Can mix with sync code as needed
    # (In real code, you might use sync PipelineService here)
    print("Async is great for I/O-bound operations!")
    print("Use sync PipelineService for simpler scripts")


async def main():
    """Run all async examples."""
    print("\n" + "=" * 60)
    print("PodX Async Service Layer Examples")
    print("=" * 60)
    print("\nThese examples demonstrate async/await support.")
    print("Uncomment the example you want to run:")
    print()

    # Uncomment one or more examples to run:
    # await basic_async_example()
    # await concurrent_steps_example()
    # await batch_processing_example()
    # await fastapi_integration_example()
    # await concurrent_fetch_example()
    # await custom_progress_tracking_example()
    # await cancellation_example()
    # await mixed_sync_async_example()

    print("\nAsync Service Layer Benefits:")
    print("  ✓ Non-blocking execution (doesn't block event loop)")
    print("  ✓ Concurrent step execution (align + diarize in parallel)")
    print("  ✓ Batch processing with concurrency control")
    print("  ✓ Real-time progress via callbacks/WebSockets")
    print("  ✓ Graceful cancellation support")
    print("  ✓ Perfect for web apps, APIs, and async applications")
    print()
    print("Use Cases:")
    print("  - FastAPI/aiohttp web applications")
    print("  - WebSocket streaming with progress updates")
    print("  - Batch processing 100s of episodes")
    print("  - Real-time dashboards and monitoring")
    print("  - Jupyter notebooks with async support")


if __name__ == "__main__":
    asyncio.run(main())
