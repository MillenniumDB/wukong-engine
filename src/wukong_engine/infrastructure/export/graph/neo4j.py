"""Provides the Neo4jKnowledgeExporter class."""

import csv
import logging
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.knowledge_export.services import KnowledgeRepository
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.model import EntityType, GraphModel
from wukong_engine.core.graph.model.values import DataType
from wukong_engine.infrastructure.serialization import EscapedStringSerializer, PropertyValueSerializer

# Logging
logger = logging.getLogger(__name__)

# Neo4j type mapping
TYPE_MAPPING = {
    DataType.STRING: 'string',
}


# Writers
class Neo4jWriter:
    """Base class for writing to a CSV file in the Neo4j format."""

    def __init__(self, path: Path) -> None:
        """Initialize the writer."""
        self._path = path
        self._serializer = PropertyValueSerializer(EscapedStringSerializer())

    def __enter__(self) -> Self:
        """Open the CSV file and write the header."""
        self._file = self._path.open('w', newline='', encoding='utf-8')
        self._writer = csv.writer(self._file, quoting=csv.QUOTE_MINIMAL)
        self._write_header()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the CSV file."""
        self._file.close()

    def _serialize_value(self, value: Any) -> str:
        """Serialize a value for CSV writing."""
        serialized_value = self._serializer.serialize(value)
        if serialized_value is None:  # If the value is None, return an empty string for CSV compatibility
            return ''
        return serialized_value

    @staticmethod
    def _to_neo4j_type(data_type: DataType) -> str:
        """Map a DataType to its corresponding Neo4j type."""
        return TYPE_MAPPING.get(data_type, 'string')  # Default to string if not found

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        raise NotImplementedError('Subclasses must implement this method.')

    def _serialize(self, obj: Any) -> list[str]:
        """Serialize an object to a list of strings for CSV writing."""
        raise NotImplementedError('Subclasses must implement this method.')

    def write(self, obj: Any) -> None:
        """Write an object to the CSV file."""
        self._writer.writerow(self._serialize(obj))


class Neo4jDocumentWriter(Neo4jWriter):
    """Writes documents to a CSV file in the Neo4j format."""

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Instance ID (main ID), Content ID
        header = ['_id:ID(Document)', '_content_id:string']

        # Fields
        header.append('source_uri:string')

        # Write the header
        self._writer.writerow(header)

    def _serialize(self, document: Document) -> list[str]:
        """Serialize a document to a list of strings for CSV writing."""
        # Instance ID (main ID), Content ID
        row = [document.id.instance.hex, document.id.content.hex]

        # Properties
        row.append(document.source_uri)  # Source URI does not require serialization

        return row

    def write(self, document: Document) -> None:
        """Write a document to the CSV file."""
        self._writer.writerow(self._serialize(document))


class Neo4jChunkWriter(Neo4jWriter):
    """Writes chunks to a CSV file in the Neo4j format."""

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Instance ID (main ID), Content ID, Identity Version
        header = ['_id:ID(Chunk)', '_content_id:string', '_id_version:string']

        # Fields
        header.extend(['chunk_index:int', 'start_offset:int', 'end_offset:int', 'content:string'])

        # Write the header
        self._writer.writerow(header)

    def _serialize(self, chunk: Chunk) -> list[str]:
        """Serialize a chunk to a list of strings for CSV writing."""
        # Instance ID (main ID), Content ID, Identity Version
        row = [chunk.id.instance.hex, chunk.id.content.hex, chunk.id.VERSION]

        # Properties
        property_values = [chunk.chunk_index, chunk.start_offset, chunk.end_offset, chunk.content]
        row.extend([self._serialize_value(value) for value in property_values])

        return row

    def write(self, chunk: Chunk) -> None:
        """Write a chunk to the CSV file."""
        self._writer.writerow(self._serialize(chunk))


class Neo4jEntityWriter(Neo4jWriter):
    """Writes entities of a specific type to a CSV file in the Neo4j format."""

    def __init__(self, path: Path, entity_type: EntityType) -> None:
        """Initialize the writer."""
        super().__init__(path)
        self._entity_type = entity_type

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Instance ID (main ID), Content ID, Identity Version
        header = [f'_id:ID({self._entity_type.name})', '_content_id:string', '_id_version:string']

        # Fields
        header.extend(
            [f'{field.name}:{self._to_neo4j_type(field.data_type)}' for field in self._entity_type.fields.values()],
        )

        # Write the header
        self._writer.writerow(header)

    def _serialize(self, entity: Entity) -> list[str]:
        """Serialize an entity to a list of strings for CSV writing."""
        # Instance ID (main ID), Content ID, Identity Version
        row = [entity.id.instance.hex, entity.id.content.hex, entity.id.VERSION]

        # Properties
        for field in self._entity_type.fields.values():
            value = entity.full_properties.get(field)
            row.append(self._serialize_value(value))

        return row

    def write(self, entity: Entity) -> None:
        """Write an entity to the CSV file."""
        self._writer.writerow(self._serialize(entity))


# TODO: Relationships
# TODO: Special Relationships: ChunkOf (use chunks again with a special writer)
# TODO: Special Relationships: ExtractedFrom
# TODO: ExtractedFrom for relationships
# Exporters
class Neo4jKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to the Neo4j graph database format."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        """Initialize the exporter with necessary dependencies."""
        self._repository = repository

    def export(self, model: GraphModel, export_uri: str) -> None:
        """Export knowledge as a graph to a set of Neo4j CSV files."""
        # Setup export directories
        base_export_dir = Path(export_uri).resolve() / 'neo4j'
        base_export_dir.mkdir(parents=True, exist_ok=True)
        entities_dir = base_export_dir / 'entities'
        entities_dir.mkdir(parents=True, exist_ok=True)
        relationships_dir = base_export_dir / 'relationships'
        relationships_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f'Exporting knowledge to Neo4j CSV files at: {base_export_dir}')

        # Export sources
        self._export_sources(base_export_dir)

        # Export entities
        self._export_entities(model, entities_dir)

        # TODO: Export relationships

        # TODO: Export provenance

    def _export_sources(self, export_dir: Path) -> None:
        """Export sources to a set of Neo4j CSV files."""
        # Documents
        logger.info('Exporting Documents...')
        docs_file_path = export_dir / 'entities' / 'Document.csv'
        with Neo4jDocumentWriter(docs_file_path) as writer:
            for doc in self._repository.stream_all_documents():
                writer.write(doc)

        # Chunks
        logger.info('Exporting Chunks...')
        chunks_file_path = export_dir / 'entities' / 'Chunk.csv'
        with Neo4jChunkWriter(chunks_file_path) as writer:
            for chunk in self._repository.stream_all_chunks():
                writer.write(chunk)

    def _export_entities(self, model: GraphModel, entities_dir: Path) -> None:
        """Export entities to a set of Neo4j CSV files."""
        for entity_type in model.active_entity_types.values():
            logger.info(f'Exporting "{entity_type.name}" entities...')
            entity_type_file_path = entities_dir / f'{entity_type.name}.csv'
            with Neo4jEntityWriter(entity_type_file_path, entity_type) as writer:
                for entity in self._repository.stream_entities_by_type(entity_type):
                    writer.write(entity)
