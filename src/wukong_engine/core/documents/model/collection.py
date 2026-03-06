from dataclasses import dataclass

from .source import DocumentSource


@dataclass(frozen=True)
class DocumentCollection:
    """A document collection."""

    sources: tuple[DocumentSource, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the collection."""
        return '\n'.join(str(source) for source in self.sources)

    def __post_init__(self) -> None:
        """Validate document collection invariants."""
        self._validate_sources()

    def _validate_sources(self) -> None:
        """Validate that sources contain no duplicates."""
        if len(self.sources) != len(set(self.sources)):
            duplicates = {str(s) for s in self.sources if self.sources.count(s) > 1}
            raise ValueError(f'Duplicate sources found in document collection: {duplicates}')
