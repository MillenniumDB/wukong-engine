"""Shared fixtures for the data extraction service tests."""

import json
from pathlib import Path

import pytest

from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider

KNOWLEDGE_MODEL = {
    'extraction_config': {'llm': {'domain': 'Mission reports.', 'language': 'en'}},
    'entity_types': {
        'Mission': {
            'description': 'A mission.',
            'primary_key': 'code',
            'fields': {
                'code': {'data_type': 'string', 'description': 'Code.', 'regex': '^[A-Z]+-[0-9]+$', 'required': True},
                'status': {
                    'data_type': 'string',
                    'description': 'Status.',
                    'options': ['planned', 'active', 'completed'],
                    'default_value': 'planned',
                },
                'crew_size': {'data_type': 'integer', 'description': 'Crew size.', 'min': 1, 'max': 12},
                'payload_tons': {'data_type': 'float', 'description': 'Payload mass.', 'min': 0, 'max': 100},
                'crewed': {'data_type': 'bool', 'description': 'Whether the mission is crewed.'},
            },
            'document_collections': {'document': 'missions', 'chunk': 'missions'},
        },
        'Sol': {
            'description': 'A mission day.',
            'primary_key': 'number',
            'fields': {'number': {'data_type': 'int', 'description': 'Day number.', 'required': True}},
            'document_collections': {'chunk': 'missions'},
        },
        'Incident': {
            'description': 'An incident.',
            'primary_key': 'code',
            'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
            'document_collections': {'chunk': 'missions'},
        },
    },
    'relationship_types': {
        'OccurredDuring': {
            'description': 'An incident during a mission.',
            'endpoints': {
                'Incident': {
                    'Mission': [{'source_context_levels': 'chunk', 'target_context_levels': ['document', 'chunk']}]
                },
            },
            'deduplication': 'endpoints',
            'fields': {'flight_day': {'data_type': 'string', 'description': 'Flight day.', 'regex': '^[0-9]+$'}},
        },
    },
}


@pytest.fixture
def model(tmp_path: Path) -> KnowledgeModel:
    """Load the test knowledge model the way a workspace's is loaded."""
    path = tmp_path / 'knowledge_model.json'
    path.write_text(json.dumps(KNOWLEDGE_MODEL))
    return LocalKnowledgeModelProvider().get(str(path))
