from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.app.data_extraction.dtos import EntityExtractionJob
from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity, EntityChunkProvenance, EntityDocumentProvenance
from wukong_engine.core.graph.model.values import EntityTypeName


class EntityExtractionStore(Protocol):
    """Store for managing entity extraction."""

    def materialize_pending_extractions(self, context_level: ContextLevel) -> None:
        """Generate pending entity type extractions for source contexts."""
        ...

    def link_extracted_entities_to_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link extracted entities to their source context."""
        ...

    def mark_completed_extractions_from_context(
        self,
        entity_type_names: Iterable[EntityTypeName],
        context: ContextRef,
    ) -> None:
        """Mark completed entity type extractions from a source context."""
        ...

    def stream_pending_document_extractions(self) -> Iterator[EntityExtractionJob]:
        """Stream source documents with their pending entity types for extraction."""
        ...

    def stream_pending_chunk_extractions(self) -> Iterator[EntityExtractionJob]:
        """Stream source chunks with their pending entity types for extraction."""
        ...

    def stream_entity_document_provenance(self) -> Iterator[EntityDocumentProvenance]:
        """Stream all links of extracted entities and their source documents."""
        ...

    def stream_entity_chunk_provenance(self) -> Iterator[EntityChunkProvenance]:
        """Stream all links of extracted entities and their source chunks."""
        ...

    def clear(self) -> None:
        """Reset the entity extraction store."""
        ...
