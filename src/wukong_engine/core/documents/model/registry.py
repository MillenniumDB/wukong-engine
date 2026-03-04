"""Provides a document registry for the engine.

Classes:
    DocumentRegistry: The document registry containing all document collections/sources.
"""

from dataclasses import dataclass
from types import MappingProxyType

from .collection import DocumentCollection
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
        for collection_name, collection in self.collections.items():
            lines.append(f'\n{collection_name.value}')
            collection_str = str(collection)
            lines.extend(f'  {line}' for line in collection_str.split('\n'))

        lines.append('\n' + '=' * 80 + '\n')
        return '\n'.join(lines)
