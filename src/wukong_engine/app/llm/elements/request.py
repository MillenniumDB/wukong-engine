"""Request model for LLM interactions."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from wukong_engine.app.llm.model import LLM


@dataclass(frozen=True)
class LLMRequest:
    """Fully rendered request to be executed by an LLM client."""

    user_prompt: str
    system_prompt: str | None
    response_schema: Mapping[str, Any] | None = None
    model: LLM | None = None

    def __str__(self) -> str:
        """User-friendly string representation of the LLM request."""
        request = 'LLM Request\n'
        if self.model:
            request += f'\n{self.model}\n'
        if self.system_prompt:
            request += f'\nSystem Prompt:\n\n{self.system_prompt}\n'
        request += f'\nUser Prompt:\n\n{self.user_prompt}\n'
        if self.response_schema:
            request += f'\nResponse Schema: {self.response_schema}\n'
        return request
