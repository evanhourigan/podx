"""Tests for quote mining: verbatim validation, quote ID, classification, and rendering."""

import pytest

from podx.core.classify import classify_episode
from podx.core.quotes import (
    _light_normalize,
    generate_quote_id,
    render_quotes_markdown,
    validate_quotes_verbatim,
)
from podx.templates.manager import DeepcastTemplate, TemplateManager


class TestVerbatimValidation:
    """Test quote verbatim validation."""

    def test_exact_match(self):
        """Test that exact substring match sets verbatim=True."""
        transcript = "The best way to predict the future is to invent it."
        quotes = [{"quote": "predict the future is to invent it"}]
        result = validate_quotes_verbatim(quotes, transcript)
        assert result[0]["verbatim"] is True

    def test_no_match(self):
        """Test that non-matching quote sets verbatim=False."""
        transcript = "The best way to predict the future is to invent it."
        quotes = [{"quote": "This quote does not exist in the transcript"}]
        result = validate_quotes_verbatim(quotes, transcript)
        assert result[0]["verbatim"] is False

    def test_smart_quote_normalization(self):
        """Test that smart quotes are normalized for matching."""
        transcript = 'He said "the future is now" and walked away.'
        quotes = [{"quote": "He said \u201cthe future is now\u201d and walked away."}]
        result = validate_quotes_verbatim(quotes, transcript)
        assert result[0]["verbatim"] is True

    def test_whitespace_normalization(self):
        """Test that extra whitespace is collapsed for matching."""
        transcript = "The future  is   now and we   must act."
        quotes = [{"quote": "The future is now and we must act."}]
        result = validate_quotes_verbatim(quotes, transcript)
        assert result[0]["verbatim"] is True

    def test_em_dash_normalization(self):
        """Test that em/en dashes are normalized."""
        transcript = "Life is short - make it count."
        quotes = [{"quote": "Life is short \u2014 make it count."}]
        result = validate_quotes_verbatim(quotes, transcript)
        assert result[0]["verbatim"] is True

    def test_case_sensitivity_preserved(self):
        """Test that case differences cause verbatim=False."""
        transcript = "The Future Is Now"
        quotes = [{"quote": "the future is now"}]
        result = validate_quotes_verbatim(quotes, transcript)
        assert result[0]["verbatim"] is False

    def test_verbatim_sorted_first(self):
        """Test that verbatim quotes come before non-verbatim."""
        transcript = "First quote here. Second quote here."
        quotes = [
            {"quote": "Not in transcript", "rank": 1},
            {"quote": "First quote here", "rank": 2},
            {"quote": "Also not in transcript", "rank": 3},
            {"quote": "Second quote here", "rank": 4},
        ]
        result = validate_quotes_verbatim(quotes, transcript)
        assert result[0]["verbatim"] is True
        assert result[1]["verbatim"] is True
        assert result[2]["verbatim"] is False
        assert result[3]["verbatim"] is False

    def test_empty_quotes_list(self):
        """Test handling of empty quotes list."""
        result = validate_quotes_verbatim([], "Some transcript")
        assert result == []

    def test_empty_transcript(self):
        """Test handling of empty transcript."""
        quotes = [{"quote": "Something"}]
        result = validate_quotes_verbatim(quotes, "")
        assert result[0]["verbatim"] is False

    def test_missing_quote_field(self):
        """Test handling of quote dict without 'quote' key."""
        quotes = [{"title": "No quote field"}]
        result = validate_quotes_verbatim(quotes, "Some transcript")
        assert result[0]["verbatim"] is False


class TestLightNormalize:
    """Test light normalization function."""

    def test_smart_single_quotes(self):
        assert _light_normalize("\u2018hello\u2019") == "'hello'"

    def test_smart_double_quotes(self):
        assert _light_normalize("\u201chello\u201d") == '"hello"'

    def test_em_dash(self):
        assert _light_normalize("a\u2014b") == "a-b"

    def test_en_dash(self):
        assert _light_normalize("a\u2013b") == "a-b"

    def test_whitespace_collapse(self):
        assert _light_normalize("  hello   world  ") == "hello world"

    def test_newline_collapse(self):
        assert _light_normalize("hello\n\nworld") == "hello world"

    def test_no_case_folding(self):
        assert _light_normalize("Hello WORLD") == "Hello WORLD"


