import sqlite3
from collections.abc import Callable
from types import TracebackType
from typing import Self

from wukong_engine.app.staging.ports import UnitOfWork

from .stores import SQLiteDocumentStore, SQLiteEntityExtractionStore, SQLiteEntityStore


class SQLiteUnitOfWork(UnitOfWork):
    """SQLite implementation of the UnitOfWork."""

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        """Initialize the UnitOfWork with a SQLite connection."""
        # Connection management
        self._connection_factory = connection_factory
        self._conn: sqlite3.Connection | None = None
        self._active = False  # To prevent nested transactions

        # Staging stores
        self.documents: SQLiteDocumentStore
        self.entities: SQLiteEntityStore
        self.extraction: SQLiteEntityExtractionStore

    def __enter__(self) -> Self:
        """Enter the runtime context related to an SQLite transaction."""
        if self._active:
            raise RuntimeError('Nested transaction contexts are not supported.')

        # Open connection and begin transaction
        self._conn = self._connection_factory()
        self._conn.execute('BEGIN')

        # Bind stores to the connection
        self.documents = SQLiteDocumentStore(self._conn)
        self.entities = SQLiteEntityStore(self._conn)
        self.extraction = SQLiteEntityExtractionStore(self._conn)

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
        """Commit the staged changes to the underlying stores."""
        if not self._active or self._conn is None:
            raise RuntimeError('Cannot commit: UnitOfWork is not active')
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback any staged changes in case of an error."""
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
