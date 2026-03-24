from dataclasses import dataclass


@dataclass(frozen=True)
class LLM:
    """LLM model."""

    name: str

    def __str__(self) -> str:
        """User-friendly string representation of the model."""
        return self.name

    def __post_init__(self) -> None:
        """Validate LLM invariants."""
        self._validate_name()

    def _validate_name(self) -> None:
        if not self.name.strip():
            raise ValueError('Model name cannot be empty')
