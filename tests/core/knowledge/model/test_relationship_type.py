"""Tests for the validation of relationship types and their fields."""

from typing import Any

import pytest

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model import KnowledgeModel, RelationshipType
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema


def _load_follows(**fields: dict[str, Any]) -> KnowledgeModel:
    """Load a model with a ``Follows`` relationship type between missions keyed by ``order``, with the given fields."""
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
                    'document_collections': {'chunk': 'missions'},
                },
            },
            'relationship_types': {
                'Follows': {
                    'description': 'A mission following another one.',
                    'endpoints': {
                        'Mission': {
                            'Mission': [{'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}],
                        },
                    },
                    'deduplication': 'primary_key',
                    'primary_key': 'order',
                    'fields': {
                        'order': {'data_type': 'string', 'description': 'Order.', 'required': True},
                        **fields,
                    },
                },
            },
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema)


def test_primary_key_cannot_declare_a_default_value() -> None:
    """Reject a default primary key, which would merge every relationship the LLM returned without one into one."""
    order = {'data_type': 'string', 'description': 'Order.', 'required': True, 'default_value': '1'}

    with pytest.raises(ValueError, match='primary key "order" cannot declare a default value'):
        _load_follows(order=order)


@pytest.mark.parametrize('key', ['options', 'examples', 'default_value'])
def test_values_must_have_the_form_of_an_extracted_value(key: str) -> None:
    """Reject a value no extraction can produce, since extracted values are stripped and an empty one is missing."""
    with pytest.raises(ValueError, match='leading or trailing whitespace'):
        _load_follows(note={'data_type': 'string', 'description': 'Note.', key: ' late'})


@pytest.mark.parametrize(
    ('field', 'error'),
    [
        ({'data_type': 'integer', 'description': 'Delay.', 'min': 2, 'max': 1}, 'min 2 is greater than max 1'),
        ({'data_type': 'integer', 'description': 'Delay.', 'min': 0, 'default_value': -1}, 'Default value -1 is less'),
        ({'data_type': 'integer', 'description': 'Delay.', 'regex': '[0-9]+'}, 'regex only applies to string fields'),
    ],
)
def test_integer_fields_take_single_bounds(field: dict[str, Any], error: str) -> None:
    """Check relationship field bounds, which take a single value instead of one per context level."""
    with pytest.raises(ValueError, match=error):
        _load_follows(delay=field)


@pytest.mark.parametrize(
    ('fields', 'error'),
    [
        ({'distance': {'data_type': 'float', 'description': 'Distance.', 'min': 1, 'default_value': 0}}, 'less than'),
        ({'order': {'data_type': 'double', 'description': 'Order.', 'required': True}}, 'cannot be a float field'),
    ],
)
def test_float_fields_take_single_bounds_and_cannot_be_primary_keys(fields: dict[str, Any], error: str) -> None:
    """Check relationship float field bounds, read from integers, and reject a float primary key."""
    with pytest.raises(ValueError, match=error):
        _load_follows(**fields)


def _load_link(endpoints: dict[str, Any], **flags: bool) -> RelationshipType:
    """Load a ``Link`` relationship type with the given endpoints and flags, between missions and crews."""
    entity_type = {
        'description': 'An entity.',
        'primary_key': 'code',
        'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
        'document_collections': {'document': 'missions', 'chunk': 'missions'},
    }
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {'Mission': entity_type, 'Crew': entity_type},
            'relationship_types': {
                'Link': {
                    'description': 'A link.',
                    'endpoints': endpoints,
                    'deduplication': 'endpoints',
                    **flags,
                },
            },
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema).relationship_types[RelationshipTypeName('Link')]


CREW_IN_CHUNK_TO_MISSION_IN_DOCUMENT = {
    'Crew': {'Mission': {'source_context_levels': 'chunk', 'target_context_levels': 'document'}},
}


def test_symmetric_endpoints_are_valid_in_both_orientations_with_their_context_levels_swapped() -> None:
    """Accept a symmetric type's endpoint reversed, carrying each entity's context level along with it."""
    crew, mission = EntityTypeName('Crew'), EntityTypeName('Mission')
    chunk, document = ContextLevel.CHUNK, ContextLevel.DOCUMENT
    directed = _load_link(CREW_IN_CHUNK_TO_MISSION_IN_DOCUMENT)
    symmetric = _load_link(CREW_IN_CHUNK_TO_MISSION_IN_DOCUMENT, symmetric=True)

    assert directed.is_valid_endpoint(crew, chunk, mission, document)
    assert not directed.is_valid_endpoint(mission, document, crew, chunk)
    assert symmetric.is_valid_endpoint(crew, chunk, mission, document)
    assert symmetric.is_valid_endpoint(mission, document, crew, chunk)
    assert not symmetric.is_valid_endpoint(mission, chunk, crew, document)


def test_self_relationships_can_only_be_allowed_with_an_endpoint_between_the_same_type() -> None:
    """Reject allowing self-relationships when no endpoint could ever connect an entity to itself."""
    with pytest.raises(ValueError, match='no endpoint connects an entity type to itself'):
        _load_link(CREW_IN_CHUNK_TO_MISSION_IN_DOCUMENT, allow_self_relationships=True)

    same_type = {'Mission': {'Mission': {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}}}
    assert _load_link(same_type, allow_self_relationships=True).allow_self_relationships
