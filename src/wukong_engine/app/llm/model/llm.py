from dataclasses import dataclass

from .values import LLMProvider


@dataclass(frozen=True)
class LLM:
    """LLM."""

    name: str
    provider: LLMProvider = LLMProvider.OPENAI

    def __str__(self) -> str:
        """User-friendly string representation of the model."""
        return f'{self.name} ({self.provider.value})'

    def __post_init__(self) -> None:
        """Validate LLM invariants."""
        self._validate_name()

    def _validate_name(self) -> None:
        """Validate that the model name is not empty."""
        if not self.name.strip():
            raise ValueError('Model name cannot be empty')
