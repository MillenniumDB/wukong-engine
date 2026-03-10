from dataclasses import dataclass
from pathlib import PurePath

from .values import DocumentSourceMode


@dataclass(frozen=True)
class DocumentSource:
    """A document source."""

    source_path: PurePath
    mode: DocumentSourceMode

    def __str__(self) -> str:
        """User-friendly string representation of the document source."""
        return f'[{self.mode.value}] {self.source_path}'

    def __post_init__(self) -> None:
        """Validate document source invariants."""
        self._validate_path()

    def _validate_path(self) -> None:
        """Validate that the path is well-formed."""
        if not str(self.source_path).strip():
            raise ValueError('Path must not be empty.')
