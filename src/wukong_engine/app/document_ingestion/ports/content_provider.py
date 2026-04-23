from typing import Protocol

from wukong_engine.core.documents.elements import Document


class DocumentContentProvider(Protocol):
    """Provides the text content of a specific document."""

    def get_content(self, document: Document, encoding: str = 'utf-8') -> str | None:
        """Retrieve the text content of the specified document."""
        ...
