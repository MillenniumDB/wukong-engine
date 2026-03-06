"""Provides a document registry for the engine.

Classes:
    DocumentRegistry: The document registry containing all document collections/sources.
"""

from dataclasses import dataclass
from types import MappingProxyType

from wukong_engine.core.graph.model import GraphModel

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

    def validate_graph_model_collections(self, graph_model: GraphModel) -> None:
        """Validate that all entity type document collections reference known collection names.

        Args:
            graph_model: The graph model to validate against this registry.

        Raises:
            ValueError: If any entity type references a document collection name not present in this registry.
        """
        unknown: dict[str, list[str]] = {}
        for entity_name, entity_type in graph_model.entity_types.items():
            for collections in entity_type.document_collections.values():
                for collection_name in collections:
                    if collection_name not in self.collections:
                        unknown.setdefault(str(entity_name), []).append(str(collection_name))
        if unknown:
            details = '; '.join(f'{e}: {c}' for e, c in unknown.items())
            raise ValueError(f'Unknown document collection names found in graph model: {details}')
