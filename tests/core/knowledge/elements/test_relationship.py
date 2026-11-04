"""Tests for the identity and endpoint order of relationships."""

from typing import Any

import pytest

from wukong_engine.core.knowledge.elements import Relationship
from wukong_engine.core.knowledge.elements.values import EntityId, NormalizedPK
from wukong_engine.core.knowledge.model import RelationshipType
from wukong_engine.core.knowledge.model.values import RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema


def _link_type(deduplication: str, *, symmetric: bool) -> RelationshipType:
    """Load a ``Link`` relationship type between missions, keyed by ``kind`` under the primary key policy."""
    link: dict[str, Any] = {
        'description': 'A link between missions.',
        'endpoints': {'Mission': {'Mission': {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}}},
        'deduplication': deduplication,
        'symmetric': symmetric,
    }
    if deduplication == 'primary_key':
        link |= {
            'primary_key': 'kind',
            'fields': {'kind': {'data_type': 'string', 'description': 'Kind.', 'required': True}},
        }
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
            'relationship_types': {'Link': link},
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema).relationship_types[RelationshipTypeName('Link')]


def _entity_id(content: str) -> EntityId:
    """Build an entity ID whose content ID is the hash of ``content``."""
    return EntityId.from_components(InstanceId.generate(), ContentHash.from_content_string(content))


def _link(relationship_type: RelationshipType, source: EntityId, target: EntityId) -> Relationship:
    """Extract a relationship of the given type, with kind ``escort`` if the type has a primary key."""
    if relationship_type.primary_key is None:
        return Relationship.from_extraction(relationship_type, source, target, {})
    return Relationship.from_extraction(relationship_type, source, target, {'kind': 'escort'}, NormalizedPK('escort'))


# Sorted by content ID, so a relationship from LOW to HIGH is already in the order symmetric types store
LOW, HIGH = sorted((_entity_id('apollo'), _entity_id('gemini')), key=lambda entity_id: entity_id.content.hex)


@pytest.mark.parametrize('deduplication', ['endpoints', 'primary_key'])
def test_both_orientations_of_a_symmetric_relationship_are_the_same_relationship(deduplication: str) -> None:
    """Give both orientations the same identity, and store them with their endpoints in the same order."""
    relationship_type = _link_type(deduplication, symmetric=True)

    forward, backward = _link(relationship_type, LOW, HIGH), _link(relationship_type, HIGH, LOW)

    assert forward.id.content == backward.id.content
    assert (backward.source, backward.target) == (forward.source, forward.target) == (LOW, HIGH)


@pytest.mark.parametrize('deduplication', ['endpoints', 'primary_key'])
def test_both_orientations_of_a_directed_relationship_are_distinct_relationships(deduplication: str) -> None:
    """Keep directed relationships as extracted, with an identity per orientation."""
    relationship_type = _link_type(deduplication, symmetric=False)

    forward, backward = _link(relationship_type, LOW, HIGH), _link(relationship_type, HIGH, LOW)

    assert forward.id.content != backward.id.content
    assert (backward.source, backward.target) == (HIGH, LOW)


@pytest.mark.parametrize(
    ('deduplication', 'identity'),
    [
        ('endpoints', 'v1|Link|ENDPOINTS|{low}|{high}'),
        ('primary_key', 'v1|Link|PRIMARY_KEY|{low}|{high}|escort'),
    ],
)
def test_directed_identities_keep_their_v1_definition(deduplication: str, identity: str) -> None:
    """Hash directed identities exactly as v1 always has, so existing content IDs stay valid."""
    relationship = _link(_link_type(deduplication, symmetric=False), LOW, HIGH)

    expected = identity.format(low=LOW.content.hex, high=HIGH.content.hex)
    assert relationship.id.content == ContentHash.from_content_string(expected)


@pytest.mark.parametrize('deduplication', ['endpoints', 'primary_key'])
def test_symmetry_is_part_of_the_identity(deduplication: str) -> None:
    """Change every identity when a type becomes symmetric, even those whose endpoints were already in order."""
    directed = _link(_link_type(deduplication, symmetric=False), LOW, HIGH)
    symmetric = _link(_link_type(deduplication, symmetric=True), LOW, HIGH)

    assert directed.id.content != symmetric.id.content
