"""Unit of work port grouping the staging stores in a single transaction."""

from types import TracebackType
from typing import Protocol, Self

from .document_store import DocumentStore
from .entity_store import EntityStore
from .extraction_store import ExtractionStore
from .pipeline_store import PipelineStore
from .relationship_store import RelationshipStore


class UnitOfWork(Protocol):
    """Unit of Work for managing operations across multiple staging stores.

    The stores are only usable inside the context, whose exit commits the staged changes, or rolls them back if an
    exception was raised.

    Attributes:
        documents: Store for documents and collections.
        entities: Store for entities and entity types.
        relationships: Store for relationships and relationship types.
        extraction: Store for entity and relationship extractions.
        pipeline: Store for the pipeline state.
    """

    documents: DocumentStore
    entities: EntityStore
    relationships: RelationshipStore
    extraction: ExtractionStore
    pipeline: PipelineStore

    def __enter__(self) -> Self:
        """Enter the runtime context related to this object.

        Raises:
            RuntimeError: If the context is already active, since nested contexts are not supported.
        """
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
        """Commit the staged changes to the underlying stores.

        Raises:
            RuntimeError: If the unit of work is not active.
        """
        ...

    def rollback(self) -> None:
        """Rollback any staged changes in case of an error.

        Raises:
            RuntimeError: If the unit of work is not active.
        """
        ...
