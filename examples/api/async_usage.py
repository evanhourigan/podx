"""Async usage examples for PodX Python API with progress callbacks.

This demonstrates the AsyncPodxClient for web UIs and applications that need
real-time progress updates during long-running operations.
"""

import asyncio
from pathlib import Path

from podx.api.client import AsyncPodxClient, ClientConfig


async def example_transcribe_with_callback():
    """Transcribe with a progress callback for real-time updates."""
    client = AsyncPodxClient()

    # Define progress callback
    async def on_progress(update: dict):
        """Called for each progress update."""
        message = update.get("message", "")
        percent = update.get("percent")

        if percent is not None:
            print(f"  [{percent:3d}%] {message}")
        else:
            print(f"  [....] {message}")

    print("Starting transcription with progress updates...")

    result = await client.transcribe(
        audio_path="episodes/podcast.mp3",
        model="base",
        progress_callback=on_progress,
    )

    if result.success:
        print("\n✓ Transcription complete!")
        print(f"  Duration: {result.duration_seconds}s")
        print(f"  Segments: {result.segments_count}")
        print(f"  Output: {result.transcript_path}")
    else:
        print(f"\n✗ Failed: {result.error}")

    return result


async def example_transcribe_stream():
    """Stream transcription progress using async generator."""
    client = AsyncPodxClient()

    print("Starting transcription with streaming updates...")

    async for update in client.transcribe_stream(
        audio_path="episodes/podcast.mp3",
        model="base",
    ):
        # Check if this is a progress update or final result
        if isinstance(update, dict):
            # Progress update
            message = update.get("message", "Working...")
            print(f"  Progress: {message}")
        else:
            # Final TranscribeResponse
            if update.success:
                print(f"\n✓ Complete! Output: {update.transcript_path}")
            else:
                print(f"\n✗ Failed: {update.error}")

    print("Stream ended.")


async def example_diarize_with_progress():
    """Diarize with progress updates."""
    client = AsyncPodxClient()

    # Progress callback
    async def on_progress(update: dict):
        stage = update.get("stage", "processing")
        message = update.get("message", "")
        print(f"  [{stage}] {message}")

    print("Starting speaker diarization...")

    result = await client.diarize(
        transcript_path="episodes/transcript-base.json",
        num_speakers=2,
        progress_callback=on_progress,
    )

    if result.success:
        print("\n✓ Diarization complete!")
        print(f"  Speakers: {result.speakers_found}")
        print(f"  Output: {result.transcript_path}")
    else:
        print(f"\n✗ Failed: {result.error}")

    return result


async def example_parallel_transcriptions():
    """Transcribe multiple files in parallel with progress tracking."""
    client = AsyncPodxClient()

    files = [
        "episodes/episode1.mp3",
        "episodes/episode2.mp3",
        "episodes/episode3.mp3",
    ]

    # Track progress for each file
    progress_state = {f: [] for f in files}

    async def make_callback(filename: str):
        """Create a progress callback for a specific file."""

        async def callback(update: dict):
            progress_state[filename].append(update)
            message = update.get("message", "")
            print(f"  [{Path(filename).name}] {message}")

        return callback

    # Start all transcriptions in parallel
    print(f"Starting {len(files)} transcriptions in parallel...\n")

    tasks = [
        client.transcribe(
            audio_path=f,
            model="base",
            progress_callback=await make_callback(f),
        )
        for f in files
    ]

    # Wait for all to complete
    results = await asyncio.gather(*tasks)

    # Check results
    print("\n=== Results ===")
    for filename, result in zip(files, results):
        if result.success:
            print(f"✓ {Path(filename).name}: {result.segments_count} segments")
        else:
            print(f"✗ {Path(filename).name}: {result.error}")


