"""Basic usage examples for PodX Python API.

This demonstrates the synchronous PodxClient for simple, straightforward operations.
"""

from pathlib import Path

from podx.api.client import ClientConfig, PodxClient


def example_fetch_episode():
    """Fetch a podcast episode by show name and date."""
    client = PodxClient()

    # Fetch episode by show name and date
    result = client.fetch_episode(
        show_name="Huberman Lab",
        date="2024-01-15",
        output_dir=Path("./episodes"),
    )

    if result.success:
        print("✓ Episode fetched successfully!")
        print(f"  Title: {result.episode_meta.get('title')}")
        print(f"  Audio: {result.audio_path}")
        print(f"  Metadata: {result.metadata_path}")
    else:
        print(f"✗ Failed to fetch episode: {result.error}")

    return result


def example_transcribe():
    """Transcribe an audio file using the default model."""
    client = PodxClient()

    # Transcribe audio file
    result = client.transcribe(
        audio_url="episodes/huberman-2024-01-15.mp3",
        asr_model="base",
        out_dir="./episodes",
    )

    if result.success:
        print("✓ Transcription complete!")
        print(f"  Model: {result.model_used}")
        print(f"  Duration: {result.duration_seconds}s")
        print(f"  Segments: {result.segments_count}")
        print(f"  Output: {result.transcript_path}")
    else:
        print(f"✗ Transcription failed: {result.error}")

    return result


def example_diarize():
    """Add speaker identification to a transcript."""
    client = PodxClient()

    # Diarize transcript (identify speakers)
    result = client.diarize(
        transcript_path="episodes/transcript-base.json",
        num_speakers=2,  # If you know how many speakers
    )

    if result.success:
        print("✓ Diarization complete!")
        print(f"  Speakers found: {result.speakers_found}")
        print(f"  Output: {result.transcript_path}")
    else:
        print(f"✗ Diarization failed: {result.error}")

    return result


def example_deepcast():
    """Analyze a transcript with AI to generate insights."""
    client = PodxClient()

    # Analyze transcript
    result = client.deepcast(
        transcript_path="episodes/transcript-base.json",
        llm_model="gpt-4o",
        analysis_type="outline",
        out_dir="./episodes",
    )

    if result.success:
        print("✓ Analysis complete!")
        print(f"  Model: {result.model_used}")
        print(f"  Markdown: {result.markdown_path}")
        if result.usage:
            print(f"  Tokens used: {result.usage}")
    else:
        print(f"✗ Analysis failed: {result.error}")

    return result


def example_export():
    """Export transcript to different formats."""
    client = PodxClient()

    # Export to multiple formats
    result = client.export(
        transcript_path="episodes/transcript-diarized.json",
        formats=["txt", "srt", "vtt", "md"],
        output_dir=Path("./episodes"),
    )

    if result.success:
        print("✓ Export complete!")
        print(f"  Formats: {', '.join(result.formats)}")
        for fmt, path in result.output_files.items():
            print(f"  {fmt.upper()}: {path}")
    else:
        print(f"✗ Export failed: {result.error}")

    return result


def example_publish_to_notion():
    """Publish deepcast analysis to Notion."""
    client = PodxClient()

    # Publish to Notion database
    result = client.publish_to_notion(
        markdown_path="episodes/huberman-2024-01-15-outline.md",
        notion_token="secret_xxx",  # Your Notion integration token
        database_id="abc123",  # Your database ID
    )

    if result.success:
        print("✓ Published to Notion!")
        print(f"  Page URL: {result.page_url}")
        print(f"  Page ID: {result.page_id}")
    else:
        print(f"✗ Publish failed: {result.error}")

    return result


def example_full_pipeline():
    """Complete pipeline: fetch -> transcribe -> analyze -> export -> publish."""
    client = PodxClient(
        config=ClientConfig(
            default_model="base",
            default_llm_model="gpt-4o",
            output_dir=Path("./episodes"),
        )
    )

    print("=== Full Pipeline Example ===\n")

    # 1. Fetch episode
    print("1. Fetching episode...")
    fetch_result = client.fetch_episode(
        show_name="Lex Fridman Podcast",
        date="2024-01-20",
    )
    if not fetch_result.success:
        print(f"Failed at fetch: {fetch_result.error}")
        return

    # 2. Transcribe
    print("\n2. Transcribing audio...")
    transcript_result = client.transcribe(
        audio_url=fetch_result.audio_path,
    )
    if not transcript_result.success:
        print(f"Failed at transcribe: {transcript_result.error}")
        return

    # 3. Diarize (identify speakers)
    print("\n3. Identifying speakers...")
    diarize_result = client.diarize(
        transcript_path=transcript_result.transcript_path,
        min_speakers=2,
        max_speakers=4,
    )
    if not diarize_result.success:
        print(f"Failed at diarize: {diarize_result.error}")
        return

    # 4. Analyze with AI
    print("\n4. Analyzing with AI...")
    analysis_result = client.deepcast(
        transcript_path=diarize_result.transcript_path,
        analysis_type="outline",
    )
    if not analysis_result.success:
        print(f"Failed at analysis: {analysis_result.error}")
        return

    # 5. Export to formats
    print("\n5. Exporting to formats...")
    export_result = client.export(
        transcript_path=diarize_result.transcript_path,
        formats=["txt", "srt", "md"],
    )
    if not export_result.success:
        print(f"Failed at export: {export_result.error}")
        return

    print("\n=== Pipeline Complete! ===")
    print(f"Transcript: {transcript_result.transcript_path}")
    print(f"Analysis: {analysis_result.markdown_path}")
    print(f"Exports: {', '.join(export_result.formats)}")


if __name__ == "__main__":
    # Run individual examples
    print("=== Individual Examples ===\n")

    # Uncomment the examples you want to run:

    # example_fetch_episode()
    # example_transcribe()
    # example_diarize()
    # example_deepcast()
    # example_export()
    # example_publish_to_notion()

    # Or run the full pipeline:
    # example_full_pipeline()

    print("\nSee source code for more examples!")
