from typing import Protocol

from .document_store import DocumentStore
from .entity_store import EntityStore
from .extraction_store import ExtractionStore


# TODO: Complete protocol
class UnitOfWork(Protocol):
    """Unit of Work for managing staging operations across multiple stores."""

    document_store: DocumentStore
    entity_store: EntityStore
    extraction_store: ExtractionStore

    def commit(self) -> None:
        """Commit the staged changes to the underlying stores."""
        ...
