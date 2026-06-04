import sqlite3
from collections.abc import Iterable, Iterator

from wukong_engine.app.data_extraction.dtos import EntityExtractionJob
from wukong_engine.app.staging.ports import EntityExtractionStore
from wukong_engine.core.documents.elements import Chunk, ContextRef, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.elements.values import ExtractionStatus
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality
from wukong_engine.core.graph.elements import Entity, EntityChunkProvenance, EntityDocumentProvenance
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId


class SQLiteEntityExtractionStore(EntityExtractionStore):
    """SQLite implementation of the EntityExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the entity extraction store with a SQLite connection."""
        self._conn = conn

    def _row_to_entity_document_provenance(self, row: sqlite3.Row) -> EntityDocumentProvenance:
        """Map a database row to an EntityDocumentProvenance object."""
        return EntityDocumentProvenance(
            entity_id=EntityId.from_components(
                instance=InstanceId.from_bytes(row['entity_instance_id']),
                content=ContentHash.from_bytes(row['entity_content_id']),
            ),
            document_id=DocumentId.from_components(
                instance=InstanceId.from_bytes(row['document_instance_id']),
                content=ContentHash.from_bytes(row['document_content_id']),
            ),
        )

    def _row_to_entity_chunk_provenance(self, row: sqlite3.Row) -> EntityChunkProvenance:
        """Map a database row to an EntityChunkProvenance object."""
        return EntityChunkProvenance(
            entity_id=EntityId.from_components(
                instance=InstanceId.from_bytes(row['entity_instance_id']),
                content=ContentHash.from_bytes(row['entity_content_id']),
            ),
            chunk_id=ChunkId.from_components(
                instance=InstanceId.from_bytes(row['chunk_instance_id']),
                content=ContentHash.from_bytes(row['chunk_content_id']),
            ),
        )

    def materialize_pending_extractions(self, context_level: ContextLevel) -> None:
        """Generate pending entity type extractions for source contexts."""
        if context_level == ContextLevel.DOCUMENT:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO entity_type_extractions (
                    context_level,
                    context_content_id,
                    entity_type_name,
                    extraction_status
                )
                SELECT
                    ?,
                    dc.document_content_id,
                    etc.entity_type_name,
                    ?
                FROM document_collections dc
                JOIN entity_type_collections etc ON etc.collection_name = dc.collection_name
                WHERE etc.context_level = ?
                """,
                (ContextLevel.DOCUMENT.value, ExtractionStatus.PENDING.value, ContextLevel.DOCUMENT.value),
            )
        elif context_level == ContextLevel.CHUNK:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO entity_type_extractions (
                    context_level,
                    context_content_id,
                    entity_type_name,
                    extraction_status
                )
                SELECT
                    ?,
                    c.content_id,
                    etc.entity_type_name,
                    ?
                FROM chunks c
                JOIN document_collections dc ON dc.document_content_id = c.document_content_id
                JOIN entity_type_collections etc ON etc.collection_name = dc.collection_name
                WHERE etc.context_level = ?
                """,
                (ContextLevel.CHUNK.value, ExtractionStatus.PENDING.value, ContextLevel.CHUNK.value),
            )

    def link_extracted_entities_to_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link extracted entities to their source context."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO entity_provenance (context_level, context_content_id, entity_content_id)
            VALUES (?, ?, ?)
            """,
            [(context.level.value, context.content_id.bytes, entity.id.content.bytes) for entity in entities],
        )

    def mark_completed_extractions_from_context(
        self,
        entity_type_names: Iterable[EntityTypeName],
        context: ContextRef,
    ) -> None:
        """Mark completed entity type extractions from a source context."""
        self._conn.executemany(
            """
            UPDATE entity_type_extractions
            SET
                extraction_status = ?
            WHERE
                context_level = ?
                AND context_content_id = ?
                AND entity_type_name = ?
                AND extraction_status = ?
            """,
            [
                (
                    ExtractionStatus.COMPLETED.value,
                    context.level.value,
                    context.content_id.bytes,
                    et_name.value,
                    ExtractionStatus.PENDING.value,
                )
                for et_name in entity_type_names
            ],
        )

    def stream_pending_document_extractions(self) -> Iterator[EntityExtractionJob]:
        """Stream source documents with their pending entity types for extraction."""
        cursor = self._conn.execute(
            """
            SELECT
                d.content_id AS document_content_id,
                d.instance_id AS document_instance_id,
                d.source_uri AS source_uri,
                ete.entity_type_name AS entity_type_name
            FROM entity_type_extractions ete
            JOIN documents d ON d.content_id = ete.context_content_id
            WHERE ete.context_level = ? AND ete.extraction_status = ?
            ORDER BY ete.context_content_id, ete.entity_type_name
            """,
            (ContextLevel.DOCUMENT.value, ExtractionStatus.PENDING.value),
        )

        current_document: Document | None = None
        current_content_id: bytes | None = None
        current_entity_types: list[EntityTypeName] = []

        for row in cursor:
            document_content_id = row['document_content_id']

            if current_document is not None and document_content_id != current_content_id:
                yield EntityExtractionJob(
                    source=current_document,
                    task=EntityExtractionTask(
                        context_level=ContextLevel.DOCUMENT,
                        cardinality=Cardinality.SINGLE,
                    ),
                    entity_types=tuple(current_entity_types),
                )
                current_entity_types = []

            if current_document is None or document_content_id != current_content_id:
                current_document = Document(
                    id=DocumentId.from_components(
                        instance=InstanceId.from_bytes(row['document_instance_id']),
                        content=ContentHash.from_bytes(row['document_content_id']),
                    ),
                    source_uri=row['source_uri'],
                )
                current_content_id = document_content_id

            current_entity_types.append(EntityTypeName(row['entity_type_name']))

        if current_document is not None:
            yield EntityExtractionJob(
                source=current_document,
                task=EntityExtractionTask(
                    context_level=ContextLevel.DOCUMENT,
                    cardinality=Cardinality.SINGLE,
                ),
                entity_types=tuple(current_entity_types),
            )

    def stream_pending_chunk_extractions(self) -> Iterator[EntityExtractionJob]:
        """Stream source chunks with their pending entity types for extraction."""
        cursor = self._conn.execute(
            """
            SELECT
                c.content_id AS chunk_content_id,
                c.instance_id AS chunk_instance_id,
                d.content_id AS document_content_id,
                d.instance_id AS document_instance_id,
                c.chunk_index AS chunk_index,
                c.start_offset AS start_offset,
                c.end_offset AS end_offset,
                c.content AS content,
                ete.entity_type_name AS entity_type_name
            FROM entity_type_extractions ete
            JOIN chunks c ON c.content_id = ete.context_content_id
            JOIN documents d ON d.content_id = c.document_content_id
            WHERE ete.context_level = ? AND ete.extraction_status = ?
            ORDER BY ete.context_content_id, ete.entity_type_name
            """,
            (ContextLevel.CHUNK.value, ExtractionStatus.PENDING.value),
        )

        current_chunk: Chunk | None = None
        current_content_id: bytes | None = None
        current_entity_types: list[EntityTypeName] = []

        for row in cursor:
            chunk_content_id = row['chunk_content_id']

            if current_chunk is not None and chunk_content_id != current_content_id:
                yield EntityExtractionJob(
                    source=current_chunk,
                    task=EntityExtractionTask(
                        context_level=ContextLevel.CHUNK,
                        cardinality=Cardinality.MULTIPLE,
                    ),
                    entity_types=tuple(current_entity_types),
                )
                current_entity_types = []

            if current_chunk is None or chunk_content_id != current_content_id:
                current_chunk = Chunk(
                    id=ChunkId.from_components(
                        instance=InstanceId.from_bytes(row['chunk_instance_id']),
                        content=ContentHash.from_bytes(row['chunk_content_id']),
                    ),
                    document_id=DocumentId.from_components(
                        instance=InstanceId.from_bytes(row['document_instance_id']),
                        content=ContentHash.from_bytes(row['document_content_id']),
                    ),
                    chunk_index=row['chunk_index'],
                    start_offset=row['start_offset'],
                    end_offset=row['end_offset'],
                    content=row['content'],
                )
                current_content_id = chunk_content_id

            current_entity_types.append(EntityTypeName(row['entity_type_name']))

        if current_chunk is not None:
            yield EntityExtractionJob(
                source=current_chunk,
                task=EntityExtractionTask(
                    context_level=ContextLevel.CHUNK,
                    cardinality=Cardinality.MULTIPLE,
                ),
                entity_types=tuple(current_entity_types),
            )

    def stream_entity_document_provenance(self) -> Iterator[EntityDocumentProvenance]:
        """Stream all links of extracted entities and their source documents."""
        cursor = self._conn.execute(
            """
            SELECT e.content_id AS entity_content_id, e.instance_id AS entity_instance_id,
                   d.content_id AS document_content_id, d.instance_id AS document_instance_id
            FROM entity_provenance ee
            JOIN entities e ON e.content_id = ee.entity_content_id
            JOIN documents d ON d.content_id = ee.context_content_id
            WHERE ee.context_level = ?
            ORDER BY ee.context_content_id, ee.entity_content_id
            """,
            (ContextLevel.DOCUMENT.value,),
        )
        for row in cursor:
            yield self._row_to_entity_document_provenance(row)

    def stream_entity_chunk_provenance(self) -> Iterator[EntityChunkProvenance]:
        """Stream all links of extracted entities and their source chunks."""
        cursor = self._conn.execute(
            """
            SELECT e.content_id AS entity_content_id, e.instance_id AS entity_instance_id,
                   c.content_id AS chunk_content_id, c.instance_id AS chunk_instance_id
            FROM entity_provenance ee
            JOIN entities e ON e.content_id = ee.entity_content_id
            JOIN chunks c ON c.content_id = ee.context_content_id
            WHERE ee.context_level = ?
            ORDER BY ee.context_content_id, ee.entity_content_id
            """,
            (ContextLevel.CHUNK.value,),
        )
        for row in cursor:
            yield self._row_to_entity_chunk_provenance(row)

    def clear(self) -> None:
        """Reset the entity extraction store."""
        self._conn.execute('DELETE FROM entity_provenance')
        self._conn.execute('DELETE FROM entity_type_extractions')
