from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.model.values import DocumentCollectionName
from wukong_engine.core.extraction.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.model import EntityType
from wukong_engine.core.graph.model.values import EntityTypeName


class EntityStore(Protocol):
    """Store for managing entities and entity types."""

    def bulk_upsert(self, entities: Iterable[Entity]) -> None:
        """Insert or update a batch of entities based on their content, ensuring deduplication."""
        ...

    def add_types(self, entity_type_names: Iterable[EntityTypeName]) -> None:
        """Add entity types."""
        ...

    def link_collections_to_type(
        self,
        collection_names: Iterable[DocumentCollectionName],
        entity_type_name: EntityTypeName,
        context_level: ContextLevel,
    ) -> None:
        """Link a set of document collections to an entity type under a specific context level."""
        ...

    def stream_by_type(self, entity_type: EntityType) -> Iterator[Entity]:
        """Stream all entities of a given type."""
        ...

    def clear(self) -> None:
        """Reset the entity store."""
        ...
