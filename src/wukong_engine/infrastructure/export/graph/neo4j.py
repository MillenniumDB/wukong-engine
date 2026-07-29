"""Provides the Neo4jKnowledgeExporter class."""

import csv
import logging
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.knowledge_export.services import KnowledgeRepository
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.graph.elements import Entity, Relationship
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model import EntityType, GraphModel, RelationshipType
from wukong_engine.core.graph.model.values import DataType
from wukong_engine.infrastructure.serialization import EscapedStringSerializer, PropertyValueSerializer
from wukong_engine.infrastructure.storage.filesystem import clear_directory

# Logging
logger = logging.getLogger(__name__)

# Neo4j type mapping
TYPE_MAPPING = {
    DataType.STRING: 'string',
}


# Base Writer
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


# Entity Writers
class Neo4jEntityWriter(Neo4jWriter):
    """Writes entities of a specific type to a CSV file in the Neo4j format."""

    def __init__(self, path: Path, entity_type: EntityType) -> None:
        """Initialize the writer."""
        super().__init__(path)
        self._entity_type = entity_type

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Instance ID (main ID), Content ID, Identity Version
        header = ['_id:ID', '_content_id:string', '_id_version:string']

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


class Neo4jDocumentWriter(Neo4jWriter):
    """Writes documents to a CSV file in the Neo4j format."""

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Instance ID (main ID), Content ID
        header = ['_id:ID', '_content_id:string']

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
        header = ['_id:ID', '_content_id:string', '_id_version:string']

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


# Relationship Writers
class Neo4jRelationshipWriter(Neo4jWriter):
    """Writes relationships of a specific type to a CSV file in the Neo4j format."""

    def __init__(self, path: Path, relationship_type: RelationshipType) -> None:
        """Initialize the writer."""
        super().__init__(path)
        self._relationship_type = relationship_type

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Endpoint: Source ID, Target ID
        header = [':START_ID', ':END_ID']

        # Identity: Instance ID (main ID), Content ID, Identity Policy, Identity Version
        header.extend(['_id:string', '_content_id:string', '_id_policy:string', '_id_version:string'])

        # Provenance: Chunk IDs (multiple)
        header.append('_provenance_chunk_ids:string[]')

        # Fields
        header.extend(
            [
                f'{field.name}:{self._to_neo4j_type(field.data_type)}'
                for field in self._relationship_type.fields.values()
            ],
        )

        # Write the header
        self._writer.writerow(header)

    def _serialize(self, relationship: Relationship, chunk_ids: tuple[ChunkId, ...]) -> list[str]:
        """Serialize a relationship to a list of strings for CSV writing."""
        # Endpoint: Source ID, Target ID
        row = [relationship.source.instance.hex, relationship.target.instance.hex]

        # Identity: Instance ID (main ID), Content ID, Identity Policy, Identity Version
        row.extend(
            [
                relationship.id.instance.hex,
                relationship.id.content.hex,
                self._relationship_type.identity_policy.value,
                relationship.id.VERSION,
            ],
        )

        # Provenance: Chunk IDs (multiple)
        row.append(';'.join(chunk_id.instance.hex for chunk_id in chunk_ids))

        # Properties
        for field in self._relationship_type.fields.values():
            value = relationship.full_properties.get(field)
            row.append(self._serialize_value(value))

        return row

    def write(self, relationship: Relationship, chunk_ids: tuple[ChunkId, ...]) -> None:
        """Write a relationship to the CSV file."""
        self._writer.writerow(self._serialize(relationship, chunk_ids))


class Neo4jChunkSourceWriter(Neo4jWriter):
    """Writes relationships between chunks and their source documents to a CSV file in the Neo4j format."""

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Endpoint: Source ID, Target ID
        header = [':START_ID', ':END_ID']

        # Write the header
        self._writer.writerow(header)

    def _serialize(self, chunk: Chunk) -> list[str]:
        """Serialize a chunk/document to a list of strings for CSV writing."""
        # Endpoint: Source ID, Target ID
        return [chunk.id.instance.hex, chunk.document_id.instance.hex]

    def write(self, chunk: Chunk) -> None:
        """Write a relationship between a chunk and its source document to the CSV file."""
        self._writer.writerow(self._serialize(chunk))


class Neo4jEntityProvenanceWriter(Neo4jWriter):
    """Writes provenance relationships between documents/chunks and their extracted entities to a CSV file in the Neo4j format."""

    def _write_header(self) -> None:
        """Write the header row to the CSV file."""
        # Endpoint: Source ID, Target ID
        header = [':START_ID', ':END_ID']

        # Write the header
        self._writer.writerow(header)

    def _serialize(self, source_id: DocumentId | ChunkId, entity_id: EntityId) -> list[str]:
        """Serialize a provenance relationship to a list of strings for CSV writing."""
        # Endpoint: Source ID, Target ID
        return [entity_id.instance.hex, source_id.instance.hex]

    def write(self, source_id: DocumentId | ChunkId, entity_id: EntityId) -> None:
        """Write a provenance relationship to the CSV file."""
        self._writer.writerow(self._serialize(source_id, entity_id))


# Exporter
class Neo4jKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to the Neo4j graph database format."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        """Initialize the exporter with necessary dependencies."""
        self._repository = repository

    def export(self, model: GraphModel, export_uri: str) -> None:
        """Export knowledge to a specified output format."""
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

        # Export relationships
        self._export_relationships(model, relationships_dir)

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

        # Special Relationship: ChunkOf
        chunk_of_file_path = export_dir / 'relationships' / 'ChunkOf.csv'
        with Neo4jChunkSourceWriter(chunk_of_file_path) as writer:
            for chunk in self._repository.stream_all_chunks():
                writer.write(chunk)

    def _export_entities(self, model: GraphModel, entities_dir: Path) -> None:
        """Export entities to a set of Neo4j CSV files."""
        # Entities
        logger.info('Exporting Entities...')
        for entity_type in model.active_entity_types.values():
            logger.info(f'Exporting Entities of type: {entity_type.name}')
            entity_type_file_path = entities_dir / f'{entity_type.name}.csv'
            with Neo4jEntityWriter(entity_type_file_path, entity_type) as writer:
                for entity in self._repository.stream_entities_by_type(entity_type):
                    writer.write(entity)

        # Special Relationship: ExtractedFrom
        logger.info('Exporting Entity Provenance...')
        extracted_from_file_path = entities_dir.parent / 'relationships' / 'ExtractedFrom.csv'
        with Neo4jEntityProvenanceWriter(extracted_from_file_path) as writer:
            for source_id, entity_id in self._repository.stream_entity_provenance():
                writer.write(source_id, entity_id)

    def _export_relationships(self, model: GraphModel, relationships_dir: Path) -> None:
        """Export relationships to a set of Neo4j CSV files."""
        # Relationships
        logger.info('Exporting Relationships...')
        for relationship_type in model.active_relationship_types.values():
            logger.info(f'Exporting Relationships of type: {relationship_type.name}')
            relationship_type_file_path = relationships_dir / f'{relationship_type.name}.csv'
            with Neo4jRelationshipWriter(relationship_type_file_path, relationship_type) as writer:
                for relationship, chunk_ids in self._repository.stream_relationships_by_type_with_provenance(
                    relationship_type,
                ):
                    writer.write(relationship, chunk_ids)

    def clear(self, export_uri: str) -> None:
        """Clear the exported knowledge state, removing any exported data."""
        clear_directory(Path(export_uri).resolve())
