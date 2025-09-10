#!/usr/bin/env python3
"""
Advanced prompt templates for Deepcast AI analysis.
Implements modern prompt engineering techniques for better podcast analysis.
"""

import textwrap
from enum import Enum
from typing import Any, Dict, Optional


class PodcastType(Enum):
    """Podcast types for specialized prompt selection."""

    INTERVIEW = "interview"
    NEWS = "news"
    EDUCATIONAL = "educational"
    TECH = "tech"
    BUSINESS = "business"
    NARRATIVE = "narrative"
    COMEDY = "comedy"
    GENERAL = "general"


class PromptTemplate:
    """Container for a complete prompt template set."""

    def __init__(
        self,
        system_prompt: str,
        map_instructions: str,
        reduce_instructions: str,
        analysis_focus: str,
        example_output: Optional[str] = None,
    ):
        self.system_prompt = system_prompt
        self.map_instructions = map_instructions
        self.reduce_instructions = reduce_instructions
        self.analysis_focus = analysis_focus
        self.example_output = example_output


# Enhanced base system prompt with better role definition
ENHANCED_SYSTEM_BASE = textwrap.dedent(
    """
You are an expert editorial assistant specializing in podcast content analysis and summarization.

Your expertise includes:
- Extracting key insights and actionable information from spoken content
- Identifying novel ideas, surprising perspectives, and valuable quotes
- Creating structured, scannable summaries for busy professionals
- Maintaining faithful representation without speculation or invention

Core principles:
- ACCURACY: Never invent or hallucinate facts, names, or details
- CLARITY: Use clear, concise language that respects the audience's time
- CONTEXT: Provide sufficient background for quotes and insights to be meaningful
- STRUCTURE: Organize information in a logical, scannable format
"""
).strip()


def build_enhanced_variant(
    has_time: bool, has_speaker: bool, podcast_type: PodcastType = PodcastType.GENERAL
) -> str:
    """Build context-aware analysis instructions."""

    # Timing context
    time_instruction = (
        "- Include precise [HH:MM:SS] timestamps for all quotes and key moments"
        if has_time
        else "- Timestamps unavailable; focus on content organization and flow"
    )

    # Speaker context
    speaker_instruction = (
        "- Preserve speaker identification (names or labels like [SPEAKER_00])\n"
        "- Note when different speakers express contrasting viewpoints"
        if has_speaker
        else "- Speaker identification unavailable; write in neutral voice"
    )

    # Type-specific analysis focus
    type_focus = get_type_specific_focus(podcast_type)

    return textwrap.dedent(
        f"""
    Create a comprehensive yet concise analysis of this podcast transcript.
    
    Context handling:
    {time_instruction}
    {speaker_instruction}
    
    Analysis focus:
    {type_focus}
    
    Required structure (only include sections with substantial content):
    
    ## 📋 Executive Summary
    Write 4-8 sentences capturing the episode's main value proposition. What would a busy executive need to know?
    
    ## 🎯 Key Insights  
    12-20 bullet points of substantive takeaways. Each bullet should be:
    - One clear insight or finding
    - 2-3 sentences with sufficient context
    - Actionable or intellectually valuable
    
    ## 💎 Gold Nuggets
    6-12 surprising, counterintuitive, or novel ideas that stood out. Include:
    - Why this insight is valuable or unexpected
    - Sufficient context for understanding
    - Connection to broader implications where relevant
    
    ## 💬 Notable Quotes
    Select 4-8 most impactful quotes that are:
    - Memorable, insightful, or quotable
    - Representative of key themes
    - Include speaker and timestamp when available
    - Prefer complete thoughts over fragments
    
    ## ⚡ Action Items
    Concrete next steps, resources, or recommendations mentioned:
    - Tools, books, or resources specifically mentioned
    - Actionable advice or strategies
    - Follow-up suggestions
    
    ## 🗂️ Timestamp Outline
    10-15 major sections with timestamps:
    - Focus on topic transitions and key moments
    - Use descriptive labels that aid navigation
    - Balance granularity with usefulness
    
    Quality standards:
    - Use specific, descriptive language
    - Maintain the speaker's voice and terminology
    - Provide sufficient context for standalone reading
    - Prioritize information density and scannability
    """
    ).strip()


