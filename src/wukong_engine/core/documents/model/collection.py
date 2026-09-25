"""Named collections of document sources."""

from dataclasses import dataclass

from .source import DocumentSource
from .values import DocumentCollectionName


@dataclass(frozen=True, slots=True)
class DocumentCollection:
    """A document collection.

    Attributes:
        name: Unique name of the collection.
        sources: Document sources belonging to the collection; must not contain duplicates.
    """

    name: DocumentCollectionName
    sources: tuple[DocumentSource, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the collection."""
        lines = []
        lines.append(str(self.name))
        lines.append(f'  • {"\n  • ".join(str(source) for source in self.sources)}')
        return '\n'.join(lines)

    def __post_init__(self) -> None:
        """Validate document collection invariants.

        Raises:
            ValueError: If the collection contains duplicated sources.
        """
        self._validate_sources()

    def _validate_sources(self) -> None:
        """Validate that sources contain no duplicates.

        Raises:
            ValueError: If any source appears more than once.
        """
        if len(self.sources) != len(set(self.sources)):
            duplicates = {str(s) for s in self.sources if self.sources.count(s) > 1}
            raise ValueError(f'Duplicated sources found in document collection "{self.name}": {duplicates}')
