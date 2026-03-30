"""Unit tests for podx.core.obsidian module."""


import pytest

from podx.core.obsidian import (
    InsightRecord,
    _extract_domain_tags,
    _extract_first_phrase,
    _extract_framework_title,
    _safe_filename,
    _split_by_h2,
    _split_section_items,
    _strip_classification_block,
    _tag_to_topic_name,
    parse_insights,
    publish_to_obsidian,
    update_domain_moc,
    update_speaker_note,
    update_topic_moc,
    write_episode_note,
    write_insight_notes,
)


@pytest.fixture
def vault_path(tmp_path):
    """Create a temporary vault directory."""
    vault = tmp_path / "podcast-brain"
    vault.mkdir()
    for folder in ["Episodes", "Insights", "Topics", "Speakers", "Domains", "Reflections"]:
        (vault / folder).mkdir()
    return vault


@pytest.fixture
def episode_meta():
    return {
        "show": "Test Podcast",
        "episode_title": "The Future of AI",
        "episode_published": "2026-03-15",
        "feed": "https://example.com/feed.xml",
    }


@pytest.fixture
def classification():
    return {
        "domain_relevance": ["Consulting", "Engineering"],
        "relevance_score": "High",
        "topic_tags": ["ai", "productivity", "leadership"],
        "guests": ["Jane Smith"],
    }


@pytest.fixture
def sample_oracle_md():
    return """## Transferable Frameworks

**The Feedback Loop Framework** — A systematic approach to continuous improvement.
Teams that implement rapid feedback cycles ship 3x faster than those with
quarterly reviews. Originally described by the guest as their core practice.

**The Context Layer Pattern** — Instead of giving AI agents raw access,
create a context layer that curates what they see. This prevents hallucination
and improves output quality dramatically.

## Contrarian Insights

- **Conventional view:** More engineers = faster shipping.
  **Contrarian position:** Two engineers with AI agents outperform teams of 15.
  This challenges the entire hiring-for-scale paradigm.

- **Conventional view:** Code review is essential for quality.
  **Contrarian position:** AI-generated code with comprehensive tests is more
  reliable than human-reviewed code without tests.

## Actionable Strategies

- Implement a daily "context dump" practice where you write down everything
  the AI agent needs to know before starting a task [Consulting] [Engineering]
- Use prompt evaluation frameworks to measure AI output quality systematically
  [Engineering] [AI/ML]
- Create a "decision journal" to track AI-assisted vs manual decisions [Personal Development]

## Quotable Insights

> "The best engineers aren't the ones who write the most code — they're the
> ones who write the best prompts." — Jane Smith [00:34:12]

> "We don't hire for skills anymore. We hire for judgment." — Jane Smith [00:45:30]

## Knowledge Connections

- The feedback loop framework echoes Toyota's kaizen philosophy applied to software
- The context layer pattern is essentially information architecture for AI agents,
  similar to how API gateway patterns work in microservices

## Domain-Specific Takeaways

### For Consulting Practice
- The feedback loop framework can be directly applied to client engagement reviews
- Context layer pattern maps to how consultants should structure client briefs

### For Therapy Practice Marketing
- Limited direct relevance — the episode focuses on engineering and AI practices

### For Personal Development
- Daily context dump practice is immediately actionable for any knowledge worker
- Decision journal concept applies to career decisions and personal growth tracking

---CLASSIFICATION---
{"domain_relevance": ["Consulting", "Engineering"], "relevance_score": "High", "topic_tags": ["ai", "productivity"], "guests": ["Jane Smith"]}
---CLASSIFICATION---
"""


class TestSafeFilename:
    def test_removes_unsafe_chars(self):
        assert _safe_filename('Test: A/B "file"') == "Test AB file"

    def test_collapses_spaces(self):
        assert _safe_filename("Too   many   spaces") == "Too many spaces"

    def test_truncates_long_names(self):
        result = _safe_filename("A" * 200)
        assert len(result) <= 150


class TestSplitByH2:
    def test_splits_sections(self):
        md = "## Section One\nContent one.\n\n## Section Two\nContent two."
        result = _split_by_h2(md)
        assert "Section One" in result
        assert "Section Two" in result
        assert "Content one." in result["Section One"]

    def test_empty_content(self):
        result = _split_by_h2("")
        assert result == {}


class TestSplitSectionItems:
    def test_bold_items(self):
        content = "**Item One** — description one.\n\n**Item Two** — description two."
        items = _split_section_items(content)
        assert len(items) == 2

    def test_bullet_items(self):
        content = "- First item here.\n- Second item here.\n- Third item."
        items = _split_section_items(content)
        assert len(items) == 3

    def test_single_item(self):
        content = "Just a single paragraph of text."
        items = _split_section_items(content)
        assert len(items) == 1


