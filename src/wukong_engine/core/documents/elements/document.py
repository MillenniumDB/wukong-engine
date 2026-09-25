"""Provides the Document class.

Classes:
    Document: A source document.
"""

from dataclasses import dataclass

from wukong_engine.core.documents.model.values import ContextLevel

from .context_ref import ContextRef
from .values import DocumentId


@dataclass(frozen=True, slots=True)
class Document:
    """A source document.

    Attributes:
        id: Unique identifier of the document.
        source_uri: URI the document was loaded from.
    """

    id: DocumentId
    source_uri: str

    def __str__(self) -> str:
        """User-friendly string representation of a document."""
        return f'{self.id.content} ({self.source_uri})'

    @property
    def context_ref(self) -> ContextRef:
        """Context reference for the document."""
        return ContextRef(
            level=ContextLevel.DOCUMENT,
            content_id=self.id.content,
        )


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    """A source document that has been loaded into memory, including its content.

    Attributes:
        metadata: The document's identity and source.
        content: Full text content of the document.
    """

    metadata: Document
    content: str
