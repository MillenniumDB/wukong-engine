"""Provides a document registry for the engine.

Classes:
    DocumentRegistry: The document registry containing all document collections/sources.
"""

from dataclasses import dataclass
from types import MappingProxyType

from .collection import DocumentCollection
from .source import DocumentSource
from .values import DocumentCollectionName


@dataclass(frozen=True, slots=True)
class DocumentRegistry:
    """The document registry.

    Attributes:
        collections: Read-only mapping from collection name to its document collection.
    """

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
            ValueError: If any collection name in the set is not found in the registry.
        """
        unknown_collections = sorted(f'"{name}"' for name in collection_names if name not in self.collections)
        if unknown_collections:
            details = ', '.join(unknown_collections)
            raise ValueError(f'Unknown document collection names found: {details}')

    def sources_missing_from(
        self,
        other: DocumentRegistry,
    ) -> tuple[tuple[DocumentCollectionName, DocumentSource], ...]:
        """Find the sources of this registry that another registry leaves out.

        Another registry extends this one when it leaves none out: it may only add collections, and sources to them.

        Args:
            other: Registry compared with this one.

        Returns:
            The name of the collection and the source of every source of this registry missing from the same
            collection in ``other``, in order; empty if ``other`` extends this registry.
        """
        missing: list[tuple[DocumentCollectionName, DocumentSource]] = []
        for name, collection in self.collections.items():
            other_collection = other.collections.get(name)
            kept = set(other_collection.sources) if other_collection is not None else set()
            missing.extend((name, source) for source in collection.sources if source not in kept)
        return tuple(missing)

    def get_all_sources(self) -> tuple[DocumentSource, ...]:
        """Return all unique DocumentSources contained in all collections.

        Returns:
            The unique sources across all collections, in order of first appearance.
        """
        seen: set[DocumentSource] = set()
        sources: list[DocumentSource] = []
        for collection in self.collections.values():
            for source in collection.sources:
                if source not in seen:
                    seen.add(source)
                    sources.append(source)
        return tuple(sources)
