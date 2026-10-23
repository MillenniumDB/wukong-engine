"""Knowledge Repository."""

from collections.abc import Collection, Iterable, Iterator

from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.knowledge.elements import Entity, Relationship
from wukong_engine.core.knowledge.elements.values import EntityId, RelationshipId
from wukong_engine.core.knowledge.model import Endpoint, EntityType, RelationshipType
from wukong_engine.core.knowledge.model.values import EntityTypeName


class KnowledgeRepository:
    """Repository for retrieving extracted knowledge."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the repository with necessary dependencies.

        Args:
            uow: Unit of work used to open a staging transaction for each stream.
        """
        self._uow = uow

    def stream_all_documents(self) -> Iterator[Document]:
        """Stream all documents from the knowledge base.

        Yields:
            Each stored document.
        """
        with self._uow as tx:
            yield from tx.documents.stream_all_documents()

    def stream_all_chunks(self) -> Iterator[Chunk]:
        """Stream all document chunks from the knowledge base.

        Yields:
            Each stored chunk.
        """
        with self._uow as tx:
            yield from tx.documents.stream_all_chunks()

    def stream_entities_by_type(self, entity_type: EntityType) -> Iterator[Entity]:
        """Stream entities of a specific type from the knowledge base.

        Args:
            entity_type: Entity type whose entities are streamed.

        Yields:
            Each stored entity of the given type.
        """
        with self._uow as tx:
            yield from tx.entities.stream_by_entity_type(entity_type)

    def stream_relationships_by_type(
        self,
        relationship_type: RelationshipType,
        endpoints: Iterable[Endpoint],
    ) -> Iterator[Relationship]:
        """Stream relationships of a specific type from the knowledge base.

        Args:
            relationship_type: Relationship type whose relationships are streamed.
            endpoints: Allowed (source, target) entity type pairs; relationships between other types are skipped.

        Yields:
            Each stored relationship of the given type between the allowed entity types.
        """
        with self._uow as tx:
            yield from tx.relationships.stream_by_relationship_type(relationship_type, endpoints)

    def stream_relationships_by_type_with_provenance(
        self,
        relationship_type: RelationshipType,
        endpoints: Iterable[Endpoint],
    ) -> Iterator[tuple[Relationship, tuple[ChunkId, ...]]]:
        """Stream relationships of a specific type along with their provenance information from the knowledge base.

        The relationship and provenance streams are consumed in lockstep, relying on both being ordered by
        relationship identifier.

        Args:
            relationship_type: Relationship type whose relationships are streamed.
            endpoints: Allowed (source, target) entity type pairs; relationships between other types are skipped.

        Yields:
            Tuples of (relationship, identifiers of the chunks the relationship was extracted from).

        Raises:
            RuntimeError: If the provenance stream ends early, contains extra entries, or falls out of sync with the
                relationship stream.
        """
        with self._uow as tx:
            endpoints = tuple(endpoints)
            relationships = iter(tx.relationships.stream_by_relationship_type(relationship_type, endpoints))
            provenance = iter(tx.relationships.stream_provenance_by_relationship_type(relationship_type, endpoints))

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

    def stream_entity_provenance(
        self,
        entity_types: Collection[EntityTypeName],
    ) -> Iterator[tuple[DocumentId | ChunkId, EntityId]]:
        """Stream provenance information for documents/chunks and their associated entities from the knowledge base.

        Document-level provenance is streamed first, followed by chunk-level provenance.

        Args:
            entity_types: Entity types whose provenance is streamed; links to entities of other types are skipped.

        Yields:
            Tuples of (identifier of the source document or chunk, identifier of an entity extracted from it).
        """
        with self._uow as tx:
            for provenance in tx.entities.stream_provenance_by_document():
                for entity_id, entity_type in zip(provenance.entity_ids, provenance.entity_types, strict=True):
                    if entity_type in entity_types:
                        yield provenance.document_id, entity_id
            for provenance in tx.entities.stream_provenance_by_chunk():
                for entity_id, entity_type in zip(provenance.entity_ids, provenance.entity_types, strict=True):
                    if entity_type in entity_types:
                        yield provenance.chunk_id, entity_id

    def stream_relationship_provenance(self) -> Iterator[tuple[ChunkId, RelationshipId]]:
        """Stream provenance information for chunks and their associated relationships from the knowledge base.

        Yields:
            Tuples of (chunk identifier, identifier of a relationship extracted from that chunk).
        """
        with self._uow as tx:
            for provenance in tx.relationships.stream_provenance_by_chunk():
                for relationship_id in provenance.relationship_ids:
                    yield provenance.chunk_id, relationship_id
