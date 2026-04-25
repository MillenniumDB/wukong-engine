"""Provides the Document class.

Classes:
    Document: A loaded document.
"""

from dataclasses import dataclass

from .values import DocumentId


@dataclass(frozen=True)
class Document:
    """A loaded document."""

    id: DocumentId
    source_uri: str

    def __str__(self) -> str:
        """User-friendly string representation of a document."""
        return f'{self.id} ({self.source_uri})'
