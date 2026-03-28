from dataclasses import dataclass

from .provider import LLMProvider


@dataclass(frozen=True)
class LLM:
    """LLM model."""

    name: str
    provider: LLMProvider = LLMProvider.OPENAI

    def __str__(self) -> str:
        """User-friendly string representation of the model."""
        return f'Model: {self.name} ({self.provider.value})'

    def __post_init__(self) -> None:
        """Validate LLM invariants."""
        self._validate_name()

    def _validate_name(self) -> None:
        if not self.name.strip():
            raise ValueError('Model name cannot be empty')
