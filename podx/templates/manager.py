"""Template manager for custom deepcast analysis prompts."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from podx.logging import get_logger
from podx.prompt_templates import QUOTE_MINER_JSON_SCHEMA

logger = get_logger(__name__)


class TemplateVariable(str, Enum):
    """Available template variables."""

    TITLE = "title"
    SHOW = "show"
    DURATION = "duration"
    TRANSCRIPT = "transcript"
    SPEAKER_COUNT = "speaker_count"
    SPEAKERS = "speakers"
    DATE = "date"
    DESCRIPTION = "description"


class TemplateError(Exception):
    """Raised when template operations fail."""

    pass


class DeepcastTemplate(BaseModel):
    """Deepcast analysis template."""

    name: str
    description: str
    system_prompt: str
    user_prompt: str
    variables: List[str] = Field(default_factory=list)
    output_format: str = "markdown"
    format: Optional[str] = None  # Podcast format (interview, panel, solo, etc.)
    map_instructions: Optional[str] = None  # Custom map phase instructions
    json_schema: Optional[str] = None  # Custom JSON schema hint for reduce phase
    wants_json_only: bool = False  # LLM returns JSON only; markdown rendered in code

    def render(self, context: Dict[str, Any]) -> tuple[str, str]:
        """Render template with context variables.

        Args:
            context: Dictionary of variable values

        Returns:
            Tuple of (rendered_system_prompt, rendered_user_prompt)

        Raises:
            TemplateError: If required variables are missing
        """
        # Check for required variables
        missing = set(self.variables) - set(context.keys())
        if missing:
            raise TemplateError(f"Missing required variables: {', '.join(missing)}")

        # Render system prompt
        system = self.system_prompt
        for var, value in context.items():
            system = system.replace(f"{{{{{var}}}}}", str(value))

        # Render user prompt
        user = self.user_prompt
        for var, value in context.items():
            user = user.replace(f"{{{{{var}}}}}", str(value))

        return system, user


class TemplateManager:
    """Manages deepcast templates.

    Handles loading built-in and user templates, validation, and rendering.
    Templates are stored as YAML files in ~/.podx/templates/
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize template manager.

        Args:
            template_dir: Directory for user templates (defaults to ~/.podx/templates)
        """
        self.template_dir = template_dir or (Path.home() / ".podx" / "templates")
        self.template_dir.mkdir(parents=True, exist_ok=True)

        # Cache loaded templates
        self._cache: Dict[str, DeepcastTemplate] = {}

    def get_builtin_templates(self) -> Dict[str, DeepcastTemplate]:
        """Get built-in templates.

        Returns:
            Dictionary of template name -> DeepcastTemplate
        """
        # Shared scaling guidance for all templates
        scaling_guidance = (
            "Adapt your analysis depth based on episode length:\n"
            "- Episodes <30 minutes: Brief analysis (2-3 items per section, 1-2 sentence summaries)\n"
            "- Episodes 30-60 minutes: Standard analysis (3-5 items per section, 2-3 sentence summaries)\n"
            "- Episodes 60-90 minutes: Comprehensive analysis (5-7 items per section, 3-4 sentence summaries)\n"
            "- Episodes 90+ minutes: Deep analysis (7-10 items per section, 4+ sentence summaries)\n\n"
            "IMPORTANT: Output ONLY the analysis. Do not include conversational follow-ups, "
            "offers to do additional work, or questions like 'Would you like me to...' at the end."
        )

        return {
            "general": DeepcastTemplate(
                name="general",
                description="Format: Works for any podcast type. A versatile template that adapts to any format.",
                format="general",
                system_prompt=(
                    "You are an expert podcast analyst. Create a comprehensive summary that captures:\n"
                    "- The main topics and themes discussed\n"
                    "- Key insights and takeaways\n"
                    "- Notable quotes and memorable moments\n"
                    "- The overall structure and flow of the episode\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this podcast episode:\n\n"
                    "Duration: {{duration}} minutes\n"
                    "Speakers: {{speaker_count}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Summary\n"
                    "A concise overview of the episode (2-3 sentences)\n\n"
                    "## Key Topics\n"
                    "(scale with duration) Main subjects discussed with brief descriptions\n\n"
                    "## Key Insights\n"
                    "(scale with duration) Important takeaways and learnings\n\n"
                    "## Notable Quotes\n"
                    "(scale with duration) Memorable statements with context\n\n"
                    "## Takeaways\n"
                    "What listeners should remember from this episode"
                ),
                variables=["duration", "speaker_count", "transcript"],
            ),
            "solo-commentary": DeepcastTemplate(
                name="solo-commentary",
                description="Format: One host sharing thoughts/analysis. Example podcasts: Dan Carlin's Hardcore History, Sam Harris: Making Sense (solo)",
                format="solo",
                system_prompt=(
                    "You are analyzing a solo commentary podcast. The host is sharing their thoughts, analysis, or storytelling without guests. Focus on:\n"
                    "- The main thesis or argument being presented\n"
                    "- The logical flow and structure of ideas\n"
                    "- Evidence and examples used to support points\n"
                    "- The host's unique perspective or insights\n"
                    "- Memorable quotes and powerful statements\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this solo commentary episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Main Thesis\n"
                    "What is the central argument or message? State it in 1-2 clear sentences.\n\n"
                    "## Supporting Points\n"
                    "(scale with duration) Extract key supporting points with specific evidence or examples from transcript\n\n"
                    "## Memorable Quotes\n"
                    "(scale with duration) Include exact quotes with brief context\n\n"
                    "## Key Takeaways\n"
                    "What should listeners remember? 2-3 actionable insights or perspective shifts\n\n"
                    "## Episode Structure\n"
                    "How did the host organize their thoughts? Note major transitions or narrative arc"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "interview-1on1": DeepcastTemplate(
                name="interview-1on1",
                description="Format: Host interviewing a single guest. Example podcasts: Lex Fridman Podcast, Joe Rogan Experience, Tim Ferriss Show, The Knowledge Project",
                format="interview",
                system_prompt=(
                    "You are analyzing a 1-on-1 interview podcast. Focus on the dialogue between host and guest, extracting:\n"
                    "- The guest's main expertise, background, or story\n"
                    "- Key questions asked by the host\n"
                    "- Important answers and insights from the guest\n"
                    "- Areas of depth and substance in the conversation\n"
                    "- Notable exchanges or turning points\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this interview episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n"
                    "Guest Info: {{speakers}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Guest Introduction\n"
                    "Who is the guest? (background, expertise, current work) Why are they interesting for this conversation?\n\n"
                    "## Key Topics Discussed\n"
                    "(scale with duration) What major subjects did they cover? For each topic, note the main insights or arguments\n\n"
                    "## Best Questions\n"
                    "(scale with duration) What were the most insightful or thought-provoking questions? Include the host's question and guest's key response\n\n"
                    "## Notable Quotes\n"
                    "(scale with duration) Extract memorable or impactful quotes from the guest with brief context\n\n"
                    "## Key Takeaways\n"
                    "What are the main lessons or insights? What should listeners remember from this conversation?\n\n"
                    "## Conversation Dynamics\n"
                    "How did the conversation flow? Were there any notable turning points or deep dives?"
                ),
                variables=["title", "show", "duration", "transcript", "speakers"],
            ),
            "panel-discussion": DeepcastTemplate(
                name="panel-discussion",
                description="Format: Multiple co-hosts or guests discussing topics. Example podcasts: All-In Podcast, The Talk Show, Hard Fork (NYT), Recode Decode (multi-guest)",
                format="panel",
                system_prompt=(
                    "You are analyzing a panel discussion podcast with multiple participants. Focus on:\n"
                    "- The diversity of perspectives and viewpoints\n"
                    "- Points of agreement and disagreement\n"
                    "- Individual contributions from each panelist\n"
                    "- The flow of debate and discussion\n"
                    "- Key conclusions or insights that emerge\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this panel discussion:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n"
                    "Panelists: {{speakers}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Episode Overview\n"
                    "(scale with duration for summary length) What topics did the panel discuss? What was the overall tone/theme?\n\n"
                    "## Key Topics & Perspectives\n"
                    "(scale with duration) For each major topic, capture the different viewpoints presented, points of agreement/disagreement, and notable insights from specific panelists\n\n"
                    "## Best Exchanges\n"
                    "(scale with duration) Highlight interesting debates or discussions with speaker attributions and context\n\n"
                    "## Notable Quotes\n"
                    "(scale with duration) Extract memorable statements from panelists with speaker attribution\n\n"
                    "## Panelist Contributions\n"
                    "What unique perspective did each panelist bring? Who drove which parts of the conversation?\n\n"
                    "## Key Takeaways\n"
                    "What emerged as the main conclusions or insights? What should listeners remember?"
                ),
                variables=[
                    "title",
                    "show",
                    "duration",
                    "transcript",
                    "speakers",
                    "speaker_count",
                ],
            ),
            "lecture-presentation": DeepcastTemplate(
                name="lecture-presentation",
                description="Format: Educational content delivery with structured teaching. Example podcasts: MIT OpenCourseWare, TED Talks Audio, Freakonomics Radio (educational episodes)",
                format="lecture",
                system_prompt=(
                    "You are analyzing an educational lecture or presentation podcast. The content is structured to teach specific concepts. Focus on:\n"
                    "- The main topic or subject being taught\n"
                    "- Key concepts and principles explained\n"
                    "- Examples and case studies used\n"
                    "- The pedagogical structure (how information is organized)\n"
                    "- Learning objectives and takeaways\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this lecture/presentation episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Topic & Learning Objectives\n"
                    "What is being taught? What should students learn from this?\n\n"
                    "## Key Concepts\n"
                    "(scale with duration) What are the main ideas or principles? For each concept, provide a clear explanation\n\n"
                    "## Examples & Case Studies\n"
                    "(scale with duration) What real-world examples or case studies were used? How do they illustrate the concepts?\n\n"
                    "## Supporting Evidence\n"
                    "(scale with duration) What data, research, or facts were cited? Note key statistics or studies mentioned\n\n"
                    "## Lecture Structure\n"
                    "How was the information organized? Note the flow: intro → main sections → conclusion\n\n"
                    "## Key Takeaways\n"
                    "What are the most important lessons? What should listeners remember or apply?"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "debate-roundtable": DeepcastTemplate(
                name="debate-roundtable",
                description="Format: Structured debate or roundtable with opposing viewpoints. Example podcasts: Intelligence Squared, The Munk Debates, Uncommon Knowledge",
                format="debate",
                system_prompt=(
                    "You are analyzing a debate or roundtable podcast where participants present opposing or contrasting viewpoints. Focus on:\n"
                    "- The central question or topic being debated\n"
                    "- Each side's main arguments and evidence\n"
                    "- Counterarguments and rebuttals\n"
                    "- The quality of reasoning and evidence\n"
                    "- Points where participants find common ground or irreconcilable differences\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this debate/roundtable:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n"
                    "Participants: {{speakers}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Debate Topic & Positions\n"
                    "What is the central question or topic? What are the main positions being argued?\n\n"
                    "## Arguments For Each Position\n"
                    "(scale with duration) For each side, extract main arguments, supporting evidence, and key reasoning\n\n"
                    "## Rebuttals & Counterarguments\n"
                    "(scale with duration) What counterarguments were raised? How did participants respond to challenges?\n\n"
                    "## Key Exchanges\n"
                    "(scale with duration) Highlight important back-and-forth moments with speaker attributions\n\n"
                    "## Common Ground & Disagreements\n"
                    "Where did participants agree? What remained unresolved or contentious?\n\n"
                    "## Assessment\n"
                    "Which arguments were strongest/weakest? What nuances emerged?"
                ),
                variables=[
                    "title",
                    "show",
                    "duration",
                    "transcript",
                    "speakers",
                    "speaker_count",
                ],
            ),
            "news-analysis": DeepcastTemplate(
                name="news-analysis",
                description="Format: Analysis and discussion of current events and news. Example podcasts: The Daily (NYT), Up First (NPR), Today, Explained (Vox)",
                format="news",
                system_prompt=(
                    "You are analyzing a news analysis podcast. Focus on:\n"
                    "- The news story or event being covered\n"
                    "- Key facts and background context\n"
                    "- Expert analysis and interpretation\n"
                    "- Multiple perspectives if present\n"
                    "- Implications and what it means for listeners\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this news analysis episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n"
                    "Date: {{date}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## News Story Overview\n"
                    "(scale with duration for summary length) What happened? Who is involved? When and where did this occur?\n\n"
                    "## Key Facts & Background\n"
                    "(scale with duration) What are the important facts? What context or history is needed to understand this?\n\n"
                    "## Analysis & Interpretation\n"
                    "(scale with duration) What does this mean? What are the implications? What perspectives or expert analysis was provided?\n\n"
                    "## Different Viewpoints\n"
                    "(scale with duration) What different perspectives were presented? How do various stakeholders view this?\n\n"
                    "## Notable Quotes\n"
                    "(scale with duration) Extract key statements from experts or newsmakers with attribution and context\n\n"
                    "## Key Takeaways\n"
                    "Why does this matter? What should listeners understand about this story?"
                ),
                variables=["title", "show", "duration", "transcript", "date"],
            ),
            "case-study": DeepcastTemplate(
                name="case-study",
                description="Format: Deep analysis of a specific company, event, or case. Example podcasts: Acquired, How I Built This, Revisionist History, Business Wars",
                format="case-study",
                system_prompt=(
                    "You are analyzing a case study podcast that does a deep dive into a specific company, person, event, or phenomenon. Focus on:\n"
                    "- The subject of the case study and why it's interesting\n"
                    "- The chronology and key turning points\n"
                    "- Decisions made and their consequences\n"
                    "- Lessons learned and insights\n"
                    "- The broader implications or patterns\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this case study episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Case Study Subject\n"
                    "What company/person/event is being analyzed? Why is this case interesting or important?\n\n"
                    "## Timeline & Key Events\n"
                    "(scale with duration) What are the major milestones or turning points? Present in chronological order with brief descriptions\n\n"
                    "## Critical Decisions\n"
                    "(scale with duration) What important decisions were made? What were the outcomes and consequences?\n\n"
                    "## Lessons Learned\n"
                    "(scale with duration) What insights emerge from this case? What worked? What didn't?\n\n"
                    "## Broader Implications\n"
                    "What patterns or principles can be extracted? How does this case relate to other situations?\n\n"
                    "## Notable Quotes & Anecdotes\n"
                    "(scale with duration) Extract memorable stories or statements with context\n\n"
                    "## Key Takeaways\n"
                    "What should listeners remember? What can be applied elsewhere?"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "technical-deep-dive": DeepcastTemplate(
                name="technical-deep-dive",
                description="Format: In-depth technical discussion of technology, engineering, or science. Example podcasts: Software Engineering Daily, The Changelog, a16z Podcast (technical episodes), Lex Fridman (technical interviews)",
                format="technical",
                system_prompt=(
                    "You are analyzing a technical deep dive podcast covering technology, engineering, or scientific topics. Focus on:\n"
                    "- The technical topic or problem being discussed\n"
                    "- Key technical concepts and terminology\n"
                    "- How the technology works\n"
                    "- Challenges, tradeoffs, and solutions\n"
                    "- Real-world applications and implications\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this technical deep dive:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Technical Topic Overview\n"
                    "What technology/system/concept is being discussed? Why is it important or interesting?\n\n"
                    "## Key Technical Concepts\n"
                    "(scale with duration) What are the fundamental ideas or technologies? Explain each concept clearly (assume technical but not expert audience)\n\n"
                    "## How It Works\n"
                    "(scale with duration) What is the architecture or design? What are the key components or mechanisms?\n\n"
                    "## Challenges & Solutions\n"
                    "(scale with duration) What technical challenges were discussed? What solutions or approaches were presented?\n\n"
                    "## Tradeoffs & Decisions\n"
                    "What design tradeoffs were discussed? Why were certain approaches chosen over alternatives?\n\n"
                    "## Real-World Applications\n"
                    "(scale with duration) How is this technology used in practice? What are the implications or use cases?\n\n"
                    "## Key Takeaways\n"
                    "What are the most important technical insights? What should technically-minded listeners remember?"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "business-strategy": DeepcastTemplate(
                name="business-strategy",
                description="Format: Discussion of business strategy, market analysis, or corporate affairs. Example podcasts: Invest Like the Best, Masters of Scale, a16z Podcast (business episodes), The Prof G Pod",
                format="business",
                system_prompt=(
                    "You are analyzing a business strategy podcast covering company strategy, market dynamics, investment thesis, or business models. Focus on:\n"
                    "- The business topic or company being discussed\n"
                    "- Strategic frameworks and mental models\n"
                    "- Market dynamics and competitive landscape\n"
                    "- Key business decisions and their rationale\n"
                    "- Lessons for business leaders and entrepreneurs\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this business strategy episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Business Topic Overview\n"
                    "(scale with duration for summary length) What company/market/strategy is being discussed? Why is this topic relevant now?\n\n"
                    "## Strategic Insights\n"
                    "(scale with duration) What strategic frameworks or mental models were discussed? What are the key strategic principles?\n\n"
                    "## Market Analysis\n"
                    "(scale with duration) What market dynamics were covered? Who are the key players and what is the competitive landscape?\n\n"
                    "## Business Decisions & Rationale\n"
                    "(scale with duration) What important business decisions were discussed? What was the reasoning behind them?\n\n"
                    "## Lessons & Frameworks\n"
                    "What can business leaders learn from this? What frameworks or approaches are applicable elsewhere?\n\n"
                    "## Notable Quotes\n"
                    "(scale with duration) Extract insightful statements about business strategy with attribution\n\n"
                    "## Key Takeaways\n"
                    "What are the most important business insights? What should entrepreneurs/leaders remember?"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "research-review": DeepcastTemplate(
                name="research-review",
                description="Format: Discussion and analysis of academic research papers. Example podcasts: The TWIML AI Podcast, Nature Podcast, Science Magazine Podcast, The Ezra Klein Show (research-heavy episodes)",
                format="research",
                system_prompt=(
                    "You are analyzing a podcast that reviews or discusses academic research. Focus on:\n"
                    "- The research question and hypothesis\n"
                    "- Methodology and study design\n"
                    "- Key findings and results\n"
                    "- Implications and significance\n"
                    "- Limitations and critiques\n"
                    "- How this advances the field\n\n"
                    f"{scaling_guidance}"
                ),
                user_prompt=(
                    "Analyze this research review episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide a structured analysis using markdown headings:\n\n"
                    "## Research Overview\n"
                    "What research paper(s) or study is being discussed? What is the research question?\n\n"
                    "## Methodology\n"
                    "How was the study conducted? What methods or approach did researchers use?\n\n"
                    "## Key Findings\n"
                    "(scale with duration) What did the research discover? What are the main results?\n\n"
                    "## Significance & Implications\n"
                    "(scale with duration) Why do these findings matter? What are the implications for the field or society?\n\n"
                    "## Limitations & Critiques\n"
                    "What are the study's limitations? What critiques or caveats were discussed?\n\n"
                    "## Context & Related Work\n"
                    "How does this fit into existing research? What related studies or theories were mentioned?\n\n"
                    "## Notable Quotes\n"
                    "(scale with duration) Extract key statements from researchers or hosts with attribution\n\n"
                    "## Key Takeaways\n"
                    "What should listeners understand about this research? What are the main insights?"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "quote-miner": DeepcastTemplate(
                name="quote-miner",
                description="Mine the most quotable moments from a podcast episode. Returns structured JSON with verbatim-verified quotes, categories, and usage suggestions.",
                format="quote-mining",
                system_prompt=(
                    "You are a quote mining specialist — an expert at identifying the most "
                    "quotable, shareable, and memorable moments from spoken content.\n\n"
                    "Your ear is tuned to statements that are:\n"
                    "- **Short** (ideally < 25 words)\n"
                    "- **Vivid** — uses a concrete image, metaphor, or analogy\n"
                    "- **Reframes** — 'people think X, but actually Y'\n"
                    "- **Sticky labels** — coins a term or phrase that sticks\n"
                    "- **Parallel structure** — has rhythm or cadence\n"
                    "- **Surprising twists** — unexpected punchlines or insights\n"
                    "- **Testable rules** — 'if you do X, then Y happens'\n"
                    "- **Maxims** — timeless principles or pithy wisdom\n"
                    "- **Humor** — laugh lines that also carry insight\n\n"
                    "CRITICAL RULES:\n"
                    "1. Every quote MUST be copied EXACTLY from the transcript — verbatim, "
                    "word-for-word, no paraphrasing, no cleaning up grammar.\n"
                    "2. Include the speaker label exactly as it appears in the transcript.\n"
                    "3. Include both start and end timestamps when available.\n"
                    "4. Return ONLY valid JSON. No markdown, no commentary.\n\n"
                    "IMPORTANT: Output ONLY the analysis. Do not include conversational follow-ups, "
                    "offers to do additional work, or questions like 'Would you like me to...' at the end."
                ),
                map_instructions=(
                    "Extract 8-15 verbatim candidate quotes from this transcript chunk.\n\n"
                    "For EACH candidate:\n"
                    "1. Copy the quote EXACTLY as spoken — word for word from the transcript. "
                    "Do NOT fix grammar, do NOT paraphrase, do NOT polish.\n"
                    "2. Include the speaker label (e.g. SPEAKER_00)\n"
                    "3. Include start timestamp (HH:MM:SS) and end timestamp if available\n"
                    "4. Write 1-2 sentences of lead-in context\n"
                    "5. Classify as: metaphor | reframe | maxim | definition | warning | "
                    "humor | analogy | sticky-label\n"
                    "6. Briefly explain why it works (the rhetorical power)\n\n"
                    "Quotability checklist — prefer quotes that hit multiple:\n"
                    "- Short (< 25 words ideal)\n"
                    "- Vivid metaphor or concrete image\n"
                    "- Crisp reframe ('people think X, but actually Y')\n"
                    "- Sticky label / coined term\n"
                    "- Parallel structure / cadence\n"
                    "- Surprising twist or laugh line\n"
                    "- Testable rule of thumb\n"
                    "- 'If…then…' clarity\n\n"
                    "Cast a wide net — high recall. Include borderline candidates. "
                    "The reduce phase will filter.\n\n"
                    "Format output as a JSON array of objects."
                ),
                user_prompt=(
                    "You are the validator/ranker. You received candidate quotes from multiple "
                    "transcript chunks.\n\n"
                    "Episode: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n"
                    "Speakers: {{speakers}}\n\n"
                    "Your job:\n"
                    "1. REMOVE candidates that aren't truly quotable — generic statements, "
                    "filler, incomplete thoughts\n"
                    "2. GROUP near-duplicates and keep the stronger version\n"
                    "3. SELECT the top quotes (roughly 1 per 4-5 minutes of episode duration, "
                    "so a 60-min episode gets ~12-15 top quotes)\n"
                    "4. For each winner, provide:\n"
                    "   - title: 3-6 word library title\n"
                    "   - tags: 2-4 topical tags\n"
                    "   - use_case: one-liner on how to use this quote\n"
                    "5. RANK by quotability (best first)\n\n"
                    "Remember: every quote must be EXACTLY as it appeared in the transcript. "
                    "Do not clean up, paraphrase, or improve any quote text.\n\n"
                    "Return the final results as a JSON object."
                ),
                variables=["title", "show", "duration", "speakers"],
                json_schema=QUOTE_MINER_JSON_SCHEMA,
                wants_json_only=True,
            ),
        }

    def load(self, name: str) -> DeepcastTemplate:
        """Load template by name.

        Args:
            name: Template name

        Returns:
            DeepcastTemplate instance

        Raises:
            TemplateError: If template not found
        """
        # Check cache
        if name in self._cache:
            return self._cache[name]

        # Check built-in templates
        builtins = self.get_builtin_templates()
        if name in builtins:
            template = builtins[name]
            self._cache[name] = template
            return template

        # Try loading from user templates
        template_file = self.template_dir / f"{name}.yaml"
        if not template_file.exists():
            raise TemplateError(
                f"Template '{name}' not found. " f"Available: {', '.join(self.list_templates())}"
            )

        try:
            with open(template_file, "r") as f:
                data = yaml.safe_load(f)

            template = DeepcastTemplate(**data)
            self._cache[name] = template
            return template

        except Exception as e:
            raise TemplateError(f"Failed to load template '{name}': {e}") from e

    def save(self, template: DeepcastTemplate) -> None:
        """Save template to disk.

        Args:
            template: Template to save

        Raises:
            TemplateError: If save fails
        """
        template_file = self.template_dir / f"{template.name}.yaml"

        try:
            with open(template_file, "w") as f:
                data = template.model_dump()
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            # Update cache
            self._cache[template.name] = template

            logger.info(
                "Template saved",
                name=template.name,
                path=str(template_file),
            )

        except Exception as e:
            raise TemplateError(f"Failed to save template: {e}") from e

    def list_templates(self) -> List[str]:
        """List all available templates.

        Returns:
            List of template names (built-in + user)
        """
        # Built-in templates
        templates = list(self.get_builtin_templates().keys())

        # User templates
        if self.template_dir.exists():
            user_templates = [p.stem for p in self.template_dir.glob("*.yaml")]
            templates.extend(user_templates)

        return sorted(set(templates))

    def delete(self, name: str) -> bool:
        """Delete user template.

        Args:
            name: Template name

        Returns:
            True if deleted, False if not found

        Raises:
            TemplateError: If trying to delete built-in template
        """
        if name in self.get_builtin_templates():
            raise TemplateError(f"Cannot delete built-in template '{name}'")

        template_file = self.template_dir / f"{name}.yaml"
        if template_file.exists():
            template_file.unlink()

            # Remove from cache
            self._cache.pop(name, None)

            logger.info("Template deleted", name=name)
            return True

        return False

    def export(self, name: str) -> str:
        """Export template as YAML string.

        Args:
            name: Template name

        Returns:
            YAML string
        """
        template = self.load(name)
        data = template.model_dump()
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def import_template(self, yaml_content: str) -> DeepcastTemplate:
        """Import template from YAML string.

        Args:
            yaml_content: YAML string

        Returns:
            Imported DeepcastTemplate

        Raises:
            TemplateError: If import fails
        """
        try:
            data = yaml.safe_load(yaml_content)
            template = DeepcastTemplate(**data)
            self.save(template)
            return template

        except Exception as e:
            raise TemplateError(f"Failed to import template: {e}") from e
