"""Knowledge Repository."""

from collections.abc import Iterator

from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.graph.elements import Entity, Relationship
from wukong_engine.core.graph.model import EntityType, RelationshipType


# TODO: Implement
class KnowledgeRepository:
    """Repository for retrieving extracted knowledge."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the repository with necessary dependencies."""
        self._uow = uow

    def stream_all_documents(self) -> Iterator[Document]:
        """Stream all documents from the knowledge base."""
        with self._uow as tx:
            yield from tx.documents.stream_all_documents()

    def stream_all_chunks(self) -> Iterator[Chunk]:
        """Stream all document chunks from the knowledge base."""
        with self._uow as tx:
            yield from tx.documents.stream_all_chunks()

    def stream_entities_by_type(self, entity_type: EntityType) -> Iterator[Entity]:
        """Stream entities of a specific type from the knowledge base."""
        with self._uow as tx:
            yield from tx.entities.stream_by_entity_type(entity_type)
