"""Tests for workflow preset utilities."""


from podx.domain.enums import ASRPreset
from podx.utils.workflow_presets import apply_fidelity_preset, apply_workflow_preset


class TestApplyFidelityPreset:
    """Test apply_fidelity_preset() delegation to domain layer."""

    def test_fidelity_1_returns_dict(self):
        """Test fidelity 1 returns dict with correct flags."""
        flags = apply_fidelity_preset("1")

        assert isinstance(flags, dict)
        assert flags["align"] is False
        assert flags["diarize"] is False
        assert flags["preprocess"] is False
        assert flags["dual"] is False
        assert flags["deepcast"] is True
        assert flags["restore"] is False

    def test_fidelity_4_uses_enum(self):
        """Test fidelity 4 returns ASRPreset enum (type-safe)."""
        flags = apply_fidelity_preset("4")

        # Should return enum, not string
        assert flags["preset"] == ASRPreset.BALANCED
        assert isinstance(flags["preset"], ASRPreset)
        assert flags["deepcast"] is True
        assert flags["preprocess"] is True

    def test_fidelity_5_dual_mode(self):
        """Test fidelity 5 returns dual mode flags."""
        flags = apply_fidelity_preset("5")

        assert flags["dual"] is True
        assert flags["preset"] == ASRPreset.BALANCED
        assert flags["preprocess"] is True
        assert flags["restore"] is True
        assert flags["deepcast"] is True

    def test_fidelity_with_custom_preset_string(self):
        """Test passing custom preset as string."""
        flags = apply_fidelity_preset("5", current_preset="precision")

        # Should use the passed preset
        assert flags["preset"] == "precision"

    def test_fidelity_with_custom_preset_enum(self):
        """Test passing custom preset as ASRPreset enum."""
        flags = apply_fidelity_preset("1", current_preset=ASRPreset.RECALL)

        # Should use the passed preset
        assert flags["preset"] == ASRPreset.RECALL

    def test_fidelity_2_recall_preset(self):
        """Test fidelity 2 uses recall preset."""
        flags = apply_fidelity_preset("2")

        assert flags["preset"] == ASRPreset.RECALL
        assert flags["preprocess"] is True
        assert flags["restore"] is True
        assert flags["deepcast"] is True

    def test_fidelity_3_precision_preset(self):
        """Test fidelity 3 uses precision preset."""
        flags = apply_fidelity_preset("3")

        assert flags["preset"] == ASRPreset.PRECISION
        assert flags["preprocess"] is True
        assert flags["restore"] is True
        assert flags["deepcast"] is True

    def test_all_fidelity_levels(self):
        """Test all 5 fidelity levels return valid dicts."""
        for level in ["1", "2", "3", "4", "5"]:
            flags = apply_fidelity_preset(level)

            # Should always return dict with expected keys
            assert isinstance(flags, dict)
            assert "preset" in flags
            assert "align" in flags
            assert "diarize" in flags
            assert "preprocess" in flags
            assert "restore" in flags
            assert "deepcast" in flags
            assert "dual" in flags

    def test_delegation_matches_domain(self):
        """Test that delegation returns same values as domain factory."""
        from podx.domain import PipelineConfig

        # Test for fidelity level 4
        domain_config = PipelineConfig.from_fidelity(4)
        utils_flags = apply_fidelity_preset("4")

        # Should match
        assert utils_flags["preset"] == domain_config.preset
        assert utils_flags["align"] == domain_config.align
        assert utils_flags["diarize"] == domain_config.diarize
        assert utils_flags["preprocess"] == domain_config.preprocess
        assert utils_flags["restore"] == domain_config.restore
        assert utils_flags["deepcast"] == domain_config.deepcast
        assert utils_flags["dual"] == domain_config.dual


class TestApplyWorkflowPreset:
    """Test apply_workflow_preset() delegation to domain layer."""

    def test_workflow_quick_returns_dict(self):
        """Test 'quick' workflow returns dict with correct flags."""
        flags = apply_workflow_preset("quick")

        assert isinstance(flags, dict)
        assert flags["align"] is False
        assert flags["diarize"] is False
        assert flags["deepcast"] is False
        assert flags["extract_markdown"] is False
        assert flags["notion"] is False

    def test_workflow_analyze(self):
        """Test 'analyze' workflow returns analysis flags."""
        flags = apply_workflow_preset("analyze")

        assert flags["align"] is True
        assert flags["diarize"] is False
        assert flags["deepcast"] is True
        assert flags["extract_markdown"] is True

    def test_workflow_publish(self):
        """Test 'publish' workflow returns publication flags."""
        flags = apply_workflow_preset("publish")

        assert flags["align"] is True
        assert flags["diarize"] is False
        assert flags["deepcast"] is True
        assert flags["extract_markdown"] is True
        assert flags["notion"] is True

    def test_all_workflows(self):
        """Test all workflows return valid dicts."""
        for workflow in ["quick", "analyze", "publish"]:
            flags = apply_workflow_preset(workflow)

            # Should always return dict with expected keys
            assert isinstance(flags, dict)
            assert "align" in flags
            assert "diarize" in flags
            assert "deepcast" in flags
            assert "extract_markdown" in flags
            assert "notion" in flags

    def test_delegation_matches_domain(self):
        """Test that delegation returns same values as domain factory."""
        from podx.domain import PipelineConfig

        # Test for 'analyze' workflow
        domain_config = PipelineConfig.from_workflow("analyze")
        utils_flags = apply_workflow_preset("analyze")

        # Should match
        assert utils_flags["align"] == domain_config.align
        assert utils_flags["diarize"] == domain_config.diarize
        assert utils_flags["deepcast"] == domain_config.deepcast
        assert utils_flags["extract_markdown"] == domain_config.extract_markdown
        assert utils_flags["notion"] == domain_config.notion
