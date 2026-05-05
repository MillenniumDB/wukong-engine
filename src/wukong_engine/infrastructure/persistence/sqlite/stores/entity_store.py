import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Iterator

from wukong_engine.app.shared import batched
from wukong_engine.app.staging.ports import EntityStore
from wukong_engine.core.documents.model import DocumentCollection
from wukong_engine.core.extraction.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model.entity_type import EntityType
from wukong_engine.core.shared.identity import ContentHash, InstanceId


# TODO: Move and define _merge in Entity class from domain?
class SQLiteEntityStore(EntityStore):
    """SQLite implementation of the EntityStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection."""
        self._conn = conn

    # TODO:
    def _merge(self, existing: Entity, incoming: Entity) -> Entity:
        return incoming

    def _row_to_entity(self, row: sqlite3.Row, entity_type: EntityType) -> Entity:
        """Map a database row to an Entity object."""
        return Entity(
            id=EntityId.from_components(
                instance=InstanceId.from_bytes(row['instance_id']),
                content=ContentHash.from_bytes(row['content_id']),
            ),
            type=entity_type,
            properties=json.loads(row['properties']),
        )

    def _find_duplicates(self, entities: Iterable[Entity]) -> dict[bytes, Entity]:
        """Find existing entities that match the content of the given entities."""
        if not entities:
            return {}

        entities_by_id = {entity.id.content.bytes: entity for entity in entities}
        result: dict[bytes, Entity] = {}
        for batch in batched(entities_by_id.keys(), 500):
            placeholders = ','.join('?' for _ in batch)
            query = f"""
                SELECT content_id, instance_id, properties
                FROM entities
                WHERE content_id IN ({placeholders})
            """  # noqa: S608
            cursor = self._conn.execute(query, batch)
            for row in cursor:
                row_type = entities_by_id[row['content_id']].type
                entity = self._row_to_entity(row, entity_type=row_type)
                result[entity.id.content.bytes] = entity

        return result

    def _bulk_insert(self, entities: Iterable[Entity]) -> None:
        """Insert a batch of new unique entities."""
        self._conn.executemany(
            """
            INSERT INTO entities (content_id, instance_id, entity_type_name, properties)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    entity.id.content.bytes,
                    entity.id.instance.bytes,
                    entity.type.name.value,
                    json.dumps(entity.properties, sort_keys=True, separators=(',', ':')),
                )
                for entity in entities
            ],
        )

    def _bulk_update_properties(self, entities: Iterable[Entity]) -> None:
        """Update properties for a batch of existing entities."""
        self._conn.executemany(
            """
            UPDATE entities
            SET properties = ?
            WHERE content_id = ?
            """,
            [
                (json.dumps(entity.properties, sort_keys=True, separators=(',', ':')), entity.id.content.bytes)
                for entity in entities
            ],
        )

    def bulk_upsert(self, entities: Iterable[Entity]) -> None:
        """Insert or update a batch of entities based on their content, ensuring deduplication."""
        # Deduplicate batch of entities locally first
        grouped_entities: dict[bytes, list[Entity]] = defaultdict(list)
        for entity in entities:
            grouped_entities[entity.id.content.bytes].append(entity)
        unique_entities: list[Entity] = []
        for group in grouped_entities.values():
            merged = group[0]
            for other in group[1:]:
                merged = self._merge(merged, other)
            unique_entities.append(merged)

        # Find duplicates in the database and determine which new entities to insert vs update
        existing_entities_by_id = self._find_duplicates(unique_entities)
        to_insert = []
        to_update = []
        for entity in unique_entities:
            entity_id = entity.id.content.bytes
            if entity_id in existing_entities_by_id:
                existing = existing_entities_by_id[entity_id]
                merged = self._merge(existing, entity)
                if merged.properties != existing.properties:
                    to_update.append(merged)
            else:
                to_insert.append(entity)

        # Perform bulk insert and update
        self._bulk_insert(to_insert)
        self._bulk_update_properties(to_update)

    def add_types(self, entity_types: Iterable[EntityType]) -> None:
        """Add entity types."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO entity_types (entity_type_name)
            VALUES (?)
            """,
            [(entity_type.name.value,) for entity_type in entity_types],
        )

    def link_collections_to_type(
        self,
        collections: Iterable[DocumentCollection],
        entity_type: EntityType,
        context_level: ContextLevel,
    ) -> None:
        """Link a set of document collections to an entity type under a specific context level."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO entity_type_collections (entity_type_name, collection_name, context_level)
            VALUES (?, ?, ?)
            """,
            [(entity_type.name.value, collection.name.value, context_level.value) for collection in collections],
        )

    def stream_by_type(self, entity_type: EntityType) -> Iterator[Entity]:
        """Stream all entities of a given type."""
        cursor = self._conn.execute(
            'SELECT content_id, instance_id, properties FROM entities WHERE entity_type_name = ? ORDER BY content_id',
            (entity_type.name.value,),
        )
        for row in cursor:
            yield self._row_to_entity(row, entity_type)

    def clear(self) -> None:
        """Reset the entity store."""
        self._conn.execute('DELETE FROM entity_type_collections')
        self._conn.execute('DELETE FROM entity_types')
        self._conn.execute('DELETE FROM entities')
