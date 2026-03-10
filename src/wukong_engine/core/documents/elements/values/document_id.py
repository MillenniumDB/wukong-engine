import hashlib
from dataclasses import dataclass
from typing import ClassVar, Self


@dataclass(frozen=True)
class DocumentId:
    """The unique identifier for documents.

    The recommended ID has the format: Document_<hash>, where <hash> is the first 16 hex
    characters of the SHA-256 hash of the document's raw bytes.
    """

    value: str

    # Parameters for generating the document ID from content
    _PREFIX: ClassVar[str] = 'Document'
    _HASH_LENGTH: ClassVar[int] = 16

    def __str__(self) -> str:
        """User-friendly string representation of the document ID."""
        return self.value

    def __repr__(self) -> str:
        """Representation of the document ID."""
        return self.value

    @classmethod
    def from_bytes(cls, content: bytes) -> Self:
        """Create a DocumentId from the raw bytes of a document.

        Args:
            content: The raw bytes of the document.

        Returns:
            A DocumentId computed from the SHA-256 hash of the content.
        """
        full_hash = hashlib.sha256(content).hexdigest()
        return cls(value=f'{cls._PREFIX}_{full_hash[: cls._HASH_LENGTH]}')
