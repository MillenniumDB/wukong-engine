"""Provides a document registry for the engine.

Classes:
    DocumentRegistry: The document registry containing all document collections/sources.
"""

from dataclasses import dataclass
from types import MappingProxyType

from .collection import DocumentCollection
from .source import DocumentSource
from .values import DocumentCollectionName


@dataclass(frozen=True)
class DocumentRegistry:
    """The document registry."""

    collections: MappingProxyType[DocumentCollectionName, DocumentCollection]

    def __str__(self) -> str:
        """User-friendly string representation of the document registry."""
        lines = []
        lines.append('=' * 80)
        lines.append(f' DOCUMENT COLLECTIONS ({len(self.collections)} total)')
        lines.append('=' * 80)

        # Collections
        for collection in self.collections.values():
            lines.append('')
            lines.extend(f'  {line}' for line in str(collection).split('\n'))

        lines.append('\n' + '=' * 80 + '\n')
        return '\n'.join(lines)

    def validate_collections(self, collection_names: frozenset[DocumentCollectionName]) -> None:
        """Validate that all document collections in a set reference known collections.

        Args:
            collection_names: A set of document collection names to validate.

        Raises:
            ValueError: If any collection name in the input set is not found in the registry.
        """
        unknown_collections = sorted(f'"{name}"' for name in collection_names if name not in self.collections)
        if unknown_collections:
            details = ', '.join(unknown_collections)
            raise ValueError(f'Unknown document collection names found: {details}')

    def get_all_sources(self) -> tuple[DocumentSource, ...]:
        """Return all unique DocumentSources contained in all collections."""
        seen: set[DocumentSource] = set()
        sources: list[DocumentSource] = []
        for collection in self.collections.values():
            for source in collection.sources:
                if source not in seen:
                    seen.add(source)
                    sources.append(source)
        return tuple(sources)

    def get_collection_sources(
        self,
        collection_names: tuple[DocumentCollectionName, ...],
    ) -> tuple[DocumentSource, ...]:
        """Get all respective DocumentSources for a given list of collections.

        Args:
            collection_names: A tuple of document collection names to retrieve sources for.

        Returns:
            A tuple of unique DocumentSources corresponding to the input collection names.
        """
        seen: set[DocumentSource] = set()
        sources: list[DocumentSource] = []
        for name in collection_names:
            collection = self.collections.get(name)
            if collection is None:
                continue
            for source in collection.sources:
                if source not in seen:
                    seen.add(source)
                    sources.append(source)
        return tuple(sources)