class TestQuoteIdGeneration:
    """Test stable quote ID generation."""

    def test_deterministic(self):
        """Test that same input produces same ID."""
        quote = {"speaker": "SPEAKER_00", "start": "00:05:30", "quote": "The future is now"}
        id1 = generate_quote_id(quote)
        id2 = generate_quote_id(quote)
        assert id1 == id2

    def test_different_quotes_different_ids(self):
        """Test that different quotes produce different IDs."""
        q1 = {"speaker": "SPEAKER_00", "start": "00:05:30", "quote": "Quote one"}
        q2 = {"speaker": "SPEAKER_00", "start": "00:05:30", "quote": "Quote two"}
        assert generate_quote_id(q1) != generate_quote_id(q2)

    def test_different_speakers_different_ids(self):
        """Test that different speakers produce different IDs."""
        q1 = {"speaker": "SPEAKER_00", "start": "00:05:30", "quote": "Same quote"}
        q2 = {"speaker": "SPEAKER_01", "start": "00:05:30", "quote": "Same quote"}
        assert generate_quote_id(q1) != generate_quote_id(q2)

    def test_id_length(self):
        """Test that ID is 12 hex characters."""
        quote = {"speaker": "A", "start": "00:00:00", "quote": "Test"}
        qid = generate_quote_id(quote)
        assert len(qid) == 12
        assert all(c in "0123456789abcdef" for c in qid)

    def test_missing_fields_handled(self):
        """Test that missing fields don't cause errors."""
        quote = {"quote": "Just a quote"}
        qid = generate_quote_id(quote)
        assert len(qid) == 12

    def test_empty_quote(self):
        """Test handling of completely empty quote dict."""
        qid = generate_quote_id({})
        assert len(qid) == 12


