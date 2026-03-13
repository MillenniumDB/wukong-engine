import hashlib
from dataclasses import dataclass
from typing import ClassVar, Self


@dataclass(frozen=True)
class DocumentId:
    """The unique identifier for documents."""

    hash: bytes

    # Parameters for generating the document ID from content
    _HASH_SIZE: ClassVar[int] = 16  # 16 bytes → 128 bits → 32 hex chars

    def __post_init__(self) -> None:
        """Validate document id invariants."""
        self._validate_hash()

    def __str__(self) -> str:
        """User-friendly string representation of the document ID."""
        return f'Document_{self.hash.hex()}'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the document ID."""
        return f'DocumentID({self.hash.hex()})'

    def _validate_hash(self) -> None:
        """Validate that the hash has the correct length."""
        if len(self.hash) != self._HASH_SIZE:
            raise ValueError(
                f'Invalid hash length: expected {self._HASH_SIZE} bytes, got {len(self.hash)}',
            )

    @classmethod
    def from_content(cls, content: bytes) -> Self:
        """Create a DocumentId from the raw bytes of a document.

        Args:
            content: The raw bytes of the document.

        Returns:
            A DocumentId computed from the SHA-256 hash of the content.
        """
        return cls(hash=hashlib.sha256(content).digest()[: cls._HASH_SIZE])