async def example_web_api_integration():
    """Example showing how to integrate with a web framework (e.g., FastAPI).

    This demonstrates the pattern for WebSocket progress streaming.
    """
    client = AsyncPodxClient()

    # Simulated WebSocket connection
    class MockWebSocket:
        """Mock WebSocket for demonstration."""

        async def send_json(self, data: dict):
            """Simulate sending JSON to client."""
            print(f"  [WebSocket] {data}")

    websocket = MockWebSocket()

    # Progress callback that sends updates via WebSocket
    async def websocket_progress(update: dict):
        """Send progress updates to WebSocket client."""
        await websocket.send_json(
            {
                "type": "progress",
                "operation": "transcribe",
                "data": update,
            }
        )

    print("=== Web API Integration Example ===")
    print("Simulating WebSocket progress streaming...\n")

    # Start transcription with WebSocket updates
    result = await client.transcribe(
        audio_path="episodes/podcast.mp3",
        model="base",
        progress_callback=websocket_progress,
    )

    # Send final result
    await websocket.send_json(
        {
            "type": "complete",
            "operation": "transcribe",
            "data": result.to_dict(),
        }
    )

    print("\n✓ WebSocket streaming complete")


async def example_pipeline_with_progress():
    """Complete async pipeline with progress tracking at each stage."""
    client = AsyncPodxClient(
        config=ClientConfig(
            default_model="base",
            output_dir=Path("./episodes"),
        )
    )

    print("=== Async Pipeline with Progress ===\n")

    # Stage 1: Transcribe
    print("Stage 1: Transcription")

    async def transcribe_progress(update: dict):
        print(f"  [transcribe] {update.get('message', '')}")

    transcript_result = await client.transcribe(
        audio_path="episodes/podcast.mp3",
        progress_callback=transcribe_progress,
    )

    if not transcript_result.success:
        print(f"✗ Pipeline failed at transcription: {transcript_result.error}")
        return

    print("✓ Transcription complete\n")

    # Stage 2: Diarize
    print("Stage 2: Speaker Diarization")

    async def diarize_progress(update: dict):
        print(f"  [diarize] {update.get('message', '')}")

    diarize_result = await client.diarize(
        transcript_path=transcript_result.transcript_path,
        min_speakers=2,
        max_speakers=4,
        progress_callback=diarize_progress,
    )

    if not diarize_result.success:
        print(f"✗ Pipeline failed at diarization: {diarize_result.error}")
        return

    print(f"✓ Diarization complete ({diarize_result.speakers_found} speakers)\n")

    print("=== Pipeline Complete! ===")
    print(f"Final transcript: {diarize_result.transcript_path}")
    print(f"Speakers identified: {diarize_result.speakers_found}")


async def example_error_handling():
    """Demonstrate proper error handling with async operations."""
    client = AsyncPodxClient()

    print("=== Error Handling Example ===\n")

    # Try to transcribe non-existent file
    print("1. Testing with invalid file path...")
    try:
        result = await client.transcribe(
            audio_path="nonexistent.mp3",
            model="base",
        )
        # Result has success=False and error message
        print(f"   Result: success={result.success}, error={result.error}\n")
    except Exception as e:
        print(f"   Exception caught: {e}\n")

    # Try to diarize non-existent transcript
    print("2. Testing with invalid transcript path...")
    try:
        result = await client.diarize(transcript_path="nonexistent.json")
        print(f"   Result: success={result.success}, error={result.error}\n")
    except Exception as e:
        print(f"   Exception caught: {e}\n")

    print("✓ Error handling demonstration complete")


# Main entry point
async def main():
    """Run async examples."""
    print("=== AsyncPodxClient Examples ===\n")

    # Uncomment the examples you want to run:

    # await example_transcribe_with_callback()
    # await example_transcribe_stream()
    # await example_diarize_with_progress()
    # await example_parallel_transcriptions()
    # await example_web_api_integration()
    # await example_pipeline_with_progress()
    # await example_error_handling()

    print("\nSee source code for more examples!")


if __name__ == "__main__":
    # Run async examples
    asyncio.run(main())
