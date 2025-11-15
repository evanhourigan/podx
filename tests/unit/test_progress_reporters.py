"""Tests for progress reporting abstraction.

Tests all ProgressReporter implementations:
- ConsoleProgressReporter (CLI output)
- APIProgressReporter (event queue for web APIs)
- SilentProgressReporter (testing with call tracking)
"""

import time
from io import StringIO

import pytest

from podx.progress import (
    APIProgressReporter,
    ConsoleProgressReporter,
    ProgressEvent,
    ProgressReporter,
    ProgressStep,
    SilentProgressReporter,
)


class TestProgressReporterInterface:
    """Test the abstract ProgressReporter interface."""

    def test_progress_reporter_is_abstract(self):
        """ProgressReporter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ProgressReporter()  # type: ignore

    def test_progress_step_dataclass(self):
        """ProgressStep dataclass works correctly."""
        step = ProgressStep(name="Test step", status="running", progress=0.5, message="In progress")
        assert step.name == "Test step"
        assert step.status == "running"
        assert step.progress == 0.5
        assert step.message == "In progress"

    def test_progress_event_dataclass(self):
        """ProgressEvent dataclass works correctly."""
        import time
        event = ProgressEvent(
            timestamp=time.time(),
            event_type="step_update",
            message="Processing",
            step=2,
            progress=0.67
        )
        assert event.event_type == "step_update"
        assert event.message == "Processing"
        assert event.step == 2
        assert event.progress == 0.67
        assert isinstance(event.timestamp, float)

        # Test to_dict method
        event_dict = event.to_dict()
        assert "event_type" in event_dict
        assert "message" in event_dict


class TestConsoleProgressReporter:
    """Test ConsoleProgressReporter (Rich-based CLI output)."""

    def test_initialization(self):
        """ConsoleProgressReporter initializes correctly."""
        # Default initialization
        reporter = ConsoleProgressReporter()
        assert reporter.console is not None
        assert reporter.verbose is False

        # With verbose mode
        reporter_verbose = ConsoleProgressReporter(verbose=True)
        assert reporter_verbose.verbose is True

    def test_start_task(self):
        """start_task outputs task start message."""
        output = StringIO()
        from rich.console import Console

        console = Console(file=output, force_terminal=False)
        reporter = ConsoleProgressReporter(console=console)

        reporter.start_task("Test Task", total_steps=5)
        output_text = output.getvalue()

        assert "Test Task" in output_text

    def test_update_step(self):
        """update_step outputs progress message."""
        output = StringIO()
        from rich.console import Console

        console = Console(file=output, force_terminal=False)
        reporter = ConsoleProgressReporter(console=console)

        reporter.update_step("Processing step 1", step=1, progress=0.2)
        output_text = output.getvalue()

        assert "Processing step 1" in output_text

    def test_complete_step(self):
        """complete_step outputs completion message."""
        output = StringIO()
        from rich.console import Console

        console = Console(file=output, force_terminal=False)
        reporter = ConsoleProgressReporter(console=console)

        reporter.complete_step("Step 1 complete", duration=2.5)
        output_text = output.getvalue()

        assert "Step 1 complete" in output_text

    def test_complete_task(self):
        """complete_task outputs task completion message."""
        output = StringIO()
        from rich.console import Console

        console = Console(file=output, force_terminal=False)
        reporter = ConsoleProgressReporter(console=console)

        reporter.complete_task("Task complete!", duration=10.0)
        output_text = output.getvalue()

        assert "Task complete!" in output_text

    def test_fail_step(self):
        """fail_step outputs error message."""
        output = StringIO()
        from rich.console import Console

        console = Console(file=output, force_terminal=False)
        reporter = ConsoleProgressReporter(console=console)

        reporter.fail_step("Something went wrong")
        output_text = output.getvalue()

        assert "Something went wrong" in output_text

    def test_fail_step_with_exception(self):
        """fail_step with exception outputs exception details."""
        output = StringIO()
        from rich.console import Console

        console = Console(file=output, force_terminal=False)
        reporter = ConsoleProgressReporter(console=console)

        exc = ValueError("Invalid value")
        reporter.fail_step("Processing failed", error=exc)
        output_text = output.getvalue()

        assert "Processing failed" in output_text


class TestAPIProgressReporter:
    """Test APIProgressReporter (event queue for web APIs)."""

    def test_initialization(self):
        """APIProgressReporter initializes with empty event queue."""
        reporter = APIProgressReporter()
        assert len(reporter.events) == 0

        # With custom maxlen
        reporter_custom = APIProgressReporter(maxlen=100)
        assert reporter_custom.events.maxlen == 100

    def test_start_task_creates_event(self):
        """start_task creates a 'task_start' event."""
        reporter = APIProgressReporter()
        reporter.start_task("Test Task", total_steps=3)

        assert len(reporter.events) == 1
        event = reporter.events[0]
        assert event.event_type == "task_start"
        assert "Test Task" in event.message
        assert event.total_steps == 3

    def test_update_step_creates_event(self):
        """update_step creates a 'step_update' event."""
        reporter = APIProgressReporter()
        reporter.update_step("Processing...", step=2, progress=0.67)

        assert len(reporter.events) == 1
        event = reporter.events[0]
        assert event.event_type == "step_update"
        assert event.message == "Processing..."
        assert event.step == 2
        assert event.progress == 0.67

    def test_complete_step_creates_event(self):
        """complete_step creates a 'step_complete' event."""
        reporter = APIProgressReporter()
        reporter.complete_step("Step done", duration=3.2)

        assert len(reporter.events) == 1
        event = reporter.events[0]
        assert event.event_type == "step_complete"
        assert event.message == "Step done"
        assert event.duration == 3.2

    def test_complete_task_creates_event(self):
        """complete_task creates a 'task_complete' event."""
        reporter = APIProgressReporter()
        reporter.complete_task("All done!", duration=15.5)

        assert len(reporter.events) == 1
        event = reporter.events[0]
        assert event.event_type == "task_complete"
        assert event.message == "All done!"
        assert event.duration == 15.5

    def test_fail_task_creates_event(self):
        """fail_task creates a 'task_fail' event."""
        reporter = APIProgressReporter()
        exc = RuntimeError("Test error")
        reporter.fail_task("Failed!", error=exc)

        assert len(reporter.events) == 1
        event = reporter.events[0]
        assert event.event_type == "task_fail"
        assert event.message == "Failed!"
        assert event.error == str(exc)

    def test_get_events_all(self):
        """get_events() returns all events."""
        reporter = APIProgressReporter()
        reporter.start_task("Task")
        reporter.update_step("Step 1", step=1)
        reporter.update_step("Step 2", step=2)
        reporter.complete_task("Done")

        events = reporter.get_events()
        assert len(events) == 4
        assert events[0].event_type == "task_start"
        assert events[1].event_type == "step_update"
        assert events[2].event_type == "step_update"
        assert events[3].event_type == "task_complete"

    def test_get_events_since_timestamp(self):
        """get_events(since=timestamp) returns only newer events."""
        reporter = APIProgressReporter()

        reporter.start_task("Task")
        time.sleep(0.01)  # Ensure different timestamps
        timestamp = time.time()
        time.sleep(0.01)

        reporter.update_step("Step 1")
        reporter.update_step("Step 2")

        events = reporter.get_events(since=timestamp)
        assert len(events) == 2  # Only events after timestamp
        assert all(e.timestamp > timestamp for e in events)

    def test_clear_events(self):
        """clear_events() removes all events."""
        reporter = APIProgressReporter()
        reporter.start_task("Task")
        reporter.update_step("Step")
        reporter.complete_task("Done")

        assert len(reporter.events) == 3
        reporter.clear_events()
        assert len(reporter.events) == 0

    def test_event_queue_maxlen(self):
        """Event queue respects maxlen (FIFO)."""
        reporter = APIProgressReporter(maxlen=3)

        # Add 5 events
        for i in range(5):
            reporter.update_step(f"Step {i}")

        # Only last 3 should remain
        assert len(reporter.events) == 3
        events = reporter.get_events()
        assert events[0].message == "Step 2"
        assert events[1].message == "Step 3"
        assert events[2].message == "Step 4"

    def test_multiple_tasks(self):
        """Can track multiple sequential tasks."""
        reporter = APIProgressReporter()

        # Task 1
        reporter.start_task("Task 1")
        reporter.update_step("Task 1 step")
        reporter.complete_task("Task 1 done")

        # Task 2
        reporter.start_task("Task 2")
        reporter.update_step("Task 2 step")
        reporter.complete_task("Task 2 done")

        events = reporter.get_events()
        assert len(events) == 6

        # Verify sequence
        task1_events = [e for e in events if "Task 1" in e.message]
        task2_events = [e for e in events if "Task 2" in e.message]
        assert len(task1_events) == 3
        assert len(task2_events) == 3


class TestSilentProgressReporter:
    """Test SilentProgressReporter (for testing)."""

    def test_initialization(self):
        """SilentProgressReporter initializes correctly."""
        reporter = SilentProgressReporter()
        assert reporter.track_calls is False
        assert len(reporter.calls) == 0

        # With call tracking
        reporter_tracking = SilentProgressReporter(track_calls=True)
        assert reporter_tracking.track_calls is True

    def test_no_output_without_tracking(self):
        """SilentProgressReporter produces no output when not tracking."""
        reporter = SilentProgressReporter(track_calls=False)

        # Should not raise any errors
        reporter.start_task("Task")
        reporter.update_step("Step")
        reporter.complete_step("Step done")
        reporter.complete_task("Done")
        reporter.fail_task("Error")

        # No calls tracked
        assert len(reporter.calls) == 0

    def test_call_tracking(self):
        """SilentProgressReporter tracks calls when enabled."""
        reporter = SilentProgressReporter(track_calls=True)

        reporter.start_task("Test Task", total_steps=3)
        reporter.update_step("Step 1", step=1, progress=0.33)
        reporter.update_step("Step 2", step=2, progress=0.67)
        reporter.complete_task("Done", duration=5.0)

        assert len(reporter.calls) == 4

        # Verify call structure: (method_name, message, kwargs)
        assert reporter.calls[0][0] == "start_task"
        assert reporter.calls[0][1] == "Test Task"
        assert reporter.calls[0][2] == {"total_steps": 3}

        assert reporter.calls[1][0] == "update_step"
        assert reporter.calls[1][1] == "Step 1"
        assert reporter.calls[1][2] == {"step": 1, "progress": 0.33}

        assert reporter.calls[2][0] == "update_step"
        assert reporter.calls[2][1] == "Step 2"
        assert reporter.calls[2][2] == {"step": 2, "progress": 0.67}

        assert reporter.calls[3][0] == "complete_task"
        assert reporter.calls[3][1] == "Done"
        assert reporter.calls[3][2] == {"duration": 5.0}

    def test_fail_step_tracking(self):
        """SilentProgressReporter tracks fail_step calls."""
        reporter = SilentProgressReporter(track_calls=True)
        exc = ValueError("Test error")

        reporter.fail_step("Something failed", error=exc)

        assert len(reporter.calls) == 1
        assert reporter.calls[0][0] == "fail_step"
        assert reporter.calls[0][1] == "Something failed"
        assert reporter.calls[0][2] == {"error": exc}

    def test_clear_calls(self):
        """Calls can be cleared."""
        reporter = SilentProgressReporter(track_calls=True)

        reporter.start_task("Task")
        reporter.update_step("Step")
        assert len(reporter.calls) == 2

        reporter.calls.clear()
        assert len(reporter.calls) == 0


class TestProgressReporterIntegration:
    """Integration tests with actual engines."""

    def test_with_transcribe_engine(self):
        """ProgressReporter works with TranscribeEngine."""
        # Skip if faster-whisper not installed
        pytest.importorskip("faster_whisper")

        from podx.core.transcribe import TranscriptionEngine

        reporter = SilentProgressReporter(track_calls=True)
        engine = TranscriptionEngine(model="tiny", progress=reporter)

        # Verify reporter was accepted
        assert engine.progress is reporter

        # Note: Actual transcription requires audio file, tested in test_core_transcribe.py
        # Here we just verify the integration works

    def test_with_preprocess_engine(self):
        """ProgressReporter works with PreprocessEngine."""
        from podx.core.preprocess import TranscriptPreprocessor
        from podx.llm import MockLLMProvider

        reporter = SilentProgressReporter(track_calls=True)
        mock_llm = MockLLMProvider(
            responses=["Cleaned text 1", "Cleaned text 2", "Cleaned text 3"]
        )

        preprocessor = TranscriptPreprocessor(
            restore=True,
            restore_batch_size=2,
            llm_provider=mock_llm,
            progress=reporter,
        )

        # Process transcript
        transcript = {
            "segments": [
                {"text": "text 1", "start": 0.0, "end": 1.0},
                {"text": "text 2", "start": 1.0, "end": 2.0},
                {"text": "text 3", "start": 2.0, "end": 3.0},
            ]
        }

        preprocessor.preprocess(transcript)

        # Verify progress updates were made
        assert len(reporter.calls) > 0

        # Check for batch progress reporting
        update_calls = [c for c in reporter.calls if c[0] == "update_step"]
        assert len(update_calls) > 0

        # Verify progress values are valid
        for method, message, kwargs in reporter.calls:
            if "progress" in kwargs:
                assert 0.0 <= kwargs["progress"] <= 1.0
            if "step" in kwargs and kwargs["step"] is not None:
                assert kwargs["step"] > 0

    def test_with_deepcast_engine(self):
        """ProgressReporter works with DeepcastEngine."""
        from podx.core.deepcast import DeepcastEngine
        from podx.llm import MockLLMProvider

        # Use APIProgressReporter to verify progress updates
        reporter = APIProgressReporter()

        mock_llm = MockLLMProvider(responses=["Analysis result", "Final summary"])

        engine = DeepcastEngine(
            model="gpt-4", llm_provider=mock_llm, progress=reporter
        )

        # Verify reporter was accepted
        assert engine.progress is reporter

        # Small transcript for testing
        transcript = {
            "segments": [
                {"text": "Test segment 1", "start": 0.0, "end": 1.0},
                {"text": "Test segment 2", "start": 1.0, "end": 2.0},
            ]
        }

        markdown, json_data = engine.deepcast(
            transcript,
            system_prompt="Analyze this",
            map_instructions="Summarize",
            reduce_instructions="Combine",
        )

        # Verify progress updates were made
        events = reporter.get_events()
        assert len(events) > 0

        # DeepcastEngine reports chunk processing and synthesis
        messages = [e.message for e in events]
        assert any("chunk" in m.lower() or "synthesis" in m.lower() for m in messages)

    def test_legacy_callback_compatibility(self):
        """Legacy callback functions still work."""
        from podx.core.transcribe import TranscriptionEngine

        call_log = []

        def legacy_callback(message: str):
            call_log.append(message)

        # Should work with progress_callback parameter
        engine = TranscriptionEngine(model="tiny", progress_callback=legacy_callback)
        assert engine.progress_callback is legacy_callback

        # Should also work via progress parameter (auto-detected as callable)
        engine2 = TranscriptionEngine(model="tiny", progress=legacy_callback)
        assert engine2.progress_callback is legacy_callback


class TestProgressReporterEdgeCases:
    """Test edge cases and error conditions."""

    def test_api_reporter_empty_get_events(self):
        """get_events on empty reporter returns empty list."""
        reporter = APIProgressReporter()
        events = reporter.get_events()
        assert events == []

    def test_api_reporter_get_events_future_timestamp(self):
        """get_events with future timestamp returns empty list."""
        reporter = APIProgressReporter()
        reporter.start_task("Task")

        future_timestamp = time.time() + 1000
        events = reporter.get_events(since=future_timestamp)
        assert events == []

    def test_silent_reporter_no_tracking_clear(self):
        """Clearing calls on non-tracking reporter is safe."""
        reporter = SilentProgressReporter(track_calls=False)
        reporter.calls.clear()  # Should not raise
        assert len(reporter.calls) == 0

    def test_progress_values_boundary(self):
        """Progress values at boundaries (0.0 and 1.0) work correctly."""
        reporter = APIProgressReporter()

        reporter.update_step("Start", progress=0.0)
        reporter.update_step("End", progress=1.0)

        events = reporter.get_events()
        assert events[0].progress == 0.0
        assert events[1].progress == 1.0

    def test_none_optional_parameters(self):
        """None values for optional parameters work correctly."""
        reporter = APIProgressReporter()

        reporter.start_task("Task", total_steps=None)
        reporter.update_step("Step", step=None, progress=None)
        reporter.complete_step("Done", duration=None)
        reporter.complete_task("Complete", duration=None)
        reporter.fail_task("Error", error=None)

        # All should succeed
        assert len(reporter.events) == 5