def get_type_specific_focus(podcast_type: PodcastType) -> str:
    """Get analysis focus based on podcast type."""

    focus_map = {
        PodcastType.INTERVIEW: """
        - Extract the guest's unique perspectives and expertise
        - Highlight personal stories, career insights, and lessons learned
        - Focus on advice, frameworks, and methodologies shared
        - Note interesting background details that provide context""",
        PodcastType.NEWS: """
        - Identify key facts, developments, and their implications
        - Extract analysis and expert commentary on events
        - Highlight predictions, trends, and forward-looking statements
        - Note different perspectives on controversial topics""",
        PodcastType.EDUCATIONAL: """
        - Extract core concepts, frameworks, and learning objectives
        - Identify step-by-step processes and methodologies
        - Highlight examples, case studies, and practical applications
        - Note resources for further learning""",
        PodcastType.TECH: """
        - Focus on technical insights, tools, and emerging trends
        - Extract implementation details and architectural decisions
        - Highlight product announcements and market analysis
        - Note technical resources and community insights""",
        PodcastType.BUSINESS: """
        - Extract strategic insights, market analysis, and business models
        - Focus on leadership lessons and operational insights
        - Highlight metrics, growth strategies, and competitive analysis
        - Note investment perspectives and market opportunities""",
        PodcastType.NARRATIVE: """
        - Follow story arc and character development
        - Extract thematic insights and broader lessons
        - Highlight dramatic moments and emotional beats
        - Note investigative findings or revelations""",
        PodcastType.COMEDY: """
        - Capture humorous observations and comedic insights
        - Extract social commentary embedded in humor
        - Highlight memorable jokes and comedic premises
        - Note genuine insights between the entertainment""",
        PodcastType.GENERAL: """
        - Adapt analysis style to the content's natural structure
        - Focus on the most valuable and actionable information
        - Extract insights relevant to the apparent target audience
        - Maintain flexibility in emphasis based on content themes""",
    }

    return focus_map.get(podcast_type, focus_map[PodcastType.GENERAL])


# Enhanced map instructions with better chunking strategy
ENHANCED_MAP_INSTRUCTIONS = textwrap.dedent(
    """
Analyze this transcript chunk and extract key information. Be precise and context-aware.

Extract:
📋 **Core Points**: 3-6 substantial insights from this chunk
💎 **Standout Ideas**: 2-4 surprising, novel, or particularly valuable concepts  
💬 **Best Quotes**: 1-3 most impactful quotes (with context about why they're notable)
⚡ **Actionables**: Any specific tools, resources, or next steps mentioned

Format as clean Markdown. Focus on this chunk only—don't attempt episode-wide synthesis.

Quality criteria:
- Each point should be self-contained and meaningful
- Provide enough context for quotes to be understood standalone
- Prefer complete thoughts over fragments
- Use the speaker's actual terminology and phrasing
"""
).strip()


# Enhanced reduce instructions with better synthesis guidance
ENHANCED_REDUCE_INSTRUCTIONS = textwrap.dedent(
    """
Synthesize the chunk analyses into a cohesive, comprehensive episode brief.

Synthesis strategy:
1. **Deduplicate intelligently**: Merge similar points, don't just delete duplicates
2. **Organize thematically**: Group related insights together
3. **Maintain narrative flow**: Present ideas in logical order
4. **Preserve nuance**: Don't oversimplify complex topics
5. **Balance breadth and depth**: Cover all major themes while diving deep on the most valuable insights

Quality checks:
- Does each section provide genuine value to readers?
- Are insights actionable or intellectually stimulating?
- Is there sufficient context for standalone comprehension?
- Does the summary respect the speaker's intent and expertise?

Follow the structure requirements from the earlier instructions exactly.
"""
).strip()


