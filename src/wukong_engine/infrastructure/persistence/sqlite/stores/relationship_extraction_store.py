import sqlite3

from wukong_engine.app.staging.ports import RelationshipExtractionStore


# TODO: Implement
# TODO: Indexes
# TODO: Test
class SQLiteRelationshipExtractionStore(RelationshipExtractionStore):
    """SQLite implementation of the RelationshipExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the relationship extraction store with a SQLite connection."""
        self._conn = conn

    def clear(self) -> None:
        """Reset the relationship extraction store."""
