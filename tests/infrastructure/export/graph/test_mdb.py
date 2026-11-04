"""Tests for the MillenniumDB QM file exporter."""

from pathlib import Path

from wukong_engine.core.knowledge.elements import Entity
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model.values import EntityTypeName, PartialDate
from wukong_engine.core.shared.identity import ContentHash, InstanceId
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema
from wukong_engine.infrastructure.export.graph.mdb import MillenniumDBWriter


def test_numbers_and_booleans_are_written_unquoted_and_strings_quoted(tmp_path: Path) -> None:
    """Write numbers, booleans and dates (from their first day) as QM literals, and strings quoted."""
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
                        'margin': {'data_type': 'float', 'description': 'Safety margin.'},
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
    path = tmp_path / 'knowledge_graph.qm'

    with MillenniumDBWriter(path) as writer:
        properties = {
            'code': '12',
            'crew_size': -(2**56 - 1),
            'payload': 4.0,
            'margin': 1e-05,
            'crewed': False,
            'launch': PartialDate(1969, 7),
        }
        writer.write_entity(Entity(entity_id, entity_type, properties), entity_type)

    assert path.read_text(encoding='utf-8').split()[-6:] == [
        'code:"12"',
        'crew_size:-72057594037927935',
        'payload:4.0',
        'margin:1e-05',
        'crewed:false',
        'launch:date("1969-07-01")',
    ]
