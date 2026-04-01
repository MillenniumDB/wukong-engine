from dataclasses import dataclass

from .source import DocumentSource
from .values import DocumentCollectionName


@dataclass(frozen=True)
class DocumentCollection:
    """A document collection."""

    name: DocumentCollectionName
    sources: tuple[DocumentSource, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the collection."""
        lines = []
        lines.append(str(self.name))
        lines.append(f'  • {"\n  • ".join(str(source) for source in self.sources)}')
        return '\n'.join(lines)

    def __post_init__(self) -> None:
        """Validate document collection invariants."""
        self._validate_sources()

    def _validate_sources(self) -> None:
        """Validate that sources contain no duplicates."""
        if len(self.sources) != len(set(self.sources)):
            duplicates = {str(s) for s in self.sources if self.sources.count(s) > 1}
            raise ValueError(f'Duplicated sources found in document collection "{self.name}": {duplicates}')
