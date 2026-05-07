import sqlite3

from wukong_engine.app.staging.ports import RelationshipStore


# TODO: Implement
# TODO: Indexes
# TODO: Test
class SQLiteRelationshipStore(RelationshipStore):
    """SQLite implementation of the RelationshipStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the relationship store with a SQLite connection."""
        self._conn = conn

    def clear(self) -> None:
        """Reset the relationship store."""
