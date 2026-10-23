"""Tests for the validation of relationship types and their fields."""

import pytest

from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema


def test_primary_key_cannot_declare_a_default_value() -> None:
    """Reject a default primary key, which would merge every relationship the LLM returned without one into one."""
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
                        'order': {
                            'data_type': 'string',
                            'description': 'Order.',
                            'required': True,
                            'default_value': '1',
                        },
                    },
                },
            },
        },
    )

    with pytest.raises(ValueError, match='primary key "order" cannot declare a default value'):
        KnowledgeModelMapper().map_knowledge_model(schema)
