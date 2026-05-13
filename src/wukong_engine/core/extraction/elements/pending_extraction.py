from dataclasses import dataclass

from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.graph.model.values import EntityTypeName


@dataclass(frozen=True)
class PendingDocumentExtraction:
    """Pending extraction of entity types from a document."""

    document: Document
    entity_types: tuple[EntityTypeName, ...]


@dataclass(frozen=True)
class PendingChunkExtraction:
    """Pending extraction of entity types from a chunk."""

    chunk: Chunk
    entity_types: tuple[EntityTypeName, ...]
