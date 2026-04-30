import sqlite3

from wukong_engine.app.staging.ports import EntityExtractionStore

# TODO: link_entities_to_document(document_id, entity_ids)

# TODO: mark_completed(document_id, entity_type(s))

# TODO: stream_pending_work()
# SELECT
#     d.document_id,
#     d.source_uri,
#     GROUP_CONCAT(DISTINCT et.entity_type) AS pending_entity_types
# FROM documents d
# JOIN document_collections dc ON dc.document_id = d.document_id
# JOIN entity_type_collections etc ON etc.collection_name = dc.collection_name
# JOIN entity_types et ON et.entity_type = etc.entity_type
# LEFT JOIN extracted_entity_types eet
#     ON eet.document_id = d.document_id
#     AND eet.entity_type = et.entity_type
# WHERE eet.entity_type IS NULL
# GROUP BY d.document_id;

# SELECT
#     d.document_id,
#     d.source_uri,
#     GROUP_CONCAT(DISTINCT et.entity_type) AS pending_entity_types
# FROM documents d
# JOIN document_collections dc
#     ON dc.document_id = d.document_id
# JOIN entity_type_collections etc
#     ON etc.collection_name = dc.collection_name
# JOIN entity_types et
#     ON et.entity_type = etc.entity_type
# WHERE NOT EXISTS (
#     SELECT 1
#     FROM extracted_entity_types eet
#     WHERE eet.document_id = d.document_id
#       AND eet.entity_type = et.entity_type
# )
# GROUP BY d.document_id;

# TODO: get_entity_document_pairs()


# SELECT entity_id, document_id FROM extracted_entities;


# TODO: Implement
# TODO: Clear method, testing
class SQLiteEntityExtractionStore(EntityExtractionStore):
    """SQLite implementation of the EntityExtractionStore."""

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
