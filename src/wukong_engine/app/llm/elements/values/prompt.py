"""Prompts for LLM interactions."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMPrompt:
    """LLM prompt for interacting with the LLM client."""

    content: str
    instructions: str | None
    schema: dict[str, Any] | None = None

    def __str__(self) -> str:
        """User-friendly string representation of the LLM prompt."""
        prompt = ''
        if self.instructions:
            prompt += f'\nInstructions:\n\n{self.instructions}\n'
        prompt += f'\nContent:\n\n{self.content}\n'
        if self.schema:
            prompt += f'\nSchema: {self.schema}\n'
        return prompt
