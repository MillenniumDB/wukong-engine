"""Request model for LLM interactions."""

from dataclasses import dataclass

from wukong_engine.app.llm.model import LLM

from .values import LLMPrompt, ReasoningEffort


@dataclass(frozen=True)
class LLMRequest:
    """Fully rendered request to be executed by an LLM client."""

    prompt: LLMPrompt
    model: LLM | None = None
    reasoning_effort: ReasoningEffort | None = None
    temperature: float | None = None

    def __str__(self) -> str:
        """User-friendly string representation of the LLM request."""
        request = 'LLM Request\n'
        if self.model:
            request += f'\n{self.model}\n'
        if self.reasoning_effort:
            request += f'\nReasoning Effort: {self.reasoning_effort.value}\n'
        if self.temperature is not None:
            request += f'\nTemperature: {self.temperature}\n'
        request += str(self.prompt)
        return request
