"""Unit tests for _build_pipeline_config() helper function."""



from podx.orchestrate import _build_pipeline_config


def test_basic_config_building():
    """Test basic configuration building with default values."""
    config = _build_pipeline_config(
        show="Test Podcast",
        rss_url=None,
        youtube_url=None,
        date=None,
        title_contains=None,
        workdir=None,
        fmt="wav16",
        model="base",
        compute="int8",
        asr_provider="auto",
        preset=None,
        align=False,
        preprocess=False,
        restore=False,
        diarize=False,
        deepcast=False,
        workflow=None,
        fidelity=None,
        dual=False,
        no_consensus=False,
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        extract_markdown=False,
        deepcast_pdf=False,
        notion=False,
        notion_db=None,
        podcast_prop="Podcast",
        date_prop="Date",
        episode_prop="Episode",
        model_prop="Model",
        asr_prop="ASR",
        append_content=False,
        full=False,
        verbose=False,
        clean=False,
        no_keep_audio=False,
    )

    assert config["show"] == "Test Podcast"
    assert config["model"] == "base"
    assert config["fmt"] == "wav16"
    assert config["align"] is False
    assert config["deepcast"] is False
    assert config["dual"] is False


def test_full_flag_transformation():
    """Test that --full flag enables all full pipeline features."""
    config = _build_pipeline_config(
        show="Test Podcast",
        rss_url=None,
        youtube_url=None,
        date=None,
        title_contains=None,
        workdir=None,
        fmt="wav16",
        model="base",
        compute="int8",
        asr_provider="auto",
        preset=None,
        align=False,  # Should be overridden to True
        preprocess=False,
        restore=False,
        diarize=False,
        deepcast=False,  # Should be overridden to True
        workflow=None,
        fidelity=None,
        dual=False,
        no_consensus=False,
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        extract_markdown=False,  # Should be overridden to True
        deepcast_pdf=False,
        notion=False,  # Should be overridden to True
        notion_db=None,
        podcast_prop="Podcast",
        date_prop="Date",
        episode_prop="Episode",
        model_prop="Model",
        asr_prop="ASR",
        append_content=False,
        full=True,  # Enable full pipeline
        verbose=False,
        clean=False,
        no_keep_audio=False,
    )

    assert config["align"] is True
    assert config["deepcast"] is True
    assert config["extract_markdown"] is True
    assert config["notion"] is True


def test_fidelity_level_1():
    """Test fidelity level 1: deepcast only (fastest)."""
    config = _build_pipeline_config(
        show="Test Podcast",
        rss_url=None,
        youtube_url=None,
        date=None,
        title_contains=None,
        workdir=None,
        fmt="wav16",
        model="base",
        compute="int8",
        asr_provider="auto",
        preset=None,
        align=False,
        preprocess=False,
        restore=False,
        diarize=False,
        deepcast=False,
        workflow=None,
        fidelity="1",  # Deepcast only
        dual=False,
        no_consensus=False,
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        extract_markdown=False,
        deepcast_pdf=False,
        notion=False,
        notion_db=None,
        podcast_prop="Podcast",
        date_prop="Date",
        episode_prop="Episode",
        model_prop="Model",
        asr_prop="ASR",
        append_content=False,
        full=False,
        verbose=False,
        clean=False,
        no_keep_audio=False,
    )

    assert config["deepcast"] is True
    assert config["preprocess"] is False
    assert config["align"] is False
    assert config["dual"] is False


def test_fidelity_level_5_dual_mode():
    """Test fidelity level 5: dual QA mode (best quality)."""
    config = _build_pipeline_config(
        show="Test Podcast",
        rss_url=None,
        youtube_url=None,
        date=None,
        title_contains=None,
        workdir=None,
        fmt="wav16",
        model="base",
        compute="int8",
        asr_provider="auto",
        preset=None,
        align=False,
        preprocess=False,
        restore=False,
        diarize=False,
        deepcast=False,
        workflow=None,
        fidelity="5",  # Dual QA mode
        dual=False,
        no_consensus=False,
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        extract_markdown=False,
        deepcast_pdf=False,
        notion=False,
        notion_db=None,
        podcast_prop="Podcast",
        date_prop="Date",
        episode_prop="Episode",
        model_prop="Model",
        asr_prop="ASR",
        append_content=False,
        full=False,
        verbose=False,
        clean=False,
        no_keep_audio=False,
    )

    assert config["dual"] is True
    assert config["preprocess"] is True
    assert config["restore"] is True
    assert config["deepcast"] is True


