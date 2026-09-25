"""Prompts for LLM interactions."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMPrompt:
    """LLM prompt for interacting with the LLM client.

    The full prompt content is `shared_content` followed directly by `content`. `shared_content` holds the
    leading part that is identical across many requests, which clients may cache for reuse.

    Attributes:
        content: Request-specific part of the prompt content.
        instructions: Instructions for the LLM, sent separately from the content, or None if there are none.
        schema: JSON schema the structured response must follow, or None for a free-form response.
        shared_content: Leading part of the prompt content shared across requests, or None if there is none.
    """

    content: str
    instructions: str | None
    schema: dict[str, Any] | None = None
    shared_content: str | None = None

    def __str__(self) -> str:
        """User-friendly string representation of the LLM prompt."""
        prompt = ''
        if self.instructions:
            prompt += f'\nInstructions:\n\n{self.instructions}\n'
        prompt += f'\nContent:\n\n{self.shared_content or ""}{self.content}\n'
        if self.schema:
            prompt += f'\nSchema: {self.schema}\n'
        return prompt
