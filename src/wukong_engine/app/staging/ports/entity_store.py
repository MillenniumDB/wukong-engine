from collections.abc import Iterator
from typing import Protocol

from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.model.values import EntityTypeName

# TODO: upsert_entities(entities)  # batch, keyed by content_id

# TODO: stream_entities_by_type(entity_type)

# SELECT * FROM entities WHERE entity_type = ?

# CREATE INDEX idx_entities_type ON entities(entity_type);


# TODO: Complete protocol
class EntityStore(Protocol):
    """Store for managing entities."""

    # def upsert_batch(self, entities: tuple[Entity, ...], document_ids: tuple[DocumentId, ...]) -> None:
    #     """Insert or update a batch of entities, linking them to their source documents/chunks for provenance.

    #     Deduplicates entities using content ID, handles merge if duplicates exist.
    #     Provenance links are also deduplicated.

    #     Args:
    #         entities: The entities to be inserted or updated.
    #         document_ids: The IDs of the source documents/chunks for provenance.
    #     """
    #     ...

    # def upsert(self, entity: Entity, document_id: DocumentId) -> None:
    #     """Insert or update entity, and link it to the source document/chunk for provenance.

    #     Deduplicates the entity using content ID, handles merge if duplicate exists.
    #     Provenance link is also deduplicated.

    #     Args:
    #         entity: The entity to be inserted or updated.
    #         document_id: The ID of the source document/chunk for provenance.
    #     """
    #     self.upsert_batch((entity,), (document_id,))

    # def stream_by_type(self, entity_type: EntityTypeName) -> Iterator[Entity]:
    #     """Stream all entities of a given type."""
    #     ...

    # def clear(self) -> None:
    #     """Reset entity store."""
    #     ...
