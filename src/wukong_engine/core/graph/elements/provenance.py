from dataclasses import dataclass

from wukong_engine.core.documents.elements.values import ChunkId, DocumentId

from .values import EntityId


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
