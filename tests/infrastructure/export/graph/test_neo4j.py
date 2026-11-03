"""Tests for the Neo4j bulk-import CSV exporter."""

import csv
from pathlib import Path

from wukong_engine.core.documents.elements import Chunk
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.knowledge.elements import Entity
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model.values import EntityTypeName, PartialDate
from wukong_engine.core.shared.identity import ContentHash, InstanceId
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema
from wukong_engine.infrastructure.export.graph.neo4j import Neo4jChunkWriter, Neo4jEntityWriter, neo4j_import_script


def test_strings_are_written_raw_for_the_csv_quoting_to_carry(tmp_path: Path) -> None:
    """Write string values unescaped, since ``neo4j-admin import`` doesn't decode backslash escapes."""
    content = 'First line, with "quotes"\nSecond line at C:\\dir\twith a tab'
    document_id = DocumentId.from_components(InstanceId.generate(), ContentHash.from_content_string('document'))
    chunk = Chunk(
        id=ChunkId.from_components(InstanceId.generate(), ContentHash.from_content_string('chunk')),
        document_id=document_id,
        chunk_index=0,
        start_offset=0,
        end_offset=len(content),
        content=content,
    )
    path = tmp_path / 'Chunk.csv'

    with Neo4jChunkWriter(path) as writer:
        writer.write(chunk)

    with path.open(newline='', encoding='utf-8') as file:
        header, row = list(csv.reader(file))
    assert row[[column.split(':')[0] for column in header].index('content')] == content


def test_typed_fields_are_written_as_typed_columns(tmp_path: Path) -> None:
    """Type integer, float, boolean and date columns, writing booleans in lowercase and dates from their first day."""
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': {
                        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
                        'crew_size': {'data_type': 'integer', 'description': 'Crew size.'},
                        'payload': {'data_type': 'float', 'description': 'Payload mass.'},
                        'crewed': {'data_type': 'boolean', 'description': 'Crewed.'},
                        'launch': {'data_type': 'date', 'description': 'Launch.'},
                    },
                    'document_collections': {'chunk': 'missions'},
                },
            },
        },
    )
    entity_type = KnowledgeModelMapper().map_knowledge_model(schema).entity_types[EntityTypeName('Mission')]
    entity_id = EntityId.from_components(InstanceId.generate(), ContentHash.from_content_string('mission'))
    path = tmp_path / 'Mission.csv'

    with Neo4jEntityWriter(path, entity_type) as writer:
        writer.write(
            Entity(
                entity_id,
                entity_type,
                {'code': 'A-1', 'crew_size': -4, 'payload': 2.5, 'crewed': True, 'launch': PartialDate(1969)},
            )
        )

    with path.open(newline='', encoding='utf-8') as file:
        header, row = list(csv.reader(file))
    columns = dict(zip(header, row, strict=True))
    typed_columns = ('crew_size:long', 'payload:double', 'crewed:boolean', 'launch:date')
    assert [columns[column] for column in typed_columns] == ['-4', '2.5', 'true', '1969-01-01']


def test_import_script_labels_every_exported_file() -> None:
    """Import the source files and every exported type's file under its label or relationship type, in that order."""
    script = neo4j_import_script(['Mission', 'Astronaut'], ['AssignedTo'])

    arguments = [line.strip().removesuffix(' \\') for line in script.splitlines() if line.startswith('    --')]
    assert arguments == [
        '--multiline-fields=true',
        '--nodes=Document=entities/Document.csv',
        '--nodes=Chunk=entities/Chunk.csv',
        '--nodes=Mission=entities/Mission.csv',
        '--nodes=Astronaut=entities/Astronaut.csv',
        '--relationships=ChunkOf=relationships/ChunkOf.csv',
        '--relationships=ExtractedFrom=relationships/ExtractedFrom.csv',
        '--relationships=AssignedTo=relationships/AssignedTo.csv',
    ]
    assert script.rstrip().endswith('"$@"')
