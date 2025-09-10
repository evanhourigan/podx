"""
Anthropic Claude analysis plugin for podx.

This plugin provides AI analysis using Anthropic's Claude models as an alternative to OpenAI.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

from podx.logging import get_logger
from podx.plugins import AnalysisPlugin, PluginMetadata, PluginType
from podx.schemas import DeepcastBrief, Transcript

logger = get_logger(__name__)

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AnthropicAnalysisPlugin(AnalysisPlugin):
    """Analysis plugin using Anthropic Claude models."""

    def __init__(self):
        self.client = None
        self.initialized = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="anthropic-analysis",
            version="1.0.0",
            description="AI transcript analysis using Anthropic Claude models",
            author="Podx Team",
            plugin_type=PluginType.ANALYSIS,
            dependencies=["anthropic"],
            config_schema={
                "api_key": {"type": "string", "required": True},
                "model": {"type": "string", "default": "claude-3-sonnet-20240229"},
                "max_tokens": {"type": "integer", "default": 4000},
                "temperature": {"type": "number", "default": 0.2},
            },
        )

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        if not ANTHROPIC_AVAILABLE:
            logger.error(
                "Anthropic library not available. Install with: pip install anthropic"
            )
            return False

        api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable"
            )
            return False

        return True

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic library not available")

        api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.config = config
        self.initialized = True

        logger.info(
            "Anthropic analysis plugin initialized",
            model=config.get("model", "claude-3-sonnet-20240229"),
        )

    def analyze_transcript(self, transcript: Transcript, **kwargs) -> DeepcastBrief:
        """
        Analyze transcript using Claude.

        Args:
            transcript: Transcript to analyze
            **kwargs: Additional parameters (model, temperature, etc.)

        Returns:
            DeepcastBrief with analysis results
        """
        if not self.initialized:
            raise RuntimeError("Plugin not initialized")

        # Extract text from transcript segments
        text = self._extract_text(transcript)

        # Get analysis parameters
        model = kwargs.get(
            "model", self.config.get("model", "claude-3-sonnet-20240229")
        )
        temperature = kwargs.get("temperature", self.config.get("temperature", 0.2))
        max_tokens = kwargs.get("max_tokens", self.config.get("max_tokens", 4000))

        # Create analysis prompt
        prompt = self._create_analysis_prompt(text, transcript)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response into DeepcastBrief format
            analysis_text = response.content[0].text

            # For now, return a basic DeepcastBrief structure
            # In a full implementation, you'd parse the structured response
            return {
                "markdown": analysis_text,
                "summary": self._extract_summary(analysis_text),
                "key_points": self._extract_key_points(analysis_text),
                "quotes": [],
                "metadata": {
                    "model": model,
                    "provider": "anthropic",
                    "temperature": temperature,
                },
            }

        except Exception as e:
            logger.error("Anthropic analysis failed", error=str(e))
            raise

    def supported_models(self) -> List[str]:
        """Return list of supported Claude models."""
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
        ]

    def _extract_text(self, transcript: Transcript) -> str:
        """Extract plain text from transcript segments."""
        segments = transcript.get("segments", [])
        if not segments:
            return transcript.get("text", "")

        text_parts = []
        for segment in segments:
            if "text" in segment:
                # Include speaker information if available
                speaker = segment.get("speaker", "")
                if speaker:
                    text_parts.append(f"[{speaker}]: {segment['text']}")
                else:
                    text_parts.append(segment["text"])

        return "\n".join(text_parts)

    def _create_analysis_prompt(self, text: str, transcript: Transcript) -> str:
        """Create analysis prompt for Claude."""
        show_name = transcript.get("show", "Unknown Show")
        episode_title = transcript.get("episode_title", "Unknown Episode")

        prompt = f"""Please analyze this podcast transcript and provide a comprehensive summary.

**Podcast:** {show_name}
**Episode:** {episode_title}

**Instructions:**
1. Provide a brief executive summary (3-4 sentences)
2. Extract 8-12 key insights or main points 
3. Identify any notable quotes with speaker attribution
4. List any actionable items or resources mentioned
5. Create a brief outline with timestamps if available

**Format your response as markdown with clear sections.**

**Transcript:**
{text}

Please provide your analysis:"""

        return prompt

    def _extract_summary(self, analysis_text: str) -> str:
        """Extract summary from analysis text."""
        # Simple extraction - in a full implementation you'd use more sophisticated parsing
        lines = analysis_text.split("\n")
        summary_lines = []
        in_summary = False

        for line in lines:
            if "summary" in line.lower() or "executive" in line.lower():
                in_summary = True
                continue
            if in_summary and line.strip():
                if line.startswith("#") and len(summary_lines) > 0:
                    break
                summary_lines.append(line.strip())

        return " ".join(summary_lines)

    def _extract_key_points(self, analysis_text: str) -> List[str]:
        """Extract key points from analysis text."""
        # Simple extraction - in a full implementation you'd use more sophisticated parsing
        lines = analysis_text.split("\n")
        key_points = []
        in_key_points = False

        for line in lines:
            if "key" in line.lower() and (
                "point" in line.lower() or "insight" in line.lower()
            ):
                in_key_points = True
                continue
            if in_key_points:
                if line.startswith("#") and len(key_points) > 0:
                    break
                if line.strip().startswith("-") or line.strip().startswith("*"):
                    key_points.append(line.strip()[1:].strip())

        return key_points
