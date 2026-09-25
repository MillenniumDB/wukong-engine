"""SQLite unit of work binding the staging stores to a single transaction."""

import sqlite3
from collections.abc import Callable
from types import TracebackType
from typing import Self

from wukong_engine.app.staging.ports import UnitOfWork

from .stores import (
    SQLiteDocumentStore,
    SQLiteEntityStore,
    SQLiteExtractionStore,
    SQLitePipelineStore,
    SQLiteRelationshipStore,
)


class SQLiteUnitOfWork(UnitOfWork):
    """SQLite implementation of the UnitOfWork.

    Each context opens a new connection from the factory, begins a transaction and binds fresh stores to it; the
    connection is closed when the context exits.

    Attributes:
        documents: Document store bound to the active connection.
        entities: Entity store bound to the active connection.
        relationships: Relationship store bound to the active connection.
        extraction: Extraction store bound to the active connection.
        pipeline: Pipeline store bound to the active connection.
    """

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        """Initialize the UnitOfWork with a SQLite connection factory.

        Args:
            connection_factory: Callable returning a new SQLite connection, called on each context entry.
        """
        # Connection management
        self._connection_factory = connection_factory
        self._conn: sqlite3.Connection | None = None
        self._active = False  # To prevent nested transactions

        # Staging stores
        self.documents: SQLiteDocumentStore
        self.entities: SQLiteEntityStore
        self.relationships: SQLiteRelationshipStore
        self.extraction: SQLiteExtractionStore
        self.pipeline: SQLitePipelineStore

    def __enter__(self) -> Self:
        """Enter the runtime context related to an SQLite transaction.

        Raises:
            RuntimeError: If the context is already active, since nested transactions are not supported.
        """
        if self._active:
            raise RuntimeError('Nested transaction contexts are not supported.')

        # Open connection and begin transaction
        self._conn = self._connection_factory()
        self._conn.execute('BEGIN')

        # Bind stores to the connection
        self.documents = SQLiteDocumentStore(self._conn)
        self.entities = SQLiteEntityStore(self._conn)
        self.relationships = SQLiteRelationshipStore(self._conn)
        self.extraction = SQLiteExtractionStore(self._conn)
        self.pipeline = SQLitePipelineStore(self._conn)

        self._active = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the runtime context and handle commit or rollback."""
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self._cleanup()

    def commit(self) -> None:
        """Commit the staged changes to the underlying stores.

        Raises:
            RuntimeError: If the unit of work is not active.
        """
        if not self._active or self._conn is None:
            raise RuntimeError('Cannot commit: UnitOfWork is not active')
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback any staged changes in case of an error.

        Raises:
            RuntimeError: If the unit of work is not active.
        """
        if not self._active or self._conn is None:
            raise RuntimeError('Cannot rollback: UnitOfWork is not active')
        self._conn.rollback()

    def _cleanup(self) -> None:
        """Cleanup used resources."""
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
                self._active = False
