"""Tests for the knowledge repository streams used by the exporters."""

import json
import os
from pathlib import Path

import pytest

from wukong_engine.app.knowledge_export.services import KnowledgeRepository
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)

CHUNK_RULES = [{'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}]
KNOWLEDGE_MODEL = {
    'extraction_config': {'projection': {'enabled_entities': ['Incident', 'Mission']}},
    'entity_types': {
        name: {
            'description': f'A {name.lower()}.',
            'primary_key': 'code',
            'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
            'document_collections': {'chunk': 'reports'},
        }
        for name in ('Incident', 'Mission', 'Vehicle')
    },
    'relationship_types': {
        'Involves': {
            'description': 'An incident involving a mission or vehicle.',
            'endpoints': {'Incident': {'Mission': CHUNK_RULES, 'Vehicle': CHUNK_RULES}},
            'deduplication': 'endpoints',
        },
    },
}


@pytest.fixture
def model(tmp_path: Path) -> KnowledgeModel:
    """Load a model whose projection leaves out the ``Vehicle`` entity type."""
    path = tmp_path / 'knowledge_model.json'
    path.write_text(json.dumps(KNOWLEDGE_MODEL))
    return LocalKnowledgeModelProvider().get(str(path))


@pytest.fixture
def repository(tmp_path: Path) -> KnowledgeRepository:
    """Stage one chunk with an incident, a mission and a vehicle, and an ``Involves`` edge to each of the latter two."""
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    conn = factory()
    document_id = ContentHash.from_content_string('document').bytes
    chunk_id = ContentHash.from_content_string('chunk').bytes
    conn.execute('INSERT INTO documents VALUES (?, ?, ?)', (document_id, os.urandom(16), 'document.txt'))
    conn.execute('INSERT INTO chunks VALUES (?, ?, ?, 0, 0, 5, ?)', (chunk_id, os.urandom(16), document_id, 'chunk'))
    conn.execute("INSERT INTO relationship_types VALUES ('Involves')")
    for name in ('Incident', 'Mission', 'Vehicle'):
        entity_id = ContentHash.from_content_string(name).bytes
        conn.execute('INSERT INTO entity_types VALUES (?)', (name,))
        conn.execute('INSERT INTO entities VALUES (?, ?, ?, ?)', (entity_id, os.urandom(16), name, '{"code":"X"}'))
        conn.execute("INSERT INTO entity_provenance VALUES ('CHUNK', ?, ?)", (chunk_id, entity_id))
    for target in ('Mission', 'Vehicle'):
        relationship_id = ContentHash.from_content_string(target).bytes[::-1]
        conn.execute(
            "INSERT INTO relationships VALUES (?, ?, 'Involves', ?, ?, '{}')",
            (
                relationship_id,
                os.urandom(16),
                ContentHash.from_content_string('Incident').bytes,
                ContentHash.from_content_string(target).bytes,
            ),
        )
        conn.execute('INSERT INTO relationship_provenance VALUES (?, ?)', (chunk_id, relationship_id))
    conn.commit()
    conn.close()
    return KnowledgeRepository(SQLiteUnitOfWork(connection_factory=factory))


def test_relationships_to_entity_types_left_out_of_the_export_are_skipped(
    model: KnowledgeModel,
    repository: KnowledgeRepository,
) -> None:
    """Stream only the relationships whose endpoint types are exported, so no edge points at a missing node."""
    relationship_type = model.relationship_types[RelationshipTypeName('Involves')]

    streamed = list(
        repository.stream_relationships_by_type_with_provenance(
            relationship_type,
            model.active_endpoints(relationship_type),
        ),
    )

    assert [relationship.target.content for relationship, _ in streamed] == [
        ContentHash.from_content_string('Mission'),
    ]
    assert [len(chunk_ids) for _, chunk_ids in streamed] == [1]


def test_entity_provenance_of_entity_types_left_out_of_the_export_is_skipped(
    model: KnowledgeModel,
    repository: KnowledgeRepository,
) -> None:
    """Stream ``ExtractedFrom`` links only for entities of exported types."""
    streamed = [entity_id.content for _, entity_id in repository.stream_entity_provenance(model.active_entity_types)]

    assert sorted(streamed, key=lambda content: content.bytes) == sorted(
        (ContentHash.from_content_string(name) for name in ('Incident', 'Mission')),
        key=lambda content: content.bytes,
    )
