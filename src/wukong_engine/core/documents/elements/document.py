"""Provides the Document class.

Classes:
    Document: A loaded document.
"""

from dataclasses import dataclass
from pathlib import PurePath

from .values import DocumentId


@dataclass(frozen=True)
class Document:
    """A loaded document."""

    id: DocumentId
    text: str
    source_path: PurePath

    def __str__(self) -> str:
        """User-friendly string representation of a document."""
        return f'{self.id} from {self.source_path}:\n{self.text[:20]}...'
