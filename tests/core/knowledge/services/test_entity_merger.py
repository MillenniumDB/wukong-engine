"""Tests for merging observations of the same entity."""

import pytest

from wukong_engine.core.knowledge.elements import Entity
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model import EntityType
from wukong_engine.core.knowledge.model.values import EntityTypeName
from wukong_engine.core.knowledge.services import EntityMerger
from wukong_engine.core.shared.identity import ContentHash, InstanceId
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema


def _mission_type(merge_strategy: str) -> EntityType:
    """Build a ``Mission`` entity type whose ``summary`` field uses the given merge strategy."""
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': {
                        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
                        'summary': {'data_type': 'string', 'description': 'Summary.', 'merge_strategy': merge_strategy},
                    },
                    'document_collections': {'chunk': 'missions'},
                },
            },
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema).entity_types[EntityTypeName('Mission')]


@pytest.mark.parametrize('merge_strategy', ['longest', 'shortest'])
def test_length_ties_resolve_the_same_way_in_either_order(merge_strategy: str) -> None:
    """Break a tie between equally long values the same way whichever is seen first, so runs are reproducible."""
    entity_type = _mission_type(merge_strategy)
    entity_id = EntityId.from_components(InstanceId.generate(), ContentHash.from_content_string('mission'))
    first, second = (Entity(entity_id, entity_type, {'code': 'A-1', 'summary': value}) for value in ('Orbit', 'Lunar'))

    merged = {
        EntityMerger().merge(first, second).properties['summary'],
        EntityMerger().merge(second, first).properties['summary'],
    }

    assert merged == {'Lunar'}


def _crew_type(merge_strategy: str) -> EntityType:
    """Build a ``Mission`` entity type whose integer ``crew_size`` field uses the given merge strategy."""
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': {
                        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
                        'crew_size': {'data_type': 'integer', 'description': 'Crew.', 'merge_strategy': merge_strategy},
                    },
                    'document_collections': {'chunk': 'missions'},
                },
            },
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema).entity_types[EntityTypeName('Mission')]


@pytest.mark.parametrize(('merge_strategy', 'expected'), [('largest', 12), ('max', 12), ('smallest', 9), ('min', 9)])
def test_numeric_strategies_pick_by_value_in_either_order(merge_strategy: str, expected: int) -> None:
    """Pick the largest or smallest number, not the longest or shortest text, whichever is seen first."""
    entity_type = _crew_type(merge_strategy)
    entity_id = EntityId.from_components(InstanceId.generate(), ContentHash.from_content_string('mission'))
    first, second = (Entity(entity_id, entity_type, {'code': 'A-1', 'crew_size': value}) for value in (12, 9))

    merged = {
        EntityMerger().merge(first, second).properties['crew_size'],
        EntityMerger().merge(second, first).properties['crew_size'],
    }

    assert merged == {expected}