def test_workflow_quick():
    """Test workflow preset: quick (fetch + transcribe)."""
    config = _build_pipeline_config(
        show="Test Podcast",
        rss_url=None,
        youtube_url=None,
        date=None,
        title_contains=None,
        workdir=None,
        fmt="wav16",
        model="base",
        compute="int8",
        asr_provider="auto",
        preset=None,
        align=False,
        preprocess=False,
        restore=False,
        diarize=False,
        deepcast=False,
        workflow="quick",  # Quick workflow
        fidelity=None,
        dual=False,
        no_consensus=False,
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        extract_markdown=False,
        deepcast_pdf=False,
        notion=False,
        notion_db=None,
        podcast_prop="Podcast",
        date_prop="Date",
        episode_prop="Episode",
        model_prop="Model",
        asr_prop="ASR",
        append_content=False,
        full=False,
        verbose=False,
        clean=False,
        no_keep_audio=False,
    )

    # Quick workflow should not enable alignment, diarization, or deepcast
    assert config["align"] is False
    assert config["diarize"] is False
    assert config["deepcast"] is False


def test_workflow_and_fidelity_combination():
    """Test that workflow and fidelity can be combined."""
    config = _build_pipeline_config(
        show="Test Podcast",
        rss_url=None,
        youtube_url=None,
        date=None,
        title_contains=None,
        workdir=None,
        fmt="wav16",
        model="base",
        compute="int8",
        asr_provider="auto",
        preset=None,
        align=False,
        preprocess=False,
        restore=False,
        diarize=False,
        deepcast=False,
        workflow="analyze",  # Analyze workflow
        fidelity="4",  # Balanced fidelity
        dual=False,
        no_consensus=False,
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        extract_markdown=False,
        deepcast_pdf=False,
        notion=False,
        notion_db=None,
        podcast_prop="Podcast",
        date_prop="Date",
        episode_prop="Episode",
        model_prop="Model",
        asr_prop="ASR",
        append_content=False,
        full=False,
        verbose=False,
        clean=False,
        no_keep_audio=False,
    )

    # Both workflow and fidelity settings should be applied
    assert config["deepcast"] is True
    assert config["preprocess"] is True
    assert config["restore"] is True


def test_all_configuration_keys_present():
    """Test that config dict contains all expected keys."""
    config = _build_pipeline_config(
        show="Test Podcast",
        rss_url=None,
        youtube_url=None,
        date=None,
        title_contains=None,
        workdir=None,
        fmt="wav16",
        model="base",
        compute="int8",
        asr_provider="auto",
        preset=None,
        align=False,
        preprocess=False,
        restore=False,
        diarize=False,
        deepcast=False,
        workflow=None,
        fidelity=None,
        dual=False,
        no_consensus=False,
        deepcast_model="gpt-4",
        deepcast_temp=0.7,
        extract_markdown=False,
        deepcast_pdf=False,
        notion=False,
        notion_db=None,
        podcast_prop="Podcast",
        date_prop="Date",
        episode_prop="Episode",
        model_prop="Model",
        asr_prop="ASR",
        append_content=False,
        full=False,
        verbose=False,
        clean=False,
        no_keep_audio=False,
    )

    # Check all required keys are present
    required_keys = [
        "show",
        "rss_url",
        "youtube_url",
        "date",
        "title_contains",
        "workdir",
        "fmt",
        "model",
        "compute",
        "asr_provider",
        "preset",
        "align",
        "preprocess",
        "restore",
        "diarize",
        "deepcast",
        "dual",
        "no_consensus",
        "deepcast_model",
        "deepcast_temp",
        "extract_markdown",
        "deepcast_pdf",
        "notion",
        "notion_db",
        "podcast_prop",
        "date_prop",
        "episode_prop",
        "model_prop",
        "asr_prop",
        "append_content",
        "verbose",
        "clean",
        "no_keep_audio",
        "yaml_analysis_type",
    ]

    for key in required_keys:
        assert key in config, f"Missing required key: {key}"
