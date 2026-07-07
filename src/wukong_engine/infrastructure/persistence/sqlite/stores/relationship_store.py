import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Iterator

from wukong_engine.app.shared.iterables import batched
from wukong_engine.app.staging.ports import RelationshipStore
from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.graph.elements import ChunkRelationshipProvenance, Relationship
from wukong_engine.core.graph.elements.values import EntityId, RelationshipId
from wukong_engine.core.graph.model import RelationshipType
from wukong_engine.core.graph.model.values import RelationshipTypeName
from wukong_engine.core.graph.services import RelationshipMerger
from wukong_engine.core.shared.identity import ContentHash, InstanceId


class SQLiteRelationshipStore(RelationshipStore):
    """SQLite implementation of the RelationshipStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the relationship store with a SQLite connection."""
        self._conn = conn
        self._merger = RelationshipMerger()

    def _row_to_relationship(self, row: sqlite3.Row, relationship_type: RelationshipType) -> Relationship:
        """Map a database row to a Relationship object."""
        return Relationship(
            id=RelationshipId.from_components(
                instance=InstanceId.from_bytes(row['instance_id']),
                content=ContentHash.from_bytes(row['content_id']),
            ),
            type=relationship_type,
            source=EntityId.from_components(
                instance=InstanceId.from_bytes(row['source_instance_id']),
                content=ContentHash.from_bytes(row['source_content_id']),
            ),
            target=EntityId.from_components(
                instance=InstanceId.from_bytes(row['target_instance_id']),
                content=ContentHash.from_bytes(row['target_content_id']),
            ),
            properties=json.loads(row['properties']),
        )

    def _find_duplicates(self, relationships: Iterable[Relationship]) -> dict[bytes, Relationship]:
        """Find existing relationships that match the content of the given relationships."""
        # If no relationships are provided, no duplicates can exist
        if not relationships:
            return {}

        # Build a mapping of content_id bytes to Relationship for quick lookup
        relationships_by_id = {relationship.id.content.bytes: relationship for relationship in relationships}
        result: dict[bytes, Relationship] = {}
        for batch in batched(relationships_by_id.keys(), 500):
            placeholders = ','.join('?' for _ in batch)
            query = f"""
                SELECT
                    r.content_id AS content_id,
                    r.instance_id AS instance_id,
                    r.properties AS properties,
                    s.instance_id AS source_instance_id,
                    s.content_id AS source_content_id,
                    t.instance_id AS target_instance_id,
                    t.content_id AS target_content_id
                FROM relationships r
                JOIN entities s ON r.source_content_id = s.content_id
                JOIN entities t ON r.target_content_id = t.content_id
                WHERE r.content_id IN ({placeholders})
            """  # noqa: S608
            rows = self._conn.execute(query, batch)
            for row in rows:
                row_type = relationships_by_id[row['content_id']].type
                relationship = self._row_to_relationship(row, relationship_type=row_type)
                result[relationship.id.content.bytes] = relationship

        return result

    def _bulk_insert_relationships(self, relationships: Iterable[Relationship]) -> None:
        """Insert a batch of new unique relationships."""
        self._conn.executemany(
            """
            INSERT INTO relationships (content_id, instance_id, relationship_type_name, source_content_id, target_content_id, properties)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    relationship.id.content.bytes,
                    relationship.id.instance.bytes,
                    relationship.type.name.value,
                    relationship.source.content.bytes,
                    relationship.target.content.bytes,
                    json.dumps(relationship.properties, sort_keys=True, separators=(',', ':')),
                )
                for relationship in relationships
            ],
        )

    def _bulk_update_properties(self, relationships: Iterable[Relationship]) -> None:
        """Update properties for a batch of existing relationships."""
        self._conn.executemany(
            """
            UPDATE relationships
            SET properties = ?
            WHERE content_id = ?
            """,
            [
                (
                    json.dumps(relationship.properties, sort_keys=True, separators=(',', ':')),
                    relationship.id.content.bytes,
                )
                for relationship in relationships
            ],
        )

    def add_relationship_types(self, relationship_types: Iterable[RelationshipType]) -> None:
        """Add relationship types and their endpoints."""
        # Add relationship types
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO relationship_types (relationship_type_name)
            VALUES (?)
            """,
            [(rt.name.value,) for rt in relationship_types],
        )

        # Add relationship type endpoints
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO relationship_type_endpoints (
                relationship_type_name,
                source_entity_type_name,
                target_entity_type_name,
                source_context_level,
                target_context_level
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    rt.name.value,
                    endpoint.source.value,
                    endpoint.target.value,
                    pair.source_level.value,
                    pair.target_level.value,
                )
                for rt in relationship_types
                for endpoint in rt.endpoints
                for pair in endpoint.context_pairs
            ],
        )

    def bulk_upsert_relationships(self, relationships: Iterable[Relationship]) -> None:
        """Insert or update a batch of relationships, ensuring deduplication."""
        # Deduplicate batch of relationships locally first
        grouped_relationships: dict[bytes, list[Relationship]] = defaultdict(list)
        for relationship in relationships:
            grouped_relationships[relationship.id.content.bytes].append(relationship)
        unique_relationships: list[Relationship] = []
        for group in grouped_relationships.values():
            merged = group[0]
            for other in group[1:]:
                merged = self._merger.merge(merged, other)
            unique_relationships.append(merged)

        # Find duplicates in the database and determine which new relationships to insert vs update
        existing_relationships_by_id = self._find_duplicates(unique_relationships)
        to_insert: list[Relationship] = []
        to_update: list[Relationship] = []
        for relationship in unique_relationships:
            relationship_id = relationship.id.content.bytes
            if relationship_id in existing_relationships_by_id:
                existing = existing_relationships_by_id[relationship_id]
                merged = self._merger.merge(existing, relationship)
                if merged.properties != existing.properties:
                    to_update.append(merged)
            else:
                to_insert.append(relationship)

        # Perform bulk insert and update
        self._bulk_insert_relationships(to_insert)
        self._bulk_update_properties(to_update)

    def link_relationships_to_source_context(self, relationships: Iterable[Relationship], context: ContextRef) -> None:
        """Link a batch of relationships to their source context."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO relationship_provenance (chunk_content_id, relationship_content_id)
            VALUES (?, ?)
            """,
            ((context.content_id.bytes, relationship.id.content.bytes) for relationship in relationships),
        )

    def stream_by_relationship_type(self, relationship_type: RelationshipType) -> Iterator[Relationship]:
        """Stream all relationships of a given type."""
        rows = self._conn.execute(
            """
            SELECT
                r.content_id AS content_id,
                r.instance_id AS instance_id,
                r.properties AS properties,
                s.instance_id AS source_instance_id,
                s.content_id AS source_content_id,
                t.instance_id AS target_instance_id,
                t.content_id AS target_content_id
            FROM relationships r
            JOIN entities s ON r.source_content_id = s.content_id
            JOIN entities t ON r.target_content_id = t.content_id
            WHERE r.relationship_type_name = ?
            ORDER BY r.content_id
            """,
            (relationship_type.name.value,),
        )
        for row in rows:
            yield self._row_to_relationship(row, relationship_type)

    def stream_chunk_provenance(self) -> Iterator[ChunkRelationshipProvenance]:
        """Stream all links of extracted relationships and their source chunks, grouped by chunk."""
        rows = self._conn.execute(
            """
            SELECT c.content_id AS chunk_content_id, c.instance_id AS chunk_instance_id,
                   d.content_id AS document_content_id, d.instance_id AS document_instance_id,
                   r.content_id AS relationship_content_id, r.instance_id AS relationship_instance_id,
                   r.relationship_type_name AS relationship_type_name
            FROM relationship_provenance rp
            JOIN chunks c ON c.content_id = rp.chunk_content_id
            JOIN documents d ON d.content_id = c.document_content_id
            JOIN relationships r ON r.content_id = rp.relationship_content_id
            ORDER BY c.document_content_id, c.chunk_index, rp.relationship_content_id
            """,
        )

        # Track the current chunk and its associated relationship info to group them together
        current_chunk_id: ChunkId | None = None
        current_document_id: DocumentId | None = None
        current_relationship_ids: list[RelationshipId] = []
        current_relationship_types: list[RelationshipTypeName] = []

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
            relationship_id = RelationshipId.from_components(
                instance=InstanceId.from_bytes(row['relationship_instance_id']),
                content=ContentHash.from_bytes(row['relationship_content_id']),
            )
            relationship_type_name = RelationshipTypeName(row['relationship_type_name'])

            # If this is the first row, initialize the current chunk
            if current_chunk_id is None or current_document_id is None:
                current_chunk_id = chunk_id
                current_document_id = document_id

            # If the chunk has changed, yield the current provenance and reset for the new chunk
            if chunk_id != current_chunk_id:
                yield ChunkRelationshipProvenance(
                    chunk_id=current_chunk_id,
                    parent_document_id=current_document_id,
                    relationship_ids=tuple(current_relationship_ids),
                    relationship_types=tuple(current_relationship_types),
                )
                current_chunk_id = chunk_id
                current_document_id = document_id
                current_relationship_ids = []
                current_relationship_types = []

            # Accumulate relationship info for the current chunk
            current_relationship_ids.append(relationship_id)
            current_relationship_types.append(relationship_type_name)

        # After the loop, yield any remaining provenance for the last chunk
        if current_chunk_id is not None and current_document_id is not None:
            yield ChunkRelationshipProvenance(
                chunk_id=current_chunk_id,
                parent_document_id=current_document_id,
                relationship_ids=tuple(current_relationship_ids),
                relationship_types=tuple(current_relationship_types),
            )

    def count_relationships(self) -> int:
        """Count the number of unique relationships."""
        row = self._conn.execute('SELECT COUNT(*) AS count FROM relationships').fetchone()
        return int(row['count']) if row else 0

    def count_relationship_mentions(self) -> int:
        """Count the number of relationship mentions."""
        row = self._conn.execute('SELECT COUNT(*) AS count FROM relationship_provenance').fetchone()
        return int(row['count']) if row else 0

    def clear(self) -> None:
        """Reset the relationship store."""
        self._conn.execute('DELETE FROM relationship_provenance')
        self._conn.execute('DELETE FROM relationships')
        self._conn.execute('DELETE FROM relationship_type_endpoints')
        self._conn.execute('DELETE FROM relationship_types')
