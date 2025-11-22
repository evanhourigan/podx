"""Template manager for custom deepcast analysis prompts."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from podx.logging import get_logger

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
            raise TemplateError(
                f"Missing required variables: {', '.join(missing)}"
            )

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
        return {
            "default": DeepcastTemplate(
                name="default",
                description="Standard podcast analysis with summary and insights",
                system_prompt=(
                    "You are an expert podcast analyst. Analyze the provided "
                    "transcript and create a comprehensive analysis."
                ),
                user_prompt=(
                    "Analyze this podcast episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide:\n"
                    "1. Executive summary\n"
                    "2. Key topics discussed\n"
                    "3. Notable quotes\n"
                    "4. Main takeaways"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "interview": DeepcastTemplate(
                name="interview",
                description="Interview-focused analysis with Q&A extraction",
                system_prompt=(
                    "You are analyzing a podcast interview. Focus on the "
                    "conversation dynamics, key questions, and guest insights."
                ),
                user_prompt=(
                    "Analyze this interview:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Speakers: {{speakers}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide:\n"
                    "1. Guest background and credentials\n"
                    "2. Key questions asked\n"
                    "3. Most insightful answers\n"
                    "4. Conversation highlights\n"
                    "5. Actionable advice from guest"
                ),
                variables=["title", "show", "speakers", "transcript"],
            ),
            "tech-talk": DeepcastTemplate(
                name="tech-talk",
                description="Technical content analysis for developer podcasts",
                system_prompt=(
                    "You are analyzing a technical podcast. Focus on technologies "
                    "discussed, code concepts, and technical insights."
                ),
                user_prompt=(
                    "Analyze this technical episode:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide:\n"
                    "1. Technologies and tools mentioned\n"
                    "2. Technical concepts explained\n"
                    "3. Code patterns or architectures discussed\n"
                    "4. Best practices highlighted\n"
                    "5. Resources or links mentioned"
                ),
                variables=["title", "show", "transcript"],
            ),
            "storytelling": DeepcastTemplate(
                name="storytelling",
                description="Narrative analysis for story-driven podcasts",
                system_prompt=(
                    "You are analyzing a narrative podcast. Focus on story "
                    "structure, character development, and narrative techniques."
                ),
                user_prompt=(
                    "Analyze this story:\n\n"
                    "Title: {{title}}\n"
                    "Show: {{show}}\n"
                    "Duration: {{duration}} minutes\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide:\n"
                    "1. Story summary and plot\n"
                    "2. Key characters and their roles\n"
                    "3. Narrative structure and pacing\n"
                    "4. Themes and motifs\n"
                    "5. Emotional arc"
                ),
                variables=["title", "show", "duration", "transcript"],
            ),
            "minimal": DeepcastTemplate(
                name="minimal",
                description="Concise analysis with just key points",
                system_prompt=(
                    "You are a concise analyst. Provide brief, actionable insights."
                ),
                user_prompt=(
                    "Provide a concise analysis of this episode:\n\n"
                    "Title: {{title}}\n\n"
                    "Transcript:\n{{transcript}}\n\n"
                    "Provide ONLY:\n"
                    "1. One-sentence summary\n"
                    "2. Top 3 key points\n"
                    "3. One key takeaway"
                ),
                variables=["title", "transcript"],
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
                f"Template '{name}' not found. "
                f"Available: {', '.join(self.list_templates())}"
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
            user_templates = [
                p.stem for p in self.template_dir.glob("*.yaml")
            ]
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
            raise TemplateError(
                f"Cannot delete built-in template '{name}'"
            )

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
