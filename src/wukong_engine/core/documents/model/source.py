from dataclasses import dataclass

from .values import DocumentSourceMode


@dataclass(frozen=True)
class DocumentSource:
    """A document source."""

    root: str
    mode: DocumentSourceMode

    def __str__(self) -> str:
        """User-friendly string representation of the document source."""
        return f'[{self.mode.value}] {self.root}'

    def __post_init__(self) -> None:
        """Validate document source invariants."""
        self._validate_root()

    def _validate_root(self) -> None:
        """Validate that the root is well-formed."""
        if not self.root.strip():
            raise ValueError('Root must not be empty.')
