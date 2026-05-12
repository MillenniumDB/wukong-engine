from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.graph.elements import DocumentEntityTypes, Entity, EntityDocumentLink
from wukong_engine.core.graph.model.values import EntityTypeName


class EntityExtractionStore(Protocol):
    """Store for managing entity extraction."""

    def materialize_pending_extractions(self) -> None:
        """Generate pending entity type extractions from documents."""
        ...

    def link_extracted_entities_to_document(self, entities: Iterable[Entity], document: Document) -> None:
        """Link extracted entities to their source document."""
        ...

    def mark_completed_extractions_from_document(
        self,
        entity_type_names: Iterable[EntityTypeName],
        document: Document,
    ) -> None:
        """Mark completed entity type extractions from a source document."""
        ...

    def stream_pending_extractions(self) -> Iterator[DocumentEntityTypes]:
        """Stream documents with their pending entity types for extraction."""
        ...

    def stream_entity_document_links(self) -> Iterator[EntityDocumentLink]:
        """Stream all links of extracted entities and their source documents."""
        ...

    def clear(self) -> None:
        """Reset the entity extraction store."""
        ...
