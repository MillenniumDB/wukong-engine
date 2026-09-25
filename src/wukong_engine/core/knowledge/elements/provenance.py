"""Provenance links between extracted knowledge and its source documents and chunks."""

from dataclasses import dataclass

from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName

from .values import EntityId, RelationshipId


# Entities
@dataclass(frozen=True, slots=True)
class DocumentEntityProvenance:
    """Provenance between a source document and all its extracted entities.

    Attributes:
        document_id: Identifier of the source document.
        entity_ids: Identifiers of the entities extracted from the document.
        entity_types: Type names of the extracted entities, aligned with ``entity_ids``.
    """

    document_id: DocumentId
    entity_ids: tuple[EntityId, ...]
    entity_types: tuple[EntityTypeName, ...]


@dataclass(frozen=True, slots=True)
class ChunkEntityProvenance:
    """Provenance between a source chunk and all its extracted entities.

    Attributes:
        chunk_id: Identifier of the source chunk.
        parent_document_id: Identifier of the document the chunk belongs to.
        entity_ids: Identifiers of the entities extracted from the chunk.
        entity_types: Type names of the extracted entities, aligned with ``entity_ids``.
    """

    chunk_id: ChunkId
    parent_document_id: DocumentId
    entity_ids: tuple[EntityId, ...]
    entity_types: tuple[EntityTypeName, ...]


# Relationships
@dataclass(frozen=True, slots=True)
class ChunkRelationshipProvenance:
    """Provenance between a source chunk and all its extracted relationships.

    Attributes:
        chunk_id: Identifier of the source chunk.
        parent_document_id: Identifier of the document the chunk belongs to.
        relationship_ids: Identifiers of the relationships extracted from the chunk.
        relationship_types: Type names of the extracted relationships, aligned with ``relationship_ids``.
    """

    chunk_id: ChunkId
    parent_document_id: DocumentId
    relationship_ids: tuple[RelationshipId, ...]
    relationship_types: tuple[RelationshipTypeName, ...]


@dataclass(frozen=True, slots=True)
class RelationshipChunkProvenance:
    """Provenance between a relationship and all its source chunks.

    Attributes:
        relationship_id: Identifier of the relationship.
        relationship_type: Type name of the relationship.
        chunk_ids: Identifiers of the chunks the relationship was extracted from.
    """

    relationship_id: RelationshipId
    relationship_type: RelationshipTypeName
    chunk_ids: tuple[ChunkId, ...]
