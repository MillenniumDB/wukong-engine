import sqlite3
from types import TracebackType
from typing import Self

from wukong_engine.app.staging.ports import UnitOfWork

from .document_store import SQLiteDocumentStore
from .entity_store import SQLiteEntityStore
from .extraction_store import SQLiteExtractionStore


class SQLiteUnitOfWork(UnitOfWork):
    """SQLite implementation of the UnitOfWork."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the UnitOfWork with a SQLite connection."""
        self._conn = conn

        # Stores will be initialized in __enter__
        self.documents: SQLiteDocumentStore
        self.entities: SQLiteEntityStore
        self.extraction: SQLiteExtractionStore

    def __enter__(self) -> Self:
        """Enter the runtime context related to an SQLite transaction."""
        self._conn.execute('BEGIN')
        self.documents = SQLiteDocumentStore(self._conn)
        self.entities = SQLiteEntityStore(self._conn)
        self.extraction = SQLiteExtractionStore(self._conn)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the runtime context and handle commit or rollback."""
        if exc:
            self.rollback()
        else:
            self.commit()

    def commit(self) -> None:
        """Commit the staged changes to the underlying stores."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback any staged changes in case of an error."""
        self._conn.rollback()
