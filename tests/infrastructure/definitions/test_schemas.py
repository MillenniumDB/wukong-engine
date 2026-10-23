"""Tests for the validation of the knowledge model and document registry schemas."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from wukong_engine.infrastructure.definitions.documents.schemas import DocumentRegistrySchema
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema

EXAMPLE_WORKSPACE = Path(__file__).parents[3] / 'workspaces' / 'example'


def _example(name: str) -> dict[str, Any]:
    """Load one of the example workspace's definition files."""
    return json.loads((EXAMPLE_WORKSPACE / name).read_text(encoding='utf-8'))


def _rename_key(data: dict[str, Any], path: list[str], new_key: str) -> dict[str, Any]:
    """Rename the key at the end of ``path`` in a nested mapping."""
    parent = data
    for key in path[:-1]:
        parent = parent[key]
    parent[new_key] = parent.pop(path[-1])
    return data


@pytest.mark.parametrize(
    ('schema', 'file_name', 'path', 'misspelled_key'),
    [
        (
            KnowledgeModelSchema,
            'knowledge_model.json',
            ['entity_types', 'Mission', 'document_collections'],
            'document_collection',
        ),
        (KnowledgeModelSchema, 'knowledge_model.json', ['relationship_types', 'AssignedTo', 'endpoints'], 'endpoint'),
        (
            KnowledgeModelSchema,
            'knowledge_model.json',
            ['entity_types', 'Mission', 'fields', 'code', 'required'],
            'requried',
        ),
        (DocumentRegistrySchema, 'document_collections.json', ['collections'], 'collection'),
    ],
)
def test_misspelled_keys_are_rejected(
    schema: type[BaseModel],
    file_name: str,
    path: list[str],
    misspelled_key: str,
) -> None:
    """Reject an unknown key instead of silently dropping it, which would quietly change what gets extracted."""
    data = _rename_key(_example(file_name), path, misspelled_key)
    with pytest.raises(ValidationError, match=rf'{misspelled_key}\s+Extra inputs are not permitted'):
        schema.model_validate(data)


@pytest.mark.parametrize(
    'rules',
    [
        [],
        {'source_context_levels': [], 'target_context_levels': 'chunk'},
        {'source_context_levels': 'chunk', 'target_context_levels': []},
    ],
)
def test_endpoints_without_any_context_pair_are_rejected(rules: Any) -> None:
    """Reject an endpoint with no rules or no levels, which would leave its relationship type active but jobless."""
    data = _example('knowledge_model.json')
    data['relationship_types']['AssignedTo']['endpoints'] = {'Astronaut': {'Mission': rules}}

    with pytest.raises(ValidationError, match='at least 1 item'):
        KnowledgeModelSchema.model_validate(data)


def test_endpoint_sources_without_targets_are_rejected() -> None:
    """Reject a source entity type listed in the endpoints with no target types."""
    data = _example('knowledge_model.json')
    data['relationship_types']['AssignedTo']['endpoints'] = {'Astronaut': {}}

    with pytest.raises(ValidationError, match='at least 1 item'):
        KnowledgeModelSchema.model_validate(data)


@pytest.mark.parametrize(
    ('path', 'mapping'),
    [
        (['fields', 'code', 'retrieval_mode'], {'chunk': 'skip', 'CHUNK': 'extract'}),
        (['document_collections'], {'chunk': 'missions', 'Chunk': 'crew'}),
    ],
)
def test_context_levels_repeated_in_another_case_are_rejected(path: list[str], mapping: dict[str, str]) -> None:
    """Reject a mapping naming a context level twice, which would otherwise silently keep the last value."""
    data = _example('knowledge_model.json')
    parent = data['entity_types']['Mission']
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = mapping

    with pytest.raises(ValidationError, match='Context level given more than once'):
        KnowledgeModelSchema.model_validate(data)