class TestExtractFrameworkTitle:
    def test_bold_name_pattern(self):
        item = "**The Feedback Loop** — A systematic approach..."
        assert _extract_framework_title(item) == "The Feedback Loop"

    def test_name_with_colon(self):
        item = "**Name: Context Layer Pattern** — description..."
        assert _extract_framework_title(item) == "Context Layer Pattern"

    def test_fallback_to_first_phrase(self):
        item = "A framework for continuous improvement in teams."
        title = _extract_framework_title(item)
        assert len(title) > 0


class TestExtractFirstPhrase:
    def test_sentence_boundary(self):
        result = _extract_first_phrase("This is the insight. More details follow.")
        assert result == "This is the insight"

    def test_colon_boundary(self):
        result = _extract_first_phrase("Key concept: implement feedback loops daily")
        assert result == "Key concept"

    def test_max_words(self):
        result = _extract_first_phrase(
            "One two three four five six seven eight nine ten", max_words=5
        )
        assert result == "One two three four five"

    def test_strips_bullets(self):
        result = _extract_first_phrase("- Implement daily reviews for better outcomes.")
        assert not result.startswith("-")


class TestExtractDomainTags:
    def test_finds_tags(self):
        item = "Do X for Y [Consulting] [Engineering]"
        assert _extract_domain_tags(item) == ["Consulting", "Engineering"]

    def test_no_tags(self):
        assert _extract_domain_tags("No domain tags here.") == []


class TestStripClassificationBlock:
    def test_strips_block(self):
        md = 'Content before.\n\n---CLASSIFICATION---\n{"key": "val"}\n---CLASSIFICATION---\n'
        result = _strip_classification_block(md)
        assert "CLASSIFICATION" not in result
        assert "Content before." in result

    def test_no_block(self):
        md = "Just regular content."
        assert _strip_classification_block(md) == md


class TestTagToTopicName:
    def test_converts(self):
        assert _tag_to_topic_name("ai-agents") == "Ai Agents"
        assert _tag_to_topic_name("workflow-design") == "Workflow Design"
        assert _tag_to_topic_name("productivity") == "Productivity"


class TestParseInsights:
    def test_parses_frameworks(self, sample_oracle_md, episode_meta, classification):
        insights = parse_insights(sample_oracle_md, episode_meta, classification)
        frameworks = [i for i in insights if i.section_type == "framework"]
        assert len(frameworks) >= 2
        titles = [f.title for f in frameworks]
        assert any("Feedback Loop" in t for t in titles)

    def test_parses_strategies(self, sample_oracle_md, episode_meta, classification):
        insights = parse_insights(sample_oracle_md, episode_meta, classification)
        strategies = [i for i in insights if i.section_type == "strategy"]
        assert len(strategies) >= 2
        assert all(s.actionable for s in strategies)

    def test_parses_contrarian(self, sample_oracle_md, episode_meta, classification):
        insights = parse_insights(sample_oracle_md, episode_meta, classification)
        contrarian = [i for i in insights if i.section_type == "contrarian"]
        assert len(contrarian) >= 1

    def test_parses_quotes(self, sample_oracle_md, episode_meta, classification):
        insights = parse_insights(sample_oracle_md, episode_meta, classification)
        quotes = [i for i in insights if i.section_type == "quote"]
        assert len(quotes) >= 1

    def test_all_have_source_episode(self, sample_oracle_md, episode_meta, classification):
        insights = parse_insights(sample_oracle_md, episode_meta, classification)
        for i in insights:
            assert "Test Podcast" in i.source_episode


class TestWriteEpisodeNote:
    def test_creates_file(self, vault_path, episode_meta, classification):
        path = write_episode_note(
            vault_path,
            episode_meta,
            "## Summary\nGreat episode.",
            None,
            classification,
            "gpt-5.1",
            "large-v3-turbo",
        )
        assert path.exists()
        assert path.parent.name == "Episodes"
        content = path.read_text()
        assert "type: episode" in content
        assert "Test Podcast" in content

    def test_frontmatter_has_tags(self, vault_path, episode_meta, classification):
        path = write_episode_note(
            vault_path,
            episode_meta,
            None,
            None,
            classification,
            "gpt-5.1",
        )
        content = path.read_text()
        assert "tags:" in content
        assert "domains:" in content
        assert "relevance_score: High" in content


