"""SQLite-backed extraction store combining entity and relationship extraction state."""

import sqlite3
from collections import Counter
from collections.abc import Iterable

from wukong_engine.app.data_extraction.elements import ExtractionJob, Rejection
from wukong_engine.app.staging.ports import ExtractionStore

from .entity_extraction_store import SQLiteEntityExtractionStore
from .relationship_extraction_store import SQLiteRelationshipExtractionStore


class SQLiteExtractionStore(ExtractionStore):
    """SQLite implementation of the ExtractionStore.

    Attributes:
        entities: Store for entity extraction state.
        relationships: Store for relationship extraction state.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the extraction store with a SQLite connection.

        Args:
            conn: Open SQLite connection used for all queries.
        """
        self._conn = conn
        self.entities = SQLiteEntityExtractionStore(conn)
        self.relationships = SQLiteRelationshipExtractionStore(conn)

    def record_rejections(self, job: ExtractionJob, rejections: Iterable[Rejection]) -> None:
        """Record what was rejected while materializing a job's results, counted per scope, reason, type and field.

        Args:
            job: Job whose results were materialized.
            rejections: Objects discarded and values unset while materializing them.
        """
        counts = Counter((r.scope.value, r.reason.value, r.type_name, r.field_name) for r in rejections)
        self._conn.executemany(
            """
            INSERT INTO extraction_rejections (
                job_id,
                rejection_scope,
                rejection_reason,
                type_name,
                field_name,
                rejection_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(job.id.instance.bytes, *key, count) for key, count in counts.items()],
        )

    def clear(self) -> None:
        """Reset the extraction store."""
        self.relationships.clear()
        self.entities.clear()
