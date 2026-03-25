"""Unit tests for podx.core.backfill module."""

import json

import pytest

from podx.core.backfill import (
    analysis_needs_rerun,
    build_notion_page_blocks,
    build_notion_properties,
    compute_template_hash,
    detect_format_template,
    find_transcript,
    parse_classification_json,
)
from podx.templates.manager import DeepcastTemplate


@pytest.fixture
def sample_template():
    return DeepcastTemplate(
        name="test",
        description="Test template",
        system_prompt="You are a test analyst.",
        user_prompt="Analyze: {{transcript}}",
        variables=["transcript"],
    )


@pytest.fixture
def sample_classification():
    return {
        "domain_relevance": ["Consulting", "Leadership"],
        "relevance_score": "High",
        "topic_tags": ["ai", "organizational-design", "productivity"],
        "guests": ["John Smith"],
    }


class TestComputeTemplateHash:
    def test_deterministic(self, sample_template):
        hash1 = compute_template_hash(sample_template)
        hash2 = compute_template_hash(sample_template)
        assert hash1 == hash2

    def test_12_chars(self, sample_template):
        h = compute_template_hash(sample_template)
        assert len(h) == 12

    def test_changes_when_prompt_changes(self, sample_template):
        hash1 = compute_template_hash(sample_template)
        modified = DeepcastTemplate(
            name="test",
            description="Test template",
            system_prompt="You are a DIFFERENT analyst.",
            user_prompt="Analyze: {{transcript}}",
            variables=["transcript"],
        )
        hash2 = compute_template_hash(modified)
        assert hash1 != hash2

    def test_includes_map_instructions(self):
        t1 = DeepcastTemplate(
            name="t1",
            description="d",
            system_prompt="s",
            user_prompt="u",
            variables=[],
            map_instructions="map v1",
        )
        t2 = DeepcastTemplate(
            name="t2",
            description="d",
            system_prompt="s",
            user_prompt="u",
            variables=[],
            map_instructions="map v2",
        )
        assert compute_template_hash(t1) != compute_template_hash(t2)


class TestAnalysisNeedsRerun:
    def test_missing_file(self, tmp_path, sample_template):
        assert analysis_needs_rerun(tmp_path / "missing.json", sample_template) is True

    def test_force_flag(self, tmp_path, sample_template):
        path = tmp_path / "analysis.json"
        h = compute_template_hash(sample_template)
        path.write_text(json.dumps({"template_hash": h}))
        assert analysis_needs_rerun(path, sample_template, force=True) is True

    def test_matching_hash_skips(self, tmp_path, sample_template):
        path = tmp_path / "analysis.json"
        h = compute_template_hash(sample_template)
        path.write_text(json.dumps({"template_hash": h}))
        assert analysis_needs_rerun(path, sample_template) is False

    def test_different_hash_reruns(self, tmp_path, sample_template):
        path = tmp_path / "analysis.json"
        path.write_text(json.dumps({"template_hash": "old_hash_1234"}))
        assert analysis_needs_rerun(path, sample_template) is True

    def test_missing_hash_reruns(self, tmp_path, sample_template):
        path = tmp_path / "analysis.json"
        path.write_text(json.dumps({"markdown": "old analysis"}))
        assert analysis_needs_rerun(path, sample_template) is True


class TestParseClassificationJson:
    def test_valid(self, sample_classification):
        md = (
            "## Analysis\n\nSome content\n\n"
            "---CLASSIFICATION---\n"
            + json.dumps(sample_classification)
            + "\n---CLASSIFICATION---\n"
        )
        result = parse_classification_json(md)
        assert result == sample_classification

    def test_with_code_fences(self, sample_classification):
        md = (
            "## Analysis\n\n"
            "---CLASSIFICATION---\n"
            "```json\n"
            + json.dumps(sample_classification)
            + "\n```\n"
            "---CLASSIFICATION---\n"
        )
        result = parse_classification_json(md)
        assert result == sample_classification

    def test_missing_delimiter(self):
        assert parse_classification_json("Just some markdown") is None

    def test_single_delimiter(self):
        assert parse_classification_json("---CLASSIFICATION---\nonly one") is None

    def test_invalid_json(self):
        md = "---CLASSIFICATION---\nnot json\n---CLASSIFICATION---"
        assert parse_classification_json(md) is None

    def test_non_dict_json(self):
        md = '---CLASSIFICATION---\n["a", "b"]\n---CLASSIFICATION---'
        assert parse_classification_json(md) is None


