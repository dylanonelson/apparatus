"""
Prompt management system for loading, validating, and rendering YAML-based prompts.

Prompts are organized by feature and version in the prompts/ directory:
    prompts/
        passage_finder/
            v0.yaml
        freeform/
            v0.yaml
"""

from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import yaml
from jinja2 import Environment as Jinja2Environment, BaseLoader
from litellm.types.utils import Message


class PromptData(TypedDict):
    """Structure of a prompt YAML file."""

    description: str
    input_variables: list[str]
    system: str
    user: str


class PromptValidationError(Exception):
    """Raised when prompt template variables don't match the expected input_variables."""

    pass


class PromptNotFoundError(Exception):
    """Raised when a requested prompt feature/version doesn't exist."""

    pass


# Path to the prompts directory (sibling of app/)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=64)
def _load_prompt_data(feature: str, version: str) -> PromptData:
    """
    Load and cache prompt data from a YAML file.

    Args:
        feature: The feature name (e.g., "passage_finder", "freeform")
        version: The version string (e.g., "v0", "v1")

    Returns:
        The parsed prompt data

    Raises:
        PromptNotFoundError: If the prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / feature / f"{version}.yaml"

    if not prompt_path.exists():
        raise PromptNotFoundError(
            f"Prompt not found: {feature}/{version} (looked in {prompt_path})"
        )

    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Validate required keys
    required_keys = {"description", "input_variables", "system", "user"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise ValueError(
            f"Prompt {feature}/{version} missing required keys: {missing_keys}"
        )

    return PromptData(
        description=data["description"],
        input_variables=data["input_variables"],
        system=data["system"],
        user=data["user"],
    )


def _validate_variables(
    prompt_data: PromptData, template_vars: dict[str, object], feature: str, version: str
) -> None:
    """
    Validate that all required input_variables are provided.

    Args:
        prompt_data: The loaded prompt data
        template_vars: The variables provided by the caller
        feature: Feature name (for error messages)
        version: Version string (for error messages)

    Raises:
        PromptValidationError: If required variables are missing
    """
    required = set(prompt_data["input_variables"])
    provided = set(template_vars.keys())
    missing = required - provided

    if missing:
        raise PromptValidationError(
            f"Missing required template variables for {feature}/{version}: {missing}. "
            f"Required: {required}, Provided: {provided}"
        )


def _render_template(template_str: str, template_vars: dict[str, object]) -> str:
    """
    Render a Jinja2 template string with the provided variables.

    Args:
        template_str: The Jinja2 template string
        template_vars: Variables to substitute into the template

    Returns:
        The rendered string
    """
    env = Jinja2Environment(loader=BaseLoader())
    template = env.from_string(template_str)
    return template.render(**template_vars)


class PromptManager:
    """
    Manages loading, validating, and rendering prompts from YAML files.

    Prompts are loaded from the prompts/ directory, organized by feature and version.
    Each prompt file contains a system prompt, user prompt, and metadata including
    the list of required input variables.

    Example usage:
        manager = PromptManager()
        messages = manager.get_messages(
            "passage_finder", "v0",
            title="Pride and Prejudice",
            author="Jane Austen",
            question="Where does Elizabeth first meet Darcy?",
            location_json='{"href": "/text/chapter-01.xhtml"}'
        )
    """

    def get_messages(
        self, feature: str, version: str, **template_vars: object
    ) -> list[Message]:
        """
        Get rendered system and user messages for a prompt.

        Args:
            feature: The feature name (e.g., "passage_finder", "freeform")
            version: The version string (e.g., "v0", "v1")
            **template_vars: Variables to substitute into the prompts

        Returns:
            A list containing the system and user Message objects

        Raises:
            PromptNotFoundError: If the prompt doesn't exist
            PromptValidationError: If required variables are missing
        """
        prompt_data = _load_prompt_data(feature, version)
        _validate_variables(prompt_data, template_vars, feature, version)

        system_content = _render_template(prompt_data["system"], template_vars)
        user_content = _render_template(prompt_data["user"], template_vars)

        messages: list[Message] = [
            Message(role="system", content=system_content),
        ]

        # Only add user message if it has content
        if user_content.strip():
            messages.append(Message(role="user", content=user_content))

        return messages

    def get_system_prompt(
        self, feature: str, version: str, **template_vars: object
    ) -> str:
        """
        Get only the rendered system prompt.

        Args:
            feature: The feature name (e.g., "passage_finder", "freeform")
            version: The version string (e.g., "v0", "v1")
            **template_vars: Variables to substitute into the prompt

        Returns:
            The rendered system prompt string

        Raises:
            PromptNotFoundError: If the prompt doesn't exist
            PromptValidationError: If required variables are missing
        """
        prompt_data = _load_prompt_data(feature, version)
        _validate_variables(prompt_data, template_vars, feature, version)

        return _render_template(prompt_data["system"], template_vars)
    
    def get_system_message(self, feature: str, version: str, **template_vars: object) -> Message:
        """
        Get the rendered system message.
        """
        content = self.get_system_prompt(feature, version, **template_vars)
        return Message(role="system", content=content)

    def get_user_prompt(
        self, feature: str, version: str, **template_vars: object
    ) -> str:
        """
        Get only the rendered user prompt.

        Args:
            feature: The feature name (e.g., "passage_finder", "freeform")
            version: The version string (e.g., "v0", "v1")
            **template_vars: Variables to substitute into the prompt

        Returns:
            The rendered user prompt string

        Raises:
            PromptNotFoundError: If the prompt doesn't exist
            PromptValidationError: If required variables are missing
        """
        prompt_data = _load_prompt_data(feature, version)
        _validate_variables(prompt_data, template_vars, feature, version)

        return _render_template(prompt_data["user"], template_vars)


# Module-level singleton for convenience
_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Get the singleton PromptManager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
