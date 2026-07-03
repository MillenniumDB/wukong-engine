from dataclasses import dataclass

from wukong_engine.core.documents.elements.values import ChunkId, DocumentId

from .values import EntityId, RelationshipId


@dataclass(frozen=True)
class EntityDocumentProvenance:
    """Provenance between an extracted entity and its source document."""

    entity_id: EntityId
    document_id: DocumentId


@dataclass(frozen=True)
class EntityChunkProvenance:
    """Provenance between an extracted entity and its source chunk."""

    entity_id: EntityId
    chunk_id: ChunkId


@dataclass(frozen=True)
class RelationshipChunkProvenance:
    """Provenance between an extracted relationship and its source chunk."""

    relationship_id: RelationshipId
    chunk_id: ChunkId
