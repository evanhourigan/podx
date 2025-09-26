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
    INTERVIEW_HOST_FOCUSED = "interview_host_focused"  # Focus on host questions
    INTERVIEW_GUEST_FOCUSED = "interview_guest_focused"  # Focus on guest responses
    NEWS = "news"
    EDUCATIONAL = "educational"
    TECH = "tech"
    BUSINESS = "business"
    NARRATIVE = "narrative"
    COMEDY = "comedy"
    SOLO_COMMENTARY = "solo_commentary"  # Single person commentary/thoughts
    PANEL_DISCUSSION = "panel_discussion"  # Multiple equal participants
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
    has_time: bool,
    has_speaker: bool,
    podcast_type: PodcastType = PodcastType.GENERAL,
    episode_duration_minutes: Optional[int] = None,
) -> str:
    """Build context-aware analysis instructions with adaptive content scaling."""

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

    # Adaptive content scaling based on episode length
    content_scaling = get_content_scaling(episode_duration_minutes)

    # Get Q&A target for interview-focused templates
    qa_target = get_qa_target(episode_duration_minutes)
    quotes_target = get_quotes_target(episode_duration_minutes)

    return textwrap.dedent(
        f"""
    Create a comprehensive yet concise analysis of this podcast transcript.
    
    Context handling:
    {time_instruction}
    {speaker_instruction}
    
    Analysis focus:
    {type_focus}
    
    Content scaling:
    {content_scaling}
    
    Required structure (only include sections with substantial content):
    
    ## 📋 Executive Summary
    Write 4-8 sentences capturing the episode's main value proposition. What would a busy executive need to know?
    
    ## 🎯 Key Insights  
    {get_key_insights_target(episode_duration_minutes)} bullet points of substantive takeaways. Each bullet should be:
    - One clear insight or finding
    - 2-3 sentences with sufficient context
    - Actionable or intellectually valuable
    ## 💎 Gold Nuggets
    {get_gold_nuggets_target(episode_duration_minutes)} surprising, counterintuitive, or novel ideas that stood out. Include:
    - Why this insight is valuable or unexpected
    - Sufficient context for understanding
    - Connection to broader implications where relevant
    
    ## 💬 Notable Quotes
    Select {get_quotes_target(episode_duration_minutes)} most impactful quotes that are:
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
    {get_outline_target(episode_duration_minutes)} major sections with timestamps:
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


def get_content_scaling(episode_duration_minutes: Optional[int]) -> str:
    """Get content scaling guidance based on episode length."""
    if not episode_duration_minutes:
        return "- Episode length unknown; use standard content density"

    if episode_duration_minutes < 30:
        return (
            "- Short episode (<30min): Focus on the most essential insights, be concise"
        )
    elif episode_duration_minutes < 60:
        return "- Medium episode (30-60min): Standard analysis depth with comprehensive coverage"
    elif episode_duration_minutes < 90:
        return "- Long episode (60-90min): Extract more detailed insights, include more examples"
    else:
        return "- Very long episode (90+min): Comprehensive analysis with maximum detail extraction"


def get_key_insights_target(episode_duration_minutes: Optional[int]) -> str:
    """Get target number of key insights based on episode length."""
    if not episode_duration_minutes:
        return "12-20"

    # Scale roughly: 1 insight per 3-4 minutes, with reasonable bounds
    min_insights = max(8, episode_duration_minutes // 4)
    max_insights = max(15, episode_duration_minutes // 2.5)
    return f"{int(min_insights)}-{int(max_insights)}"


def get_gold_nuggets_target(episode_duration_minutes: Optional[int]) -> str:
    """Get target number of gold nuggets based on episode length."""
    if not episode_duration_minutes:
        return "6-12"

    # Scale roughly: 1 nugget per 8-10 minutes
    min_nuggets = max(4, episode_duration_minutes // 10)
    max_nuggets = max(8, episode_duration_minutes // 6)
    return f"{int(min_nuggets)}-{int(max_nuggets)}"


def get_quotes_target(episode_duration_minutes: Optional[int]) -> str:
    """Get target number of quotes based on episode length."""
    if not episode_duration_minutes:
        return "4-8"

    # Scale roughly: 1 quote per 12-15 minutes
    min_quotes = max(3, episode_duration_minutes // 15)
    max_quotes = max(6, episode_duration_minutes // 8)
    return f"{int(min_quotes)}-{int(max_quotes)}"


def get_outline_target(episode_duration_minutes: Optional[int]) -> str:
    """Get target number of outline sections based on episode length."""
    if not episode_duration_minutes:
        return "10-15"

    # Scale roughly: 1 section per 5-6 minutes
    min_sections = max(6, episode_duration_minutes // 6)
    max_sections = max(12, episode_duration_minutes // 4)
    return f"{int(min_sections)}-{int(max_sections)}"


def get_qa_target(episode_duration_minutes: Optional[int]) -> str:
    """Get target number of Q&A exchanges based on episode length."""
    if not episode_duration_minutes:
        return "8-12"

    # Scale roughly: 1 Q&A per 8-10 minutes
    min_qa = max(5, episode_duration_minutes // 10)
    max_qa = max(8, episode_duration_minutes // 6)
    return f"{int(min_qa)}-{int(max_qa)}"


def get_type_specific_focus(podcast_type: PodcastType) -> str:
    """Get analysis focus based on podcast type."""

    focus_map = {
        PodcastType.INTERVIEW: """
        - Extract the guest's unique perspectives and expertise
        - Highlight personal stories, career insights, and lessons learned
        - Focus on advice, frameworks, and methodologies shared
        - Note interesting background details that provide context""",
        PodcastType.INTERVIEW_HOST_FOCUSED: """
        - Prioritize host questions, frameworks, and interviewing approach
        - Extract the host's insights, observations, and follow-up questions
        - Capture how the host frames topics and guides conversation
        - Note the host's commentary and synthesis between guest responses
        - Include host questions verbatim when they reveal important frameworks""",
        PodcastType.INTERVIEW_GUEST_FOCUSED: """
        - Prioritize guest responses, expertise, and unique perspectives
        - Extract detailed guest insights, methodologies, and personal experiences
        - Focus heavily on guest advice, frameworks, and lessons learned
        - Minimize host questions unless they directly elicit valuable guest responses
        - Capture guest's authentic voice and terminology""",
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
        PodcastType.SOLO_COMMENTARY: """
        - Focus on the host's personal insights, opinions, and frameworks
        - Extract thought processes, reasoning, and unique perspectives
        - Highlight personal experiences and lessons shared
        - Note commentary on current events or industry trends""",
        PodcastType.PANEL_DISCUSSION: """
        - Capture different perspectives from multiple participants
        - Note agreements, disagreements, and synthesis between speakers
        - Extract unique contributions from each panel member
        - Highlight collaborative insights and group dynamics""",
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
        + "\n\nSpecialization: Interview analysis with balanced focus on host-guest interaction.",
        map_instructions=ENHANCED_MAP_INSTRUCTIONS
        + "\n\nPrioritize: Balance host questions and guest responses, capturing the conversation flow.",
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS
        + "\n\nEmphasize: The value created through the host-guest interaction.",
        analysis_focus="Extract value from both host questions and guest responses, focusing on the conversation's insights.",
    ),
    PodcastType.INTERVIEW_HOST_FOCUSED: PromptTemplate(
        system_prompt=ENHANCED_SYSTEM_BASE
        + "\n\nSpecialization: Host-focused interview analysis capturing interviewing excellence and host insights.",
        map_instructions=ENHANCED_MAP_INSTRUCTIONS
        + "\n\nPrioritize: Host questions, frameworks, follow-ups, and commentary. Extract guest responses that directly answer host questions."
        + "\n\nSpecial instruction: Include verbatim host questions that reveal frameworks, methodologies, or insightful angles.",
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS
        + "\n\nEmphasize: Host's interviewing approach, question quality, and insights. Show how host guides valuable conversation.",
        analysis_focus="Extract maximum value from the host's interviewing expertise and conversational guidance.",
    ),
    PodcastType.INTERVIEW_GUEST_FOCUSED: PromptTemplate(
        system_prompt="""You are an expert at analyzing interview-style podcasts to extract maximum value from guest insights.

Your goal is to create a comprehensive, scannable analysis that captures the guest's unique expertise, tactical advice, and key insights while filtering out fluff and repetitive content.

Focus on:
- Actionable insights and frameworks shared by the guest
- Specific examples, case studies, and real-world applications
- Contrarian or counterintuitive perspectives
- Tactical advice that can be implemented
- The host's strategic questions that unlock valuable responses
- Length-adaptive content based on episode duration""",
        map_instructions="""Extract guest insights, host questions, frameworks, examples, and tactical advice from this transcript segment.

Focus on substance over fluff:
- Guest's unique perspectives, methodologies, and lessons learned
- Specific examples with context and outcomes
- Tactical advice and actionable frameworks
- Host questions that reveal important angles or unlock valuable responses
- Contrarian views or surprising insights
- Real numbers, metrics, or concrete details when mentioned

Ignore filler, small talk, and repetitive content.""",
        reduce_instructions="""Create a comprehensive interview analysis with the following structure:

# [Episode Title] - Interview Analysis

## Executive Summary
Write 3-4 sentences capturing the main value, key themes, and why this interview matters.

## Guest Profile
- **Name**: [Guest name and title]
- **Background**: [Company, role, relevant expertise]  
- **Why Listen**: [What makes this person's perspective valuable]

## Core Insights & Tactical Advice
Organize the most valuable insights by theme. For each insight:
- Provide specific, actionable details
- Include context and examples when available
- Focus on what's unique or counterintuitive
- Scale content based on episode length - longer episodes should have more detailed insights

## Key Q&A Exchanges
Extract the most valuable question-answer pairs based on episode length:

**Q:** [Host's exact question - these often reveal common challenges or important angles]
**Key Points:**
- [Primary insight or advice from the answer]
- [Specific example, framework, or tactic mentioned]
- [Any counterintuitive or contrarian perspective]
- [Concrete details, numbers, or metrics if mentioned]

*Continue this pattern for each valuable exchange. Include more Q&A pairs for longer episodes.*

## Frameworks & Mental Models
List any specific frameworks, processes, methodologies, or mental models the guest shared, with brief explanations.

## Examples & Case Studies
Document real examples shared by the guest with:
- Situation/context
- Actions taken
- Results/outcomes
- Key lessons

## Quotable Moments
Extract the most insightful or memorable quotes with context (more for longer episodes).

## Actionable Takeaways
Specific things listeners can implement, tools mentioned, or resources referenced.

Structure the content to be scannable and reference-worthy. Scale detail based on episode length.""",
        analysis_focus="Extract maximum value from guest expertise through detailed tactical insights, frameworks, and real-world examples.",
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
    PodcastType.SOLO_COMMENTARY: PromptTemplate(
        system_prompt=ENHANCED_SYSTEM_BASE
        + "\n\nSpecialization: Solo commentary analysis focusing on host's insights, reasoning, and perspectives.",
        map_instructions=ENHANCED_MAP_INSTRUCTIONS
        + "\n\nPrioritize: Host's thoughts, frameworks, opinions, and personal experiences.",
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS
        + "\n\nEmphasize: The host's unique perspective and thought processes.",
        analysis_focus="Extract value from the host's solo insights and commentary.",
    ),
    PodcastType.PANEL_DISCUSSION: PromptTemplate(
        system_prompt=ENHANCED_SYSTEM_BASE
        + "\n\nSpecialization: Panel discussion analysis capturing multiple perspectives and group dynamics.",
        map_instructions=ENHANCED_MAP_INSTRUCTIONS
        + "\n\nPrioritize: Different viewpoints, agreements/disagreements, and unique contributions from each participant.",
        reduce_instructions=ENHANCED_REDUCE_INSTRUCTIONS
        + "\n\nEmphasize: The diversity of perspectives and collaborative insights.",
        analysis_focus="Extract value from multiple perspectives and group dynamics.",
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
