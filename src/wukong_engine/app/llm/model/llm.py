"""LLM model definition."""

from dataclasses import dataclass

from .values import LLMProvider


@dataclass(frozen=True, slots=True)
class LLM:
    """LLM identified by its model name and provider.

    Attributes:
        name: Provider-specific model name.
        provider: Provider offering the model.
    """

    name: str
    provider: LLMProvider = LLMProvider.OPENAI

    def __str__(self) -> str:
        """User-friendly string representation of the model."""
        return f'{self.name} ({self.provider.value})'

    def __post_init__(self) -> None:
        """Validate LLM invariants.

        Raises:
            ValueError: If the model name is empty.
        """
        self._validate_name()

    def _validate_name(self) -> None:
        """Validate that the model name is not empty.

        Raises:
            ValueError: If the model name is empty or only whitespace.
        """
        if not self.name.strip():
            raise ValueError('Model name cannot be empty')
