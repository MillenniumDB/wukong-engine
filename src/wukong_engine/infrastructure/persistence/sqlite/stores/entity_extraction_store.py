import sqlite3
from collections.abc import Iterable, Iterator

from wukong_engine.app.staging.ports import EntityExtractionStore
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.extraction.elements.values import ExtractionStatus
from wukong_engine.core.graph.elements import DocumentEntityTypes, Entity, EntityDocumentLink
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId


# TODO: ContextLevel usage when dealing with context level materialization (needs Chunk first)
class SQLiteEntityExtractionStore(EntityExtractionStore):
    """SQLite implementation of the EntityExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the entity extraction store with a SQLite connection."""
        self._conn = conn

    def _row_to_entity_document_link(self, row: sqlite3.Row) -> EntityDocumentLink:
        """Map a database row to an EntityDocumentLink object."""
        return EntityDocumentLink(
            entity_id=EntityId.from_components(
                instance=InstanceId.from_bytes(row['entity_instance_id']),
                content=ContentHash.from_bytes(row['entity_content_id']),
            ),
            document_id=DocumentId.from_components(
                instance=InstanceId.from_bytes(row['document_instance_id']),
                content=ContentHash.from_bytes(row['document_content_id']),
            ),
        )

    def materialize_pending_extractions(self) -> None:
        """Generate pending entity type extractions from documents."""
        self._conn.execute(
            f"""
            INSERT OR IGNORE INTO entity_type_extractions (
                document_content_id,
                entity_type_name,
                extraction_status
            )
            SELECT
                dc.document_content_id,
                etc.entity_type_name,
                {ExtractionStatus.PENDING.value!r}
            FROM document_collections dc
            JOIN entity_type_collections etc ON etc.collection_name = dc.collection_name
            """,  # noqa: S608
        )

    def link_extracted_entities_to_document(self, entities: Iterable[Entity], document: Document) -> None:
        """Link extracted entities to their source document."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO extracted_entities (document_content_id, entity_content_id)
            VALUES (?, ?)
            """,
            [(document.id.content.bytes, entity.id.content.bytes) for entity in entities],
        )

    def mark_completed_extractions_from_document(
        self,
        entity_types: Iterable[EntityTypeName],
        document: Document,
    ) -> None:
        """Mark completed entity type extractions from a source document."""
        self._conn.executemany(
            f"""
            UPDATE entity_type_extractions
            SET
                extraction_status = ?
            WHERE
                document_content_id = ?
                AND entity_type_name = ?
                AND extraction_status = {ExtractionStatus.PENDING.value!r}
            """,  # noqa: S608
            [
                (ExtractionStatus.COMPLETED.value, document.id.content.bytes, entity_type.value)
                for entity_type in entity_types
            ],
        )

    def stream_pending_extractions(self) -> Iterator[DocumentEntityTypes]:
        """Stream documents with their pending entity types for extraction."""
        cursor = self._conn.execute(
            f"""
            SELECT
                d.content_id AS document_content_id,
                d.instance_id AS document_instance_id,
                d.source_uri AS source_uri,
                ete.entity_type_name AS entity_type_name
            FROM entity_type_extractions ete
            JOIN documents d ON d.content_id = ete.document_content_id
            WHERE ete.extraction_status = {ExtractionStatus.PENDING.value!r}
            ORDER BY ete.document_content_id
            """,  # noqa: S608
        )

        current_document: Document | None = None
        current_entity_types: list[EntityTypeName] = []

        for row in cursor:
            document_content_id = row['document_content_id']

            if current_document is not None and document_content_id != current_document.id.content.bytes:
                yield DocumentEntityTypes(
                    document=current_document,
                    entity_types=tuple(current_entity_types),
                )
                current_entity_types = []

            if current_document is None or document_content_id != current_document.id.content.bytes:
                current_document = Document(
                    id=DocumentId.from_components(
                        instance=InstanceId.from_bytes(row['document_instance_id']),
                        content=ContentHash.from_bytes(row['document_content_id']),
                    ),
                    source_uri=row['source_uri'],
                )

            current_entity_types.append(EntityTypeName(row['entity_type_name']))

        if current_document is not None:
            yield DocumentEntityTypes(
                document=current_document,
                entity_types=tuple(current_entity_types),
            )

    def stream_entity_document_links(self) -> Iterator[EntityDocumentLink]:
        """Stream all links of extracted entities and their source documents."""
        cursor = self._conn.execute(
            """
            SELECT e.content_id AS entity_content_id, e.instance_id AS entity_instance_id,
                   d.content_id AS document_content_id, d.instance_id AS document_instance_id
            FROM extracted_entities ee
            JOIN entities e ON e.content_id = ee.entity_content_id
            JOIN documents d ON d.content_id = ee.document_content_id
            """,
        )
        for row in cursor:
            yield self._row_to_entity_document_link(row)

    def clear(self) -> None:
        """Reset the entity extraction store."""
        self._conn.execute('DELETE FROM extracted_entities')
        self._conn.execute('DELETE FROM entity_type_extractions')
