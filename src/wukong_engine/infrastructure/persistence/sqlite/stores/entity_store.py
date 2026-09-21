"""SQLite-backed entity store implementation."""

import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Iterator

from wukong_engine.app.shared.iterables import batched
from wukong_engine.app.staging.ports import EntityStore
from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import ContextLevel, DocumentCollectionName
from wukong_engine.core.knowledge.elements import ChunkEntityProvenance, DocumentEntityProvenance, Entity
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model import EntityType, KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName
from wukong_engine.core.knowledge.services import EntityMerger
from wukong_engine.core.shared.identity import ContentHash, InstanceId


class SQLiteEntityStore(EntityStore):
    """SQLite implementation of the EntityStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection."""
        self._conn = conn
        self._merger = EntityMerger()

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
        # If no entities are provided, no duplicates can exist
        if not entities:
            return {}

        # Build a mapping of content_id bytes to Entity for quick lookup
        entities_by_id = {entity.id.content.bytes: entity for entity in entities}
        result: dict[bytes, Entity] = {}
        for batch in batched(entities_by_id.keys(), 500):
            placeholders = ','.join('?' for _ in batch)
            query = f"""
                SELECT content_id, instance_id, properties
                FROM entities
                WHERE content_id IN ({placeholders})
            """  # noqa: S608
            rows = self._conn.execute(query, batch)
            for row in rows:
                row_type = entities_by_id[row['content_id']].type
                entity = self._row_to_entity(row, entity_type=row_type)
                result[entity.id.content.bytes] = entity

        return result

    def _bulk_insert_entities(self, entities: Iterable[Entity]) -> None:
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

    def add_entity_types(self, entity_type_names: Iterable[EntityTypeName]) -> None:
        """Add entity types."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO entity_types (entity_type_name)
            VALUES (?)
            """,
            [(et_name.value,) for et_name in entity_type_names],
        )

    def link_collections_to_entity_type(
        self,
        collection_names: Iterable[DocumentCollectionName],
        entity_type_name: EntityTypeName,
        context_level: ContextLevel,
    ) -> None:
        """Link a set of document collections to an entity type under a specific context level."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO entity_type_collections (context_level, entity_type_name, collection_name)
            VALUES (?, ?, ?)
            """,
            [(context_level.value, entity_type_name.value, c_name.value) for c_name in collection_names],
        )

    def bulk_upsert_entities(self, entities: Iterable[Entity]) -> None:
        """Insert or update a batch of entities, ensuring deduplication."""
        # Deduplicate batch of entities locally first
        grouped_entities: dict[bytes, list[Entity]] = defaultdict(list)
        for entity in entities:
            grouped_entities[entity.id.content.bytes].append(entity)
        unique_entities: list[Entity] = []
        for group in grouped_entities.values():
            merged = group[0]
            for other in group[1:]:
                merged = self._merger.merge(merged, other)
            unique_entities.append(merged)

        # Find duplicates in the database and determine which new entities to insert vs update
        existing_entities_by_id = self._find_duplicates(unique_entities)
        to_insert: list[Entity] = []
        to_update: list[Entity] = []
        for entity in unique_entities:
            entity_id = entity.id.content.bytes
            if entity_id in existing_entities_by_id:
                existing = existing_entities_by_id[entity_id]
                merged = self._merger.merge(existing, entity)
                if merged.properties != existing.properties:
                    to_update.append(merged)
            else:
                to_insert.append(entity)

        # Perform bulk insert and update
        self._bulk_insert_entities(to_insert)
        self._bulk_update_properties(to_update)

    def link_entities_to_source_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link a batch of entities to their source context."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO entity_provenance (context_level, context_content_id, entity_content_id)
            VALUES (?, ?, ?)
            """,
            [(context.level.value, context.content_id.bytes, entity.id.content.bytes) for entity in entities],
        )

    def stream_by_entity_type(self, entity_type: EntityType) -> Iterator[Entity]:
        """Stream all entities of a given type."""
        rows = self._conn.execute(
            'SELECT content_id, instance_id, properties FROM entities WHERE entity_type_name = ? ORDER BY content_id',
            (entity_type.name.value,),
        )
        for row in rows:
            yield self._row_to_entity(row, entity_type)

    def stream_by_source_context(self, context: ContextRef, model: KnowledgeModel) -> Iterator[Entity]:
        """Stream all entities linked to a specific source context."""
        rows = self._conn.execute(
            """
            SELECT e.content_id, e.instance_id, e.entity_type_name, e.properties
            FROM entity_provenance ep
            JOIN entities e ON e.content_id = ep.entity_content_id
            WHERE ep.context_level = ? AND ep.context_content_id = ?
            ORDER BY e.content_id
            """,
            (context.level.value, context.content_id.bytes),
        )
        for row in rows:
            entity_type_name = EntityTypeName(row['entity_type_name'])
            entity_type = model.entity_type(entity_type_name)
            if entity_type is None:
                raise ValueError(f'Entity type "{entity_type_name.value}" not found in the provided knowledge model.')
            yield self._row_to_entity(row, entity_type)

    def stream_provenance_by_document(self) -> Iterator[DocumentEntityProvenance]:
        """Stream all links of extracted entities and their source documents, grouped by document."""
        rows = self._conn.execute(
            """
            SELECT d.content_id AS document_content_id, d.instance_id AS document_instance_id,
                   e.content_id AS entity_content_id, e.instance_id AS entity_instance_id, e.entity_type_name AS entity_type_name
            FROM entity_provenance ep
            JOIN documents d ON d.content_id = ep.context_content_id
            JOIN entities e ON e.content_id = ep.entity_content_id
            WHERE ep.context_level = ?
            ORDER BY ep.context_content_id, ep.entity_content_id
            """,
            (ContextLevel.DOCUMENT.value,),
        )

        # Track the current document and its associated entity info to group them together
        current_document_id: DocumentId | None = None
        current_entity_ids: list[EntityId] = []
        current_entity_types: list[EntityTypeName] = []

        # Iterate through the rows and yield provenance objects when the document changes
        for row in rows:
            document_id = DocumentId.from_components(
                instance=InstanceId.from_bytes(row['document_instance_id']),
                content=ContentHash.from_bytes(row['document_content_id']),
            )
            entity_id = EntityId.from_components(
                instance=InstanceId.from_bytes(row['entity_instance_id']),
                content=ContentHash.from_bytes(row['entity_content_id']),
            )
            entity_type_name = EntityTypeName(row['entity_type_name'])

            # If this is the first row, initialize the current document ID
            if current_document_id is None:
                current_document_id = document_id

            # If the document ID has changed, yield the current provenance and reset for the new document
            if document_id != current_document_id:
                yield DocumentEntityProvenance(
                    document_id=current_document_id,
                    entity_ids=tuple(current_entity_ids),
                    entity_types=tuple(current_entity_types),
                )
                current_document_id = document_id
                current_entity_ids = []
                current_entity_types = []

            # Accumulate entity info for the current document
            current_entity_ids.append(entity_id)
            current_entity_types.append(entity_type_name)

        # After the loop, yield any remaining provenance for the last document
        if current_document_id is not None:
            yield DocumentEntityProvenance(
                document_id=current_document_id,
                entity_ids=tuple(current_entity_ids),
                entity_types=tuple(current_entity_types),
            )

    def stream_provenance_by_chunk(self) -> Iterator[ChunkEntityProvenance]:
        """Stream all links of extracted entities and their source chunks, grouped by chunk."""
        rows = self._conn.execute(
            """
            SELECT c.content_id AS chunk_content_id, c.instance_id AS chunk_instance_id,
                   d.content_id AS document_content_id, d.instance_id AS document_instance_id,
                   e.content_id AS entity_content_id, e.instance_id AS entity_instance_id, e.entity_type_name AS entity_type_name
            FROM entity_provenance ep
            JOIN chunks c ON c.content_id = ep.context_content_id
            JOIN documents d ON d.content_id = c.document_content_id
            JOIN entities e ON e.content_id = ep.entity_content_id
            WHERE ep.context_level = ?
            ORDER BY c.document_content_id, c.chunk_index, ep.entity_content_id
            """,
            (ContextLevel.CHUNK.value,),
        )

        # Track the current chunk and its associated entity info to group them together
        current_chunk_id: ChunkId | None = None
        current_document_id: DocumentId | None = None
        current_entity_ids: list[EntityId] = []
        current_entity_types: list[EntityTypeName] = []

        # Iterate through the rows and yield provenance objects when the chunk changes
        for row in rows:
            chunk_id = ChunkId.from_components(
                instance=InstanceId.from_bytes(row['chunk_instance_id']),
                content=ContentHash.from_bytes(row['chunk_content_id']),
            )
            document_id = DocumentId.from_components(
                instance=InstanceId.from_bytes(row['document_instance_id']),
                content=ContentHash.from_bytes(row['document_content_id']),
            )
            entity_id = EntityId.from_components(
                instance=InstanceId.from_bytes(row['entity_instance_id']),
                content=ContentHash.from_bytes(row['entity_content_id']),
            )
            entity_type_name = EntityTypeName(row['entity_type_name'])

            # If this is the first row, initialize the current chunk
            if current_chunk_id is None or current_document_id is None:
                current_chunk_id = chunk_id
                current_document_id = document_id

            # If the chunk has changed, yield the current provenance and reset for the new chunk
            if chunk_id != current_chunk_id:
                yield ChunkEntityProvenance(
                    chunk_id=current_chunk_id,
                    parent_document_id=current_document_id,
                    entity_ids=tuple(current_entity_ids),
                    entity_types=tuple(current_entity_types),
                )
                current_chunk_id = chunk_id
                current_document_id = document_id
                current_entity_ids = []
                current_entity_types = []

            # Accumulate entity info for the current chunk
            current_entity_ids.append(entity_id)
            current_entity_types.append(entity_type_name)

        # After the loop, yield any remaining provenance for the last chunk
        if current_chunk_id is not None and current_document_id is not None:
            yield ChunkEntityProvenance(
                chunk_id=current_chunk_id,
                parent_document_id=current_document_id,
                entity_ids=tuple(current_entity_ids),
                entity_types=tuple(current_entity_types),
            )

    def count_entities(self, context_level: ContextLevel) -> int:
        """Count the number of unique entities for a given context level."""
        row = self._conn.execute(
            """
            SELECT COUNT(DISTINCT entity_content_id) AS count
            FROM entity_provenance
            WHERE context_level = ?
            """,
            (context_level.value,),
        ).fetchone()
        return int(row['count']) if row else 0

    def count_entity_mentions(self, context_level: ContextLevel) -> int:
        """Count the number of entity mentions for a given context level."""
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM entity_provenance
            WHERE context_level = ?
            """,
            (context_level.value,),
        ).fetchone()
        return int(row['count']) if row else 0

    def clear(self) -> None:
        """Reset the entity store."""
        self._conn.execute('DELETE FROM entity_provenance')
        self._conn.execute('DELETE FROM entities')
        self._conn.execute('DELETE FROM entity_type_collections')
        self._conn.execute('DELETE FROM entity_types')