class TestRenderQuotesMarkdown:
    """Test markdown rendering from quote-miner JSON."""

    @pytest.fixture
    def sample_json(self):
        return {
            "quotes": [
                {
                    "rank": 1,
                    "title": "The Future Is Now",
                    "quote": "The future is already here, it's just not evenly distributed.",
                    "speaker": "SPEAKER_00",
                    "start": "00:12:34",
                    "end": "00:12:52",
                    "context": "Discussing technology adoption curves.",
                    "category": "reframe",
                    "why_it_works": "Reframes inequality as a time problem.",
                    "tags": ["technology", "inequality"],
                    "use_case": "Opening slide for a tech equity talk.",
                    "verbatim": True,
                },
                {
                    "rank": 2,
                    "title": "Build vs Buy",
                    "quote": "If it's not your core competency, don't build it.",
                    "speaker": "SPEAKER_01",
                    "start": "00:25:10",
                    "end": "",
                    "context": "Arguing for focus.",
                    "category": "maxim",
                    "why_it_works": "Simple heuristic for decision-making.",
                    "tags": ["strategy"],
                    "use_case": "Engineering leadership discussions.",
                    "verbatim": False,
                },
            ],
            "episode_summary": "A conversation about tech strategy.",
            "total_candidates_found": 30,
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
        }

    @pytest.fixture
    def sample_meta(self):
        return {
            "episode_title": "Tech Strategy Deep Dive",
            "show": "The Strategy Pod",
            "episode_published": "2025-01-15",
        }

    def test_renders_title(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "# Quote Mining: Tech Strategy Deep Dive" in md

    def test_renders_show_info(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "**Show:** The Strategy Pod" in md

    def test_renders_summary(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "A conversation about tech strategy" in md

    def test_renders_quote_block(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "The future is already here" in md
        assert "SPEAKER_00" in md

    def test_renders_timestamps(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "00:12:34" in md

    def test_renders_category(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "(reframe)" in md

    def test_renders_unverified_marker(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "[unverified]" in md

    def test_renders_verbatim_count(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "1 verbatim" in md
        assert "1 unverified" in md

    def test_renders_tags(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "technology" in md

    def test_renders_speakers_list(self, sample_json, sample_meta):
        md = render_quotes_markdown(sample_json, sample_meta)
        assert "SPEAKER_00, SPEAKER_01" in md

    def test_empty_quotes(self, sample_meta):
        md = render_quotes_markdown({"quotes": []}, sample_meta)
        assert "No quotes extracted" in md

    def test_minimal_meta(self):
        md = render_quotes_markdown(
            {"quotes": [], "episode_summary": ""},
            {},
        )
        assert "Quote Mining:" in md


class TestEpisodeClassifier:
    """Test heuristic episode classification."""

    def test_solo_commentary(self):
        """Single speaker -> solo-commentary."""
        transcript = {
            "segments": [
                {"text": "Welcome to the show.", "speaker": "SPEAKER_00"},
                {"text": "Today I want to talk about AI.", "speaker": "SPEAKER_00"},
                {"text": "Let me explain why this matters.", "speaker": "SPEAKER_00"},
            ]
        }
        result = classify_episode(transcript, {})
        assert result["format"] == "solo-commentary"
        assert result["confidence"] >= 0.8

    def test_interview_with_questions(self):
        """Two speakers, high question ratio -> interview."""
        transcript = {
            "segments": [
                {"text": "Welcome. What got you into AI?", "speaker": "SPEAKER_00"},
                {"text": "I started in college.", "speaker": "SPEAKER_01"},
                {"text": "What's the biggest challenge?", "speaker": "SPEAKER_00"},
                {"text": "Scaling the models.", "speaker": "SPEAKER_01"},
                {"text": "How do you handle that?", "speaker": "SPEAKER_00"},
                {"text": "We use distributed computing.", "speaker": "SPEAKER_01"},
            ]
        }
        result = classify_episode(transcript, {})
        assert result["format"] == "interview-1on1"
        assert result["confidence"] >= 0.6

    def test_panel_discussion(self):
        """Three+ speakers -> panel-discussion."""
        transcript = {
            "segments": [
                {"text": "Let's start the discussion.", "speaker": "SPEAKER_00"},
                {"text": "I think AI is transformative.", "speaker": "SPEAKER_01"},
                {"text": "I disagree, it's overhyped.", "speaker": "SPEAKER_02"},
                {"text": "What about safety?", "speaker": "SPEAKER_03"},
            ]
        }
        result = classify_episode(transcript, {})
        assert result["format"] == "panel-discussion"
        assert result["confidence"] >= 0.6

    def test_no_speakers(self):
        """No speaker labels -> general with low confidence."""
        transcript = {
            "segments": [
                {"text": "Hello world."},
                {"text": "How are you?"},
            ]
        }
        result = classify_episode(transcript, {})
        assert result["format"] == "general"
        assert result["confidence"] <= 0.3

    def test_empty_segments(self):
        """Empty segments -> general with zero confidence."""
        result = classify_episode({"segments": []}, {})
        assert result["format"] == "general"
        assert result["confidence"] == 0.0

    def test_two_speakers_low_questions(self):
        """Two speakers, few questions -> general."""
        transcript = {
            "segments": [
                {"text": "I think this is great.", "speaker": "SPEAKER_00"},
                {"text": "Yeah, absolutely.", "speaker": "SPEAKER_01"},
                {"text": "Let me tell you about it.", "speaker": "SPEAKER_00"},
                {"text": "Sure, go ahead.", "speaker": "SPEAKER_01"},
                {"text": "So it works like this.", "speaker": "SPEAKER_00"},
                {"text": "That makes sense.", "speaker": "SPEAKER_01"},
            ]
        }
        result = classify_episode(transcript, {})
        assert result["format"] == "general"

    def test_evidence_fields_present(self):
        """Test that all evidence fields are populated."""
        transcript = {
            "segments": [
                {"text": "Hello?", "speaker": "SPEAKER_00"},
                {"text": "Hi there.", "speaker": "SPEAKER_01"},
            ]
        }
        result = classify_episode(transcript, {})
        evidence = result["evidence"]
        assert "speaker_count" in evidence
        assert "qa_ratio" in evidence
        assert "avg_turn_length" in evidence
        assert "turn_count" in evidence
        assert "markers" in evidence
        assert isinstance(evidence["markers"], list)


class TestTemplateMapInstructionsOverride:
    """Test that template map_instructions and json_schema are properly exposed."""

    def test_template_with_map_instructions(self):
        """Test that DeepcastTemplate accepts map_instructions."""
        tmpl = DeepcastTemplate(
            name="test-map",
            description="Test",
            system_prompt="System",
            user_prompt="User",
            map_instructions="Custom map instructions for this template.",
        )
        assert tmpl.map_instructions == "Custom map instructions for this template."

    def test_template_without_map_instructions(self):
        """Test that map_instructions defaults to None."""
        tmpl = DeepcastTemplate(
            name="test-default",
            description="Test",
            system_prompt="System",
            user_prompt="User",
        )
        assert tmpl.map_instructions is None

    def test_template_with_json_schema(self):
        """Test that DeepcastTemplate accepts json_schema."""
        tmpl = DeepcastTemplate(
            name="test-schema",
            description="Test",
            system_prompt="System",
            user_prompt="User",
            json_schema='{"type": "object"}',
        )
        assert tmpl.json_schema == '{"type": "object"}'

    def test_template_with_wants_json_only(self):
        """Test that DeepcastTemplate accepts wants_json_only."""
        tmpl = DeepcastTemplate(
            name="test-json-only",
            description="Test",
            system_prompt="System",
            user_prompt="User",
            wants_json_only=True,
        )
        assert tmpl.wants_json_only is True

    def test_wants_json_only_defaults_false(self):
        """Test that wants_json_only defaults to False."""
        tmpl = DeepcastTemplate(
            name="test",
            description="Test",
            system_prompt="System",
            user_prompt="User",
        )
        assert tmpl.wants_json_only is False

    def test_quote_miner_builtin_has_custom_fields(self):
        """Test that the quote-miner built-in template has custom fields set."""
        manager = TemplateManager()
        tmpl = manager.load("quote-miner")
        assert tmpl.map_instructions is not None
        assert "verbatim" in tmpl.map_instructions.lower()
        assert tmpl.json_schema is not None
        assert tmpl.wants_json_only is True

    def test_existing_templates_have_no_map_instructions(self):
        """Test that existing templates don't set map_instructions."""
        manager = TemplateManager()
        tmpl = manager.load("general")
        assert tmpl.map_instructions is None
        assert tmpl.json_schema is None
        assert tmpl.wants_json_only is False

    def test_map_instructions_fallback_logic(self):
        """Test the fallback pattern used in CLI: tmpl.map_instructions or DEFAULT."""
        default = "Default map instructions"
        tmpl_with = DeepcastTemplate(
            name="a",
            description="A",
            system_prompt="S",
            user_prompt="U",
            map_instructions="Custom",
        )
        tmpl_without = DeepcastTemplate(
            name="b",
            description="B",
            system_prompt="S",
            user_prompt="U",
        )

        assert (tmpl_with.map_instructions or default) == "Custom"
        assert (tmpl_without.map_instructions or default) == default
