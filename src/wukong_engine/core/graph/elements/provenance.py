from dataclasses import dataclass

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.graph.model.values import EntityTypeName

from .values import EntityId


@dataclass(frozen=True)
class EntityDocumentLink:
    """A link between an extracted entity and its source document."""

    entity_id: EntityId
    document_id: DocumentId


@dataclass(frozen=True)
class DocumentEntityTypes:
    """A document with its associated entity types."""

    document: Document
    entity_types: tuple[EntityTypeName, ...]
