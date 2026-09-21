"""Provides the MillenniumDBKnowledgeExporter class."""

import logging
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.knowledge_export.services import KnowledgeRepository
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.knowledge.elements import Entity, Relationship
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model import EntityType, KnowledgeModel, RelationshipType
from wukong_engine.infrastructure.serialization import EscapedStringSerializer, PropertyValueSerializer
from wukong_engine.infrastructure.storage.filesystem import clear_directory

# Logging
logger = logging.getLogger(__name__)


# Writer
class MillenniumDBWriter:
    """Writes entities and relationships to a MillenniumDB QM file."""

    def __init__(self, path: Path) -> None:
        """Initialize the writer."""
        self._path = path
        self._serializer = PropertyValueSerializer(EscapedStringSerializer())

    def __enter__(self) -> Self:
        """Open the QM file for writing."""
        self._file = self._path.open('w', encoding='utf-8')
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the QM file."""
        self._file.close()

    def _serialize_value(self, value: Any) -> str | None:
        """Serialize a property value for MillenniumDB."""
        serialized_value = self._serializer.serialize(value)

        # If the value is null, return None to be explicit
        if serialized_value is None:
            return None

        # If the value is a string, wrap it in double quotes and escape any internal ones
        if isinstance(value, str):
            escaped_value = serialized_value.replace('"', '\\"')
            return f'"{escaped_value}"'

        return serialized_value

    def _write_line(self, identity: str, label: str, properties: list[str]) -> None:
        """Write a line to the QM file representing an object in the MillenniumDB format."""
        self._file.write(f'{identity} :{label} {" ".join(properties)}'.strip() + '\n')

    # Entities

    def write_entity(self, entity: Entity, entity_type: EntityType) -> None:
        """Write an entity to the QM file."""
        # Label
        label = entity_type.name.value

        # Instance ID (main ID), Content ID, Identity Version
        identity = f'N_{entity.id.instance.hex}'
        properties = [f'P_content_id:"{entity.id.content.hex}"', f'P_id_version:"{entity.id.VERSION}"']

        # Properties
        for field in entity_type.fields.values():
            value = entity.full_properties.get(field)
            serialized_value = self._serialize_value(value)
            if serialized_value is not None:
                properties.append(f'{field.name}:{serialized_value}')

        self._write_line(identity, label, properties)

    def write_document(self, document: Document) -> None:
        """Write a document to the QM file."""
        # Label
        label = 'Document'

        # Instance ID (main ID), Content ID
        identity = f'N_{document.id.instance.hex}'
        properties = [f'P_content_id:"{document.id.content.hex}"']

        # Properties
        prop_keys = ['source_uri']
        prop_values = [document.source_uri]
        for key, value in zip(prop_keys, prop_values, strict=True):
            serialized_value = self._serialize_value(value)
            if serialized_value is not None:
                properties.append(f'{key}:{serialized_value}')

        self._write_line(identity, label, properties)

    def write_chunk(self, chunk: Chunk) -> None:
        """Write a chunk to the QM file."""
        # Label
        label = 'Chunk'

        # Instance ID (main ID), Content ID, Identity Version
        identity = f'N_{chunk.id.instance.hex}'
        properties = [f'P_content_id:"{chunk.id.content.hex}"', f'P_id_version:"{chunk.id.VERSION}"']

        # Properties
        prop_keys = ['chunk_index', 'start_offset', 'end_offset', 'content']
        prop_values = [chunk.chunk_index, chunk.start_offset, chunk.end_offset, chunk.content]
        for key, value in zip(prop_keys, prop_values, strict=True):
            serialized_value = self._serialize_value(value)
            if serialized_value is not None:
                properties.append(f'{key}:{serialized_value}')

        self._write_line(identity, label, properties)

    # Relationships

    def write_relationship(
        self,
        relationship: Relationship,
        relationship_type: RelationshipType,
        provenance: tuple[ChunkId, ...],
    ) -> None:
        """Write a relationship to the QM file."""
        # Label
        label = relationship_type.name.value

        # Identity: Endpoint, Instance ID (main ID), Content ID, Identity Policy, Identity Version
        identity = f'N_{relationship.source.instance.hex}->N_{relationship.target.instance.hex}'
        properties = [
            f'P_id:"{relationship.id.instance.hex}"',
            f'P_content_id:"{relationship.id.content.hex}"',
            f'P_id_policy:"{relationship_type.identity_policy.value}"',
            f'P_id_version:"{relationship.id.VERSION}"',
        ]

        # Provenance: Chunk IDs (multiple)
        provenance_chunks = ';'.join(chunk_id.instance.hex for chunk_id in provenance)
        properties.append(f'P_provenance_chunk_ids:"{provenance_chunks}"')

        # Properties
        for field in relationship_type.fields.values():
            value = relationship.full_properties.get(field)
            serialized_value = self._serialize_value(value)
            if serialized_value is not None:
                properties.append(f'{field.name}:{serialized_value}')

        self._write_line(identity, label, properties)

    def write_chunk_source(self, chunk: Chunk) -> None:
        """Write a relationship between a chunk and its source document to the QM file."""
        # Label
        label = 'ChunkOf'

        # Endpoint
        identity = f'N_{chunk.id.instance.hex}->N_{chunk.document_id.instance.hex}'

        self._write_line(identity, label, [])

    def write_entity_provenance(self, source_id: DocumentId | ChunkId, entity_id: EntityId) -> None:
        """Write a provenance relationship to the QM file."""
        # Label
        label = 'ExtractedFrom'

        # Endpoint
        identity = f'N_{entity_id.instance.hex}->N_{source_id.instance.hex}'

        self._write_line(identity, label, [])


# Exporter
class MillenniumDBKnowledgeExporter(KnowledgeExporter):
    """Exports knowledge as a graph to the MillenniumDB graph database format."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        """Initialize the exporter with necessary dependencies."""
        self._repository = repository

    def export(self, model: KnowledgeModel, export_uri: str) -> None:
        """Export knowledge to a specified output format."""
        # Setup export directories
        base_export_dir = Path(export_uri).resolve() / 'mdb'
        base_export_dir.mkdir(parents=True, exist_ok=True)
        output_path = base_export_dir / 'knowledge_graph.qm'
        logger.info(f'Exporting knowledge to MillenniumDB QM file at: {output_path}')

        # Export sources, entities, and relationships
        with MillenniumDBWriter(output_path) as writer:
            self._export_sources(writer)
            self._export_entities(model, writer)
            self._export_relationships(model, writer)

    def _export_sources(self, writer: MillenniumDBWriter) -> None:
        """Export sources to the MillenniumDB format."""
        # Documents
        logger.info('Exporting Documents...')
        for doc in self._repository.stream_all_documents():
            writer.write_document(doc)

        # Chunks and ChunkOf (Special Relationship)
        logger.info('Exporting Chunks...')
        for chunk in self._repository.stream_all_chunks():
            writer.write_chunk(chunk)
            writer.write_chunk_source(chunk)

    def _export_entities(self, model: KnowledgeModel, writer: MillenniumDBWriter) -> None:
        """Export entities to the MillenniumDB format."""
        # Entities
        logger.info('Exporting Entities...')
        for entity_type in model.active_entity_types.values():
            logger.info(f'Exporting Entities of type: {entity_type.name}')
            for entity in self._repository.stream_entities_by_type(entity_type):
                writer.write_entity(entity, entity_type)

        # Special Relationship: ExtractedFrom
        logger.info('Exporting Entity Provenance...')
        for source_id, entity_id in self._repository.stream_entity_provenance():
            writer.write_entity_provenance(source_id, entity_id)

    def _export_relationships(self, model: KnowledgeModel, writer: MillenniumDBWriter) -> None:
        """Export relationships to the MillenniumDB format."""
        # Relationships
        logger.info('Exporting Relationships...')
        for relationship_type in model.active_relationship_types.values():
            logger.info(f'Exporting Relationships of type: {relationship_type.name}')
            for relationship, provenance in self._repository.stream_relationships_by_type_with_provenance(
                relationship_type,
            ):
                writer.write_relationship(relationship, relationship_type, provenance)

    def clear(self, export_uri: str) -> None:
        """Clear the exported knowledge state, removing any exported data."""
        export_path = Path(export_uri).resolve()
        if export_path.exists() and export_path.is_dir():
            clear_directory(export_path)
