"""Knowledge Repository."""

from collections.abc import Iterator

from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.graph.elements import Entity, Relationship
from wukong_engine.core.graph.elements.values import EntityId, RelationshipId
from wukong_engine.core.graph.model import EntityType, RelationshipType


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

    def stream_relationships_by_type(self, relationship_type: RelationshipType) -> Iterator[Relationship]:
        """Stream relationships of a specific type from the knowledge base."""
        with self._uow as tx:
            yield from tx.relationships.stream_by_relationship_type(relationship_type)

    def stream_relationships_by_type_with_provenance(
        self,
        relationship_type: RelationshipType,
    ) -> Iterator[tuple[Relationship, tuple[ChunkId, ...]]]:
        """Stream relationships of a specific type along with their provenance information from the knowledge base."""
        with self._uow as tx:
            relationships = iter(tx.relationships.stream_by_relationship_type(relationship_type))
            provenance = iter(tx.relationships.stream_provenance_by_relationship_type(relationship_type))

            # Iterate through both streams in parallel, yielding relationships with their corresponding provenance information
            for relationship in relationships:
                relationship_provenance = next(provenance, None)

                # The provenance stream should not end before the relationship stream
                if relationship_provenance is None:
                    raise RuntimeError('Export: Relationship provenance stream ended before the relationship stream.')

                # The relationship ID in both streams should match due to the ordering guarantee
                if relationship.id != relationship_provenance.relationship_id:
                    raise RuntimeError(
                        f'Relationship stream and provenance stream are out of sync. '
                        f'Expected provenance for relationship {relationship.id}, '
                        f'got {relationship_provenance.relationship_id}.',
                    )

                yield relationship, relationship_provenance.chunk_ids

            # Provenance stream should not have any remaining entries after the relationship stream has ended
            remaining_provenance = next(provenance, None)
            if remaining_provenance is not None:
                raise RuntimeError(
                    f'Relationship provenance stream contains unexpected extra entry for '
                    f'relationship {remaining_provenance.relationship_id}.',
                )

    def stream_entity_provenance(self) -> Iterator[tuple[DocumentId | ChunkId, EntityId]]:
        """Stream provenance information for documents/chunks and their associated entities from the knowledge base."""
        with self._uow as tx:
            for provenance in tx.entities.stream_provenance_by_document():
                for entity_id in provenance.entity_ids:
                    yield provenance.document_id, entity_id
            for provenance in tx.entities.stream_provenance_by_chunk():
                for entity_id in provenance.entity_ids:
                    yield provenance.chunk_id, entity_id

    def stream_relationship_provenance(self) -> Iterator[tuple[ChunkId, RelationshipId]]:
        """Stream provenance information for chunks and their associated relationships from the knowledge base."""
        with self._uow as tx:
            for provenance in tx.relationships.stream_provenance_by_chunk():
                for relationship_id in provenance.relationship_ids:
                    yield provenance.chunk_id, relationship_id