class TestBuildNotionProperties:
    def test_full_classification(self, sample_classification):
        props = build_notion_properties(
            classification=sample_classification,
            templates_run=["interview-1on1", "knowledge-oracle"],
            model="gpt-5.2",
        )

        assert props["Domain Relevance"] == {
            "multi_select": [{"name": "Consulting"}, {"name": "Leadership"}]
        }
        assert props["Relevance Score"] == {"select": {"name": "High"}}
        assert props["Tags"] == {
            "multi_select": [
                {"name": "ai"},
                {"name": "organizational-design"},
                {"name": "productivity"},
            ]
        }
        assert props["Guest(s)"]["rich_text"][0]["text"]["content"] == "John Smith"
        assert props["Template Used"]["rich_text"][0]["text"]["content"] == "interview-1on1, knowledge-oracle"
        assert props["Has Transcript"] == {"checkbox": True}

    def test_tags_is_full_replacement(self, sample_classification):
        """Tags should be a complete replacement, not merged with old values."""
        props = build_notion_properties(
            classification=sample_classification,
            templates_run=["knowledge-oracle"],
            model="gpt-5.2",
        )
        # The Tags property should contain exactly the classification tags
        tag_names = [t["name"] for t in props["Tags"]["multi_select"]]
        assert tag_names == ["ai", "organizational-design", "productivity"]

    def test_no_classification(self):
        props = build_notion_properties(
            classification=None,
            templates_run=["general"],
            model="gpt-5.2",
        )
        assert "Domain Relevance" not in props
        assert "Relevance Score" not in props
        assert "Tags" not in props
        assert "Guest(s)" not in props
        assert props["Has Transcript"] == {"checkbox": True}

    def test_invalid_domains_filtered(self):
        classification = {"domain_relevance": ["Consulting", "InvalidDomain"]}
        props = build_notion_properties(
            classification=classification,
            templates_run=[],
            model="gpt-5.2",
        )
        assert props["Domain Relevance"] == {"multi_select": [{"name": "Consulting"}]}

    def test_source_url(self):
        props = build_notion_properties(
            classification=None,
            templates_run=[],
            model="gpt-5.2",
            source_url="https://example.com/feed.xml",
        )
        assert props["Source URL"] == {"url": "https://example.com/feed.xml"}


class TestBuildNotionPageBlocks:
    def test_with_both_analyses(self):
        blocks = build_notion_page_blocks(
            format_analysis_md="## Summary\nGreat episode.",
            oracle_analysis_md="## Frameworks\nSome framework.",
            transcript=None,
        )
        # Should have blocks from both + divider
        assert any(b.get("type") == "divider" for b in blocks)
        assert len(blocks) >= 3  # at least heading + paragraph per analysis + divider

    def test_with_transcript(self):
        transcript = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello.", "speaker": "Alice"},
                {"start": 5.0, "end": 10.0, "text": "Hi.", "speaker": "Bob"},
            ]
        }
        blocks = build_notion_page_blocks(
            format_analysis_md="## Summary\nTest.",
            oracle_analysis_md=None,
            transcript=transcript,
        )
        # Should have toggle block(s) for transcript
        assert any(b.get("type") == "toggle" for b in blocks)

    def test_strips_classification_from_display(self):
        oracle_md = (
            "## Frameworks\nSome insight.\n\n"
            "---CLASSIFICATION---\n"
            '{"domain_relevance": ["Consulting"]}\n'
            "---CLASSIFICATION---\n"
        )
        blocks = build_notion_page_blocks(
            format_analysis_md=None,
            oracle_analysis_md=oracle_md,
            transcript=None,
        )
        # Classification block should not appear in the rendered blocks
        all_text = " ".join(
            rt.get("text", {}).get("content", "")
            for b in blocks
            for rt in b.get(b.get("type", ""), {}).get("rich_text", [])
        )
        assert "CLASSIFICATION" not in all_text

    def test_no_content(self):
        blocks = build_notion_page_blocks(None, None, None)
        assert blocks == []


class TestFindTranscript:
    def test_standard_name(self, tmp_path):
        (tmp_path / "transcript.json").write_text("{}")
        assert find_transcript(tmp_path) == tmp_path / "transcript.json"

    def test_diarized_fallback(self, tmp_path):
        (tmp_path / "transcript-diarized-large-v3.json").write_text("{}")
        assert find_transcript(tmp_path) is not None

    def test_no_transcript(self, tmp_path):
        assert find_transcript(tmp_path) is None


class TestDetectFormatTemplate:
    def test_general_fallback(self):
        transcript = {"segments": []}
        meta = {}
        assert detect_format_template(transcript, meta) == "general"
