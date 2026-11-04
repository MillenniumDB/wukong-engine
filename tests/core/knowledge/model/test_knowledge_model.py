"""Tests for comparing knowledge models when documents are added to a workspace."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema

EXAMPLE_MODEL = Path(__file__).parents[4] / 'workspaces' / 'example' / 'knowledge_model.json'


def _load(definition: dict[str, Any]) -> KnowledgeModel:
    """Load a knowledge model from its JSON definition."""
    return KnowledgeModelMapper().map_knowledge_model(KnowledgeModelSchema.model_validate(definition))


@pytest.fixture
def definition() -> dict[str, Any]:
    """Provide the definition of the example knowledge model."""
    return json.loads(EXAMPLE_MODEL.read_text())


def test_a_model_loaded_again_only_adds_collections(definition: dict[str, Any]) -> None:
    """Treat two loads of the same definition as the same model."""
    assert _load(definition).only_adds_collections_to(_load(definition))


def test_collections_added_to_entity_types_are_the_only_change(definition: dict[str, Any]) -> None:
    """Accept collections added to an entity type, at a context level it had or a new one."""
    edited = copy.deepcopy(definition)
    edited['entity_types']['Mission']['document_collections']['document'] = ['missions', 'logs']
    edited['entity_types']['Spacecraft']['document_collections']['document'] = ['missions']

    assert _load(edited).only_adds_collections_to(_load(definition))


def test_removing_a_collection_is_not_only_adding(definition: dict[str, Any]) -> None:
    """Refuse a model that stops extracting an entity type from one of its collections."""
    edited = copy.deepcopy(definition)
    edited['entity_types']['Mission']['document_collections']['chunk'] = ['missions', 'crew']

    assert not _load(edited).only_adds_collections_to(_load(definition))


@pytest.mark.parametrize(
    'edit',
    [
        lambda model: model['entity_types']['Mission'].update(description='An edited description.'),
        lambda model: model['entity_types'].update(Station=copy.deepcopy(model['entity_types']['Spacecraft'])),
        lambda model: model['relationship_types']['AssignedTo'].update(description='An edited description.'),
        lambda model: model['extraction_config']['llm'].update(domain='An edited domain.'),
    ],
)
def test_any_other_change_is_not_only_adding(definition: dict[str, Any], edit: Any) -> None:
    """Refuse a model that changes anything else, even along with added collections."""
    edited = copy.deepcopy(definition)
    edit(edited)
    edited['entity_types']['Mission']['document_collections']['document'] = ['missions', 'logs']

    assert not _load(edited).only_adds_collections_to(_load(definition))
