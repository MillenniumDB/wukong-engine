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
        seen = set()
        for source in self.sources:
            if source in seen:
                raise ValueError(f'Duplicated source in document collections: {source}')
            seen.add(source)
