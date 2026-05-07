import sqlite3

from wukong_engine.app.staging.ports import ExtractionStore

from .entity_extraction_store import SQLiteEntityExtractionStore
from .relationship_extraction_store import SQLiteRelationshipExtractionStore


class SQLiteExtractionStore(ExtractionStore):
    """SQLite implementation of the ExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the extraction store with a SQLite connection."""
        self._conn = conn
        self.entities = SQLiteEntityExtractionStore(conn)
        self.relationships = SQLiteRelationshipExtractionStore(conn)

    def clear(self) -> None:
        """Reset the extraction store."""
        self.relationships.clear()
        self.entities.clear()
