from types import TracebackType
from typing import Protocol, Self

from .document_store import DocumentStore
from .entity_store import EntityStore
from .extraction_store import ExtractionStore


# TODO: Test with DocumentStore
# def ingest_documents(stream, uow: UnitOfWork):
#     with uow as tx:
#         for batch in batched(stream, 1000):
#             tx.documents.upsert_documents(batch)
#             tx.documents.link_documents_to_collection(
#                 [doc_id for doc_id, *_ in batch],
#                 collection_name,
#             )
# TODO: Clear
class UnitOfWork(Protocol):
    """Unit of Work for managing operations across multiple staging stores."""

    documents: DocumentStore
    entities: EntityStore
    extraction: ExtractionStore

    def __enter__(self) -> Self:
        """Enter the runtime context related to this object."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the runtime context and handle commit or rollback."""
        ...

    def commit(self) -> None:
        """Commit the staged changes to the underlying stores."""
        ...

    def rollback(self) -> None:
        """Rollback any staged changes in case of an error."""
        ...
