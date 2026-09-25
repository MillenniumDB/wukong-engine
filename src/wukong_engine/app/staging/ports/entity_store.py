"""Store port for staged entities, entity types and their provenance."""

from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.model.values import ContextLevel, DocumentCollectionName
from wukong_engine.core.knowledge.elements import ChunkEntityProvenance, DocumentEntityProvenance, Entity
from wukong_engine.core.knowledge.model import EntityType, KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName


class EntityStore(Protocol):
    """Store for managing entities and entity types."""

    def add_entity_types(self, entity_type_names: Iterable[EntityTypeName]) -> None:
        """Add entity types.

        Args:
            entity_type_names: Names of the entity types to add. Entity types that already exist are kept.
        """
        ...

    def link_collections_to_entity_type(
        self,
        collection_names: Iterable[DocumentCollectionName],
        entity_type_name: EntityTypeName,
        context_level: ContextLevel,
    ) -> None:
        """Link a set of document collections to an entity type under a specific context level.

        Args:
            collection_names: Collections to link.
            entity_type_name: Entity type extracted from the collections.
            context_level: Context level at which the entity type is extracted from the collections.
        """
        ...

    def bulk_upsert_entities(self, entities: Iterable[Entity]) -> None:
        """Insert or update a batch of entities, ensuring deduplication.

        Args:
            entities: Entities to store. Entities sharing a content ID are merged with each other and with the stored one.
        """
        ...

    def link_entities_to_source_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link a batch of entities to their source context.

        Args:
            entities: Entities extracted from the context.
            context: Source context (document or chunk) the entities were extracted from.
        """
        ...

    def stream_by_entity_type(self, entity_type: EntityType) -> Iterator[Entity]:
        """Stream all entities of a given type.

        Args:
            entity_type: Entity type to filter by.

        Yields:
            The stored entities of that type.
        """
        ...

    def stream_by_source_context(self, context: ContextRef, model: KnowledgeModel) -> Iterator[Entity]:
        """Stream all entities linked to a specific source context.

        Args:
            context: Source context whose linked entities are streamed.
            model: Knowledge model used to resolve each entity's type.

        Yields:
            The entities linked to the context.

        Raises:
            ValueError: If an entity's type isn't an active entity type in the knowledge model.
        """
        ...

    def stream_provenance_by_document(self) -> Iterator[DocumentEntityProvenance]:
        """Stream all links of extracted entities and their source documents, grouped by document.

        Yields:
            One provenance record per document with linked entities.
        """
        ...

    def stream_provenance_by_chunk(self) -> Iterator[ChunkEntityProvenance]:
        """Stream all links of extracted entities and their source chunks, grouped by chunk.

        Yields:
            One provenance record per chunk with linked entities.
        """
        ...

    def count_entities(self, context_level: ContextLevel) -> int:
        """Count the number of unique entities for a given context level.

        Args:
            context_level: Context level whose entity links are counted.

        Returns:
            The number of distinct entities linked to at least one source context of that level.
        """
        ...

    def count_entity_mentions(self, context_level: ContextLevel) -> int:
        """Count the number of entity mentions for a given context level.

        Args:
            context_level: Context level whose entity links are counted.

        Returns:
            The number of links between entities and source contexts of that level.
        """
        ...

    def clear(self) -> None:
        """Reset the entity store."""
        ...
