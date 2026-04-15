import json
import sqlite3

from wukong_engine.app.staging.ports import EntityStore
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.elements.values import EntityId


# TODO: Implement
class SQLiteEntityStore(EntityStore):
    """SQLite-based implementation of the EntityStagingStore interface."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection."""
        self._conn = conn

    def upsert_entity(self, entity: Entity, document_id: str) -> EntityId:
        """Insert or update an entity in the staging store, linking it to the source document."""
        cursor = self._conn.cursor()

        # Try insert
        try:
            cursor.execute(
                """
                INSERT INTO entities (entity_id, content_id, entity_type, version, properties)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entity.id.instance,
                    entity.id.content,
                    entity.type.name,
                    json.dumps(entity.properties),
                ),
            )
            entity_id = entity.id

        except sqlite3.IntegrityError:
            # Duplicate content_id → fetch existing
            cursor.execute(
                'SELECT entity_id, properties FROM entities WHERE content_id = ?',
                (entity.id.content,),
            )
            row = cursor.fetchone()

            existing_id = EntityId.from_string(row[0])
            existing_props = json.loads(row[1])

            # Merge strategy (you define this)
            merged_props = self._merge(existing_props, entity.properties)

            cursor.execute(
                """
                UPDATE entities
                SET properties = ?
                WHERE entity_id = ?
                """,
                (json.dumps(merged_props), row[0]),
            )

            entity_id = existing_id

        # Link to document (idempotent)
        cursor.execute(
            """
            INSERT OR IGNORE INTO entity_documents (entity_id, document_id)
            VALUES (?, ?)
            """,
            (entity_id.instance, document_id),
        )

        return entity_id

    def _merge(self, existing: dict, incoming: dict) -> dict:
        # Define policy:
        # - overwrite?
        # - keep first?
        # - union lists?
        return {**existing, **incoming}
