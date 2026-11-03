"""Tests for the JSON encoding of properties in the SQLite stores."""

from wukong_engine.core.knowledge.model.values import EntityTypeName, PartialDate
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema
from wukong_engine.infrastructure.persistence.sqlite.stores.properties import dump_properties, load_properties


def test_properties_round_trip_with_dates_as_iso_text() -> None:
    """Store dates as ISO text and read them back as dates, leaving strings that look like dates as strings."""
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': {
                        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
                        'launch': {'data_type': 'date', 'description': 'Launch.'},
                        'landing': {'data_type': 'date', 'description': 'Landing.'},
                        'crewed': {'data_type': 'bool', 'description': 'Crewed.'},
                    },
                    'document_collections': {'chunk': 'missions'},
                },
            },
        },
    )
    fields = KnowledgeModelMapper().map_knowledge_model(schema).entity_types[EntityTypeName('Mission')].fields
    properties = {'code': '1969', 'launch': PartialDate(1969, 7), 'crewed': True}

    text = dump_properties(properties)

    assert text == '{"code":"1969","crewed":true,"launch":"1969-07"}'
    assert load_properties(text, fields.values()) == properties
