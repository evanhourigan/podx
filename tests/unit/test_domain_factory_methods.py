"""Tests for PipelineConfig factory methods."""


from podx.domain import PipelineConfig
from podx.domain.enums import ASRPreset


class TestFromFidelity:
    """Test PipelineConfig.from_fidelity() factory method."""

    def test_fidelity_1_deepcast_only(self):
        """Test fidelity level 1: deepcast only (fastest)."""
        config = PipelineConfig.from_fidelity(1)

        assert config.align is False
        assert config.diarize is False
        assert config.preprocess is False
        assert config.dual is False
        assert config.deepcast is True
        assert config.restore is False

    def test_fidelity_2_recall_preset(self):
        """Test fidelity level 2: recall preset + enhancements."""
        config = PipelineConfig.from_fidelity(2)

        assert config.preset == ASRPreset.RECALL
        assert config.preprocess is True
        assert config.restore is True
        assert config.deepcast is True
        assert config.dual is False

    def test_fidelity_3_precision_preset(self):
        """Test fidelity level 3: precision preset + enhancements."""
        config = PipelineConfig.from_fidelity(3)

        assert config.preset == ASRPreset.PRECISION
        assert config.preprocess is True
        assert config.restore is True
        assert config.deepcast is True
        assert config.dual is False

    def test_fidelity_4_balanced_preset(self):
        """Test fidelity level 4: balanced preset + enhancements (recommended)."""
        config = PipelineConfig.from_fidelity(4)

        assert config.preset == ASRPreset.BALANCED
        assert config.preprocess is True
        assert config.restore is True
        assert config.deepcast is True
        assert config.dual is False

    def test_fidelity_5_dual_mode(self):
        """Test fidelity level 5: dual QA mode (best quality)."""
        config = PipelineConfig.from_fidelity(5)

        assert config.dual is True
        assert config.preprocess is True
        assert config.restore is True
        assert config.deepcast is True
        # Preset should default to balanced in dual mode
        assert config.preset == ASRPreset.BALANCED

    def test_fidelity_with_kwargs_override(self):
        """Test that kwargs can override fidelity defaults."""
        config = PipelineConfig.from_fidelity(
            4,
            show="Test Podcast",
            deepcast_model="gpt-4o",
        )

        # Fidelity settings applied
        assert config.preset == ASRPreset.BALANCED
        assert config.deepcast is True

        # Kwargs override defaults
        assert config.show == "Test Podcast"
        assert config.deepcast_model == "gpt-4o"

    def test_fidelity_with_custom_preset(self):
        """Test that fidelity preset overrides kwargs preset.

        Note: Current behavior is that fidelity settings override kwargs.
        This is intentional - fidelity level is the primary preset selector.
        """
        config = PipelineConfig.from_fidelity(4, preset=ASRPreset.PRECISION)

        # Fidelity 4 sets preset=BALANCED, overriding the kwargs
        assert config.preset == ASRPreset.BALANCED

    def test_fidelity_preserves_unrelated_defaults(self):
        """Test that fidelity doesn't change unrelated settings."""
        config = PipelineConfig.from_fidelity(4)

        # These should keep their defaults
        assert config.model == "base"
        assert config.fmt == "wav16"
        assert config.verbose is False


class TestFromWorkflow:
    """Test PipelineConfig.from_workflow() factory method."""

    def test_workflow_quick(self):
        """Test 'quick' workflow: minimal processing."""
        config = PipelineConfig.from_workflow("quick")

        assert config.align is False
        assert config.diarize is False
        assert config.deepcast is False
        assert config.extract_markdown is False
        assert config.notion is False

    def test_workflow_analyze(self):
        """Test 'analyze' workflow: analysis with alignment."""
        config = PipelineConfig.from_workflow("analyze")

        assert config.align is True
        assert config.diarize is False
        assert config.deepcast is True
        assert config.extract_markdown is True

    def test_workflow_publish(self):
        """Test 'publish' workflow: full pipeline with Notion."""
        config = PipelineConfig.from_workflow("publish")

        assert config.align is True
        assert config.diarize is False
        assert config.deepcast is True
        assert config.extract_markdown is True
        assert config.notion is True

    def test_workflow_with_kwargs_override(self):
        """Test that workflow settings override kwargs.

        Note: Current behavior is that workflow settings override kwargs.
        This is intentional - workflow is the primary configuration selector.
        """
        config = PipelineConfig.from_workflow(
            "quick",
            show="My Podcast",
            align=True,  # Try to override (will be overridden by workflow)
        )

        # Workflow settings take precedence
        assert config.deepcast is False  # Quick workflow default
        assert config.align is False  # Quick sets this, overriding kwargs

        # Non-workflow settings from kwargs are preserved
        assert config.show == "My Podcast"

    def test_workflow_preserves_other_defaults(self):
        """Test that workflow doesn't change unrelated settings."""
        config = PipelineConfig.from_workflow("analyze")

        # These should keep their defaults
        assert config.model == "base"
        assert config.fmt == "wav16"
        assert config.verbose is False
        assert config.dual is False


class TestPipelineResult:
    """Test PipelineResult model."""

    def test_to_dict(self):
        """Test PipelineResult.to_dict() conversion."""
        from pathlib import Path
        from podx.domain import PipelineResult

        result = PipelineResult(
            workdir=Path("/tmp/test"),
            steps_completed=["fetch", "transcribe", "deepcast"],
            artifacts={"transcript": "/tmp/test/transcript.json"},
            duration=123.45,
            errors=[],
        )

        result_dict = result.to_dict()

        assert result_dict["workdir"] == "/tmp/test"
        assert result_dict["steps_completed"] == ["fetch", "transcribe", "deepcast"]
        assert result_dict["artifacts"] == {"transcript": "/tmp/test/transcript.json"}
        assert result_dict["duration"] == 123.45
        assert result_dict["errors"] == []

    def test_to_dict_with_errors(self):
        """Test PipelineResult.to_dict() with errors."""
        from pathlib import Path
        from podx.domain import PipelineResult

        result = PipelineResult(
            workdir=Path("/tmp/test"),
            errors=["Error 1", "Error 2"],
        )

        result_dict = result.to_dict()

        assert len(result_dict["errors"]) == 2
        assert "Error 1" in result_dict["errors"]
