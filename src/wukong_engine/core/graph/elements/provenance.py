from dataclasses import dataclass

from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipTypeName

from .values import EntityId, RelationshipId


@dataclass(frozen=True)
class DocumentEntityProvenance:
    """Provenance between a source document and all its extracted entities."""

    document_id: DocumentId
    entity_ids: tuple[EntityId, ...]
    entity_types: tuple[EntityTypeName, ...]


@dataclass(frozen=True)
class ChunkEntityProvenance:
    """Provenance between a source chunk and all its extracted entities."""

    chunk_id: ChunkId
    parent_document_id: DocumentId
    entity_ids: tuple[EntityId, ...]
    entity_types: tuple[EntityTypeName, ...]


@dataclass(frozen=True)
class ChunkRelationshipProvenance:
    """Provenance between a source chunk and all its extracted relationships."""

    chunk_id: ChunkId
    parent_document_id: DocumentId
    relationship_ids: tuple[RelationshipId, ...]
    relationship_types: tuple[RelationshipTypeName, ...]
