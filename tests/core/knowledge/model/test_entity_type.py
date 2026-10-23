"""Tests for the validation of entity types and their fields."""

from typing import Any

import pytest

from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema


def _load_mission(**fields: dict[str, Any]) -> KnowledgeModel:
    """Load a model with a ``Mission`` entity type keyed by ``code``, overriding or adding the given fields."""
    mission_fields: dict[str, Any] = {
        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
        'name': {'data_type': 'string', 'description': 'Name.'},
        **fields,
    }
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': mission_fields,
                    'document_collections': {'document': 'missions'},
                },
            },
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema)


@pytest.mark.parametrize('field_name', ['code', 'name'])
def test_load_retrieval_mode_is_rejected_until_implemented(field_name: str) -> None:
    """Reject the ``load`` retrieval mode, which would otherwise leave the field unfilled after the LLM call."""
    field = {'data_type': 'string', 'description': 'A field.', 'retrieval_mode': {'document': 'load'}}
    if field_name == 'code':
        field['required'] = True

    with pytest.raises(ValueError, match='"load" is not implemented yet'):
        _load_mission(**{field_name: field})


def test_primary_key_cannot_declare_a_default_value() -> None:
    """Reject a default primary key, which would merge every entity the LLM returned without one into one entity."""
    code = {'data_type': 'string', 'description': 'Code.', 'required': True, 'default_value': 'ARTEMIS-7'}

    with pytest.raises(ValueError, match='primary key "code" cannot declare a default value'):
        _load_mission(code=code)
