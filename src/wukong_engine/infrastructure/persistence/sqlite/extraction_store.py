import sqlite3

from wukong_engine.app.staging.ports import ExtractionStore


class SQLiteExtractionStore(ExtractionStore):
    """SQLite implementation of the ExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the extraction store with a SQLite connection."""
        self._conn = conn

    # def get_extracted_entity_types(self, document_id):
    #     cursor = self._conn.execute(
    #         """
    #         SELECT entity_type
    #         FROM extracted_entity_types
    #         WHERE document_id = ?
    #         """,
    #         (document_id,),
    #     )
    #     return {row[0] for row in cursor}

    # def link_entities_to_document(self, document_id, entity_ids):
    #     self._conn.executemany(
    #         """
    #         INSERT OR IGNORE INTO extracted_entities (entity_id, document_id)
    #         VALUES (?, ?)
    #         """,
    #         [(eid, document_id) for eid in entity_ids],
    #     )

    # def mark_entity_type_extracted(self, document_id, entity_type):
    #     self._conn.execute(
    #         """
    #         INSERT OR IGNORE INTO extracted_entity_types (document_id, entity_type)
    #         VALUES (?, ?)
    #         """,
    #         (document_id, entity_type),
    #     )

    # def get_entity_document_pairs(self):
    #     cursor = self._conn.execute(
    #         """
    #         SELECT entity_id, document_id
    #         FROM extracted_entities
    #         """,
    #     )
    #     yield from cursor

    def clear(self) -> None:
        """Reset extraction store."""
