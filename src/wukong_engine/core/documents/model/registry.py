"""Provides a document registry for the engine.

Classes:
    DocumentRegistry: The document registry containing all document collections/sources.
"""

from dataclasses import dataclass
from types import MappingProxyType

from wukong_engine.core.extraction.model.values import ContextLevel
from wukong_engine.core.graph.model import EntityType, GraphModel

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

    def validate_graph_model_collections(self, graph_model: GraphModel) -> None:
        """Validate that all entity type document collections reference known collection names.

        Args:
            graph_model: The graph model to validate against this registry.

        Raises:
            ValueError: If any entity type references a document collection name not present in this registry.
        """
        unknown: dict[str, list[str]] = {}
        for entity_type in graph_model.entity_types.values():
            for collections in entity_type.document_collections.values():
                for collection_name in collections:
                    if collection_name not in self.collections:
                        unknown.setdefault(str(entity_type.name), []).append(str(collection_name))
        if unknown:
            details = '; '.join(f'{e}: {c}' for e, c in unknown.items())
            raise ValueError(f'Unknown document collection names found in graph model: {details}')

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

    def get_entity_sources(self, entity_type: EntityType, context_level: ContextLevel) -> tuple[DocumentSource, ...]:
        """Return the respective DocumentSources for a given EntityType and ContextLevel.

        Args:
            entity_type: The entity type whose document collections to resolve.
            context_level: The context level to look up within the entity type.

        Returns:
            A tuple of unique DocumentSources corresponding to the EntityType/ContextLevel pair.
            Returns an empty tuple if the pair has no associated collections or the collections
            are not present in this registry.
        """
        collection_names = entity_type.document_collections.get(context_level, ())
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
