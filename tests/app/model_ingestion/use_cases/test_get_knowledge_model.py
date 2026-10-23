"""Tests for loading the knowledge model."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from wukong_engine.app.model_ingestion.use_cases import GetKnowledgeModel
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider

EXAMPLE_MODEL = Path(__file__).parents[4] / 'workspaces' / 'example' / 'knowledge_model.json'


def _entity_type(collections: dict[str, str]) -> dict[str, Any]:
    """Build an entity type definition keyed by a required ``code`` field."""
    return {
        'description': 'An entity.',
        'primary_key': 'code',
        'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
        'document_collections': collections,
    }


def test_enabled_types_that_are_never_extracted_are_warned_about(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warn about an entity type without collections and a relationship type without enabled endpoints."""
    model = {
        'extraction_config': {'projection': {'enabled_entities': ['Mission', 'Crew']}},
        'entity_types': {
            'Mission': _entity_type({}),
            'Crew': _entity_type({'chunk': 'crew'}),
            'Vehicle': _entity_type({'chunk': 'vehicles'}),
        },
        'relationship_types': {
            'Flies': {
                'description': 'Crew flying a vehicle.',
                'endpoints': {
                    'Crew': {'Vehicle': {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}},
                },
                'deduplication': 'endpoints',
            },
        },
    }
    path = tmp_path / 'knowledge_model.json'
    path.write_text(json.dumps(model))

    with caplog.at_level(logging.WARNING):
        GetKnowledgeModel(LocalKnowledgeModelProvider()).execute(str(path))

    assert [record.getMessage() for record in caplog.records] == [
        'Entity type "Mission" lists no document collections and is never extracted',
        'Relationship type "Flies" has no endpoint between enabled entity types and is never extracted',
    ]


def test_the_example_model_loads_without_warnings(caplog: pytest.LogCaptureFixture) -> None:
    """Load the example workspace's model, whose enabled types are all extractable, without warnings."""
    with caplog.at_level(logging.WARNING):
        GetKnowledgeModel(LocalKnowledgeModelProvider()).execute(str(EXAMPLE_MODEL))

    assert caplog.records == []
