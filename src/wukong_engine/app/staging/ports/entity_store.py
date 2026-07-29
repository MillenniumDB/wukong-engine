from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.model.values import ContextLevel, DocumentCollectionName
from wukong_engine.core.graph.elements import ChunkEntityProvenance, DocumentEntityProvenance, Entity
from wukong_engine.core.graph.model import EntityType, GraphModel
from wukong_engine.core.graph.model.values import EntityTypeName


class EntityStore(Protocol):
    """Store for managing entities and entity types."""

    def add_entity_types(self, entity_type_names: Iterable[EntityTypeName]) -> None:
        """Add entity types."""
        ...

    def link_collections_to_entity_type(
        self,
        collection_names: Iterable[DocumentCollectionName],
        entity_type_name: EntityTypeName,
        context_level: ContextLevel,
    ) -> None:
        """Link a set of document collections to an entity type under a specific context level."""
        ...

    def bulk_upsert_entities(self, entities: Iterable[Entity]) -> None:
        """Insert or update a batch of entities, ensuring deduplication."""
        ...

    def link_entities_to_source_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link a batch of entities to their source context."""
        ...

    def stream_by_entity_type(self, entity_type: EntityType) -> Iterator[Entity]:
        """Stream all entities of a given type."""
        ...

    def stream_by_source_context(self, context: ContextRef, model: GraphModel) -> Iterator[Entity]:
        """Stream all entities linked to a specific source context."""
        ...

    def stream_provenance_by_document(self) -> Iterator[DocumentEntityProvenance]:
        """Stream all links of extracted entities and their source documents, grouped by document."""
        ...

    def stream_provenance_by_chunk(self) -> Iterator[ChunkEntityProvenance]:
        """Stream all links of extracted entities and their source chunks, grouped by chunk."""
        ...

    def count_entities(self, context_level: ContextLevel) -> int:
        """Count the number of unique entities for a given context level."""
        ...

    def count_entity_mentions(self, context_level: ContextLevel) -> int:
        """Count the number of entity mentions for a given context level."""
        ...

    def clear(self) -> None:
        """Reset the entity store."""
        ...
