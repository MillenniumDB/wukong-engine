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