class TestWriteInsightNotes:
    def test_writes_files(self, vault_path):
        insights = [
            InsightRecord(
                title="Test Insight",
                body="This is a test insight.",
                section_type="framework",
                speaker="Jane",
                topics=["ai"],
                domains=["Consulting"],
                actionable=False,
                source_episode="2026-03-15 - Test - Episode",
                date="2026-03-15",
            )
        ]
        paths = write_insight_notes(vault_path, insights)
        assert len(paths) == 1
        assert paths[0].exists()
        content = paths[0].read_text()
        assert "type: insight" in content
        assert "[[2026-03-15 - Test - Episode]]" in content

    def test_handles_filename_collisions(self, vault_path):
        insights = [
            InsightRecord(
                "Same Title", "Body 1", "framework", None, [], [], False, "Ep", "2026-01-01"
            ),
            InsightRecord(
                "Same Title", "Body 2", "framework", None, [], [], False, "Ep", "2026-01-01"
            ),
        ]
        paths = write_insight_notes(vault_path, insights)
        assert len(paths) == 2
        assert paths[0].stem != paths[1].stem


class TestUpdateSpeakerNote:
    def test_creates_new(self, vault_path):
        update_speaker_note(vault_path, "Jane Smith", "Ep Note", ["Insight 1"])
        path = vault_path / "Speakers" / "Jane Smith.md"
        assert path.exists()
        content = path.read_text()
        assert "[[Ep Note]]" in content
        assert "[[Insight 1]]" in content

    def test_idempotent(self, vault_path):
        update_speaker_note(vault_path, "Jane", "Ep1", ["I1"])
        update_speaker_note(vault_path, "Jane", "Ep1", ["I1"])
        content = (vault_path / "Speakers" / "Jane.md").read_text()
        assert content.count("[[Ep1]]") == 1

    def test_accumulates(self, vault_path):
        update_speaker_note(vault_path, "Jane", "Ep1", ["I1"])
        update_speaker_note(vault_path, "Jane", "Ep2", ["I2"])
        content = (vault_path / "Speakers" / "Jane.md").read_text()
        assert "[[Ep1]]" in content
        assert "[[Ep2]]" in content


class TestUpdateTopicMoc:
    def test_creates_new(self, vault_path):
        update_topic_moc(vault_path, "AI Agents", ["Insight 1"])
        path = vault_path / "Topics" / "AI Agents.md"
        assert path.exists()
        assert "[[Insight 1]]" in path.read_text()

    def test_idempotent(self, vault_path):
        update_topic_moc(vault_path, "AI", ["I1"])
        update_topic_moc(vault_path, "AI", ["I1"])
        content = (vault_path / "Topics" / "AI.md").read_text()
        assert content.count("[[I1]]") == 1


class TestUpdateDomainMoc:
    def test_creates_new(self, vault_path):
        update_domain_moc(vault_path, "Consulting", ["Insight 1"])
        path = vault_path / "Domains" / "Consulting.md"
        assert path.exists()
        assert "[[Insight 1]]" in path.read_text()


class TestPublishToObsidian:
    def test_full_pipeline(self, vault_path, episode_meta, classification, sample_oracle_md):
        publish_to_obsidian(
            vault_path=vault_path,
            episode_meta=episode_meta,
            transcript=None,
            format_md="## Summary\nGreat episode.",
            oracle_md=sample_oracle_md,
            classification=classification,
            model="gpt-5.1",
            asr_model="large-v3-turbo",
            auto_commit=False,  # Don't try to git commit in tests
        )

        # Episode note exists
        episodes = list((vault_path / "Episodes").glob("*.md"))
        assert len(episodes) == 1
        assert "Test Podcast" in episodes[0].read_text()

        # Insight notes exist
        insights = list((vault_path / "Insights").glob("*.md"))
        assert len(insights) > 0

        # Speaker note exists
        assert (vault_path / "Speakers" / "Jane Smith.md").exists()

        # Topic MOCs exist
        topics = list((vault_path / "Topics").glob("*.md"))
        assert len(topics) > 0

        # Domain MOCs exist
        assert (vault_path / "Domains" / "Consulting.md").exists()
        assert (vault_path / "Domains" / "Engineering.md").exists()

    def test_no_oracle_md(self, vault_path, episode_meta, classification):
        """Should still write episode note even without oracle analysis."""
        publish_to_obsidian(
            vault_path=vault_path,
            episode_meta=episode_meta,
            transcript=None,
            format_md="## Summary\nBasic analysis.",
            oracle_md=None,
            classification=classification,
            model="gpt-5.1",
            auto_commit=False,
        )
        episodes = list((vault_path / "Episodes").glob("*.md"))
        assert len(episodes) == 1
