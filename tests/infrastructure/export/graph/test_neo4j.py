"""Tests for the Neo4j bulk-import CSV exporter."""

import csv
from pathlib import Path

from wukong_engine.core.documents.elements import Chunk
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.knowledge.elements import Entity
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema
from wukong_engine.infrastructure.export.graph.neo4j import Neo4jChunkWriter, Neo4jEntityWriter


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


def test_integer_fields_are_written_as_long_columns(tmp_path: Path) -> None:
    """Type integer columns as ``long``, which holds every integer field value, and write their decimal text."""
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': {
                        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
                        'crew_size': {'data_type': 'integer', 'description': 'Crew size.'},
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
        writer.write(Entity(entity_id, entity_type, {'code': 'A-1', 'crew_size': -4}))

    with path.open(newline='', encoding='utf-8') as file:
        header, row = list(csv.reader(file))
    assert dict(zip(header, row, strict=True))['crew_size:long'] == '-4'