# Enhanced JSON schema with more detailed structure
ENHANCED_JSON_SCHEMA = textwrap.dedent(
    """
After your Markdown analysis, provide a structured JSON object for programmatic use:

{
  "summary": "4-6 sentence executive summary capturing main value",
  "key_points": [
    "Specific insight with context (2-3 sentences each)"
  ],
  "gold_nuggets": [
    "Surprising or counterintuitive insight with explanation"
  ],
  "quotes": [
    {
      "quote": "Exact quote text",
      "speaker": "Speaker name or label",
      "time": "HH:MM:SS or null",
      "context": "Why this quote is notable"
    }
  ],
  "actions": [
    "Specific actionable items, tools, or resources mentioned"
  ],
  "outline": [
    {
      "label": "Descriptive section title",
      "time": "HH:MM:SS or null",
      "description": "Brief content summary"
    }
  ],
  "metadata": {
    "total_insights": "number",
    "primary_themes": ["theme1", "theme2"],
    "content_type": "interview|discussion|presentation|other"
  }
}

Separate with: ---JSON---
"""
).strip()


# Template collection
TEMPLATES = {
    PodcastType.INTERVIEW: PromptTemplate(
        system_prompt=ENHANCED_SYSTEM_BASE
        + "\n\nSpecialization: Interview analysis with focus on guest expertise and personal insights.",
        map_instructions=ENHANCED_MAP_INSTRUCTIONS
        + "\n\nPrioritize: Guest's unique perspectives, advice, and personal anecdotes.",
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS
        + "\n\nEmphasize: The guest's expertise and actionable advice for listeners.",
        analysis_focus="Extract maximum value from the guest's expertise and experience sharing.",
    ),
    PodcastType.TECH: PromptTemplate(
        system_prompt=ENHANCED_SYSTEM_BASE
        + "\n\nSpecialization: Technical content analysis with focus on tools, trends, and implementation.",
        map_instructions=ENHANCED_MAP_INSTRUCTIONS
        + "\n\nPrioritize: Technical insights, tools mentioned, and implementation details.",
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS
        + "\n\nEmphasize: Actionable technical information and emerging trends.",
        analysis_focus="Focus on technical depth, practical implementation, and industry trends.",
    ),
    PodcastType.BUSINESS: PromptTemplate(
        system_prompt=ENHANCED_SYSTEM_BASE
        + "\n\nSpecialization: Business content analysis with focus on strategy, growth, and market insights.",
        map_instructions=ENHANCED_MAP_INSTRUCTIONS
        + "\n\nPrioritize: Strategic insights, business models, and market analysis.",
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS
        + "\n\nEmphasize: Strategic takeaways and business-applicable insights.",
        analysis_focus="Extract strategic business insights and actionable growth strategies.",
    ),
    PodcastType.GENERAL: PromptTemplate(
        system_prompt=ENHANCED_SYSTEM_BASE,
        map_instructions=ENHANCED_MAP_INSTRUCTIONS,
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS,
        analysis_focus="Adapt analysis to content type and maximize value extraction.",
    ),
}


def get_template(podcast_type: PodcastType = PodcastType.GENERAL) -> PromptTemplate:
    """Get the appropriate template for the podcast type."""
    return TEMPLATES.get(podcast_type, TEMPLATES[PodcastType.GENERAL])


def detect_podcast_type(transcript: Dict[str, Any]) -> PodcastType:
    """Attempt to detect podcast type from metadata and content."""

    # Check show name for obvious indicators
    show_name = (transcript.get("show") or transcript.get("show_name", "")).lower()
    episode_title = (
        transcript.get("episode_title") or transcript.get("title", "")
    ).lower()

    combined_text = f"{show_name} {episode_title}"

    # Simple keyword-based detection
    if any(
        word in combined_text for word in ["interview", "talk", "conversation", "chat"]
    ):
        return PodcastType.INTERVIEW
    elif any(word in combined_text for word in ["news", "update", "daily", "weekly"]):
        return PodcastType.NEWS
    elif any(
        word in combined_text
        for word in ["tech", "startup", "coding", "dev", "ai", "software"]
    ):
        return PodcastType.TECH
    elif any(
        word in combined_text
        for word in ["business", "entrepreneur", "ceo", "strategy", "growth"]
    ):
        return PodcastType.BUSINESS
    elif any(
        word in combined_text
        for word in ["learn", "education", "course", "tutorial", "guide"]
    ):
        return PodcastType.EDUCATIONAL
    elif any(
        word in combined_text
        for word in ["story", "investigation", "documentary", "narrative"]
    ):
        return PodcastType.NARRATIVE
    elif any(word in combined_text for word in ["comedy", "humor", "funny", "laugh"]):
        return PodcastType.COMEDY

    return PodcastType.GENERAL
