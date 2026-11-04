"""Tests for checking what adding the documents of a registry to the ingested ones would do."""

import os
from pathlib import Path
from types import MappingProxyType

import pytest

from wukong_engine.app.document_ingestion.use_cases import CheckDocumentAdditions
from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry, DocumentSource
from wukong_engine.core.documents.model.values import DocumentCollectionName, DocumentSourceMode
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem.documents import LocalDocumentStreamProvider


class Workspace:
    """Data directory and staging database, holding documents ingested and extracted by earlier runs."""

    def __init__(self, tmp_path: Path) -> None:
        """Create an empty data directory and staging database."""
        self.data = tmp_path / 'data'
        self.data.mkdir()
        factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
        initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
        self.conn = factory()
        self.uow = SQLiteUnitOfWork(connection_factory=factory)

    def write(self, path: str, text: str) -> None:
        """Write a document to the data directory."""
        file = self.data / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def ingest(self, text: str, *collections: str, relationships_extracted: bool = False) -> None:
        """Store a document with one chunk in the given collections, as if relationships were extracted from it."""
        document_id = ContentHash.from_content_string(text).bytes
        chunk_id = ContentHash.from_content_string(f'{text} chunk').bytes
        with self.conn:
            self.conn.execute('INSERT INTO documents VALUES (?, ?, ?)', (document_id, os.urandom(16), text))
            self.conn.execute(
                'INSERT INTO chunks VALUES (?, ?, ?, 0, 0, ?, ?)',
                (chunk_id, os.urandom(16), document_id, len(text), text),
            )
            for collection in collections:
                self.conn.execute('INSERT OR IGNORE INTO collections VALUES (?)', (collection,))
                self.conn.execute('INSERT INTO document_collections VALUES (?, ?)', (document_id, collection))
            if relationships_extracted:
                self.conn.execute("INSERT OR IGNORE INTO relationship_types VALUES ('AssignedTo')")
                self.conn.execute(
                    "INSERT INTO relationship_extractions VALUES (?, 'AssignedTo', 'COMPLETED', 1, 0, NULL)",
                    (chunk_id,),
                )

    def link(self, entity_type: str, *collections: str) -> None:
        """Store the links entity extraction made between an entity type and collections, at chunk level."""
        with self.conn:
            self.conn.execute('INSERT OR IGNORE INTO entity_types VALUES (?)', (entity_type,))
            for collection in collections:
                self.conn.execute('INSERT OR IGNORE INTO collections VALUES (?)', (collection,))
                self.conn.execute(
                    "INSERT INTO entity_type_collections VALUES ('CHUNK', ?, ?)",
                    (entity_type, collection),
                )

    def registry(self, *collections: str) -> DocumentRegistry:
        """Build a registry whose collections are the directories of the data directory with the same name."""
        return DocumentRegistry(
            collections=MappingProxyType(
                {
                    DocumentCollectionName(name): DocumentCollection(
                        name=DocumentCollectionName(name),
                        sources=(DocumentSource(root=str(self.data / name), mode=DocumentSourceMode.DIRECTORY),),
                    )
                    for name in collections
                },
            ),
        )

    def check(self, registry: DocumentRegistry, model: KnowledgeModel) -> tuple[int, int, list[str]]:
        """Check the addition, returning the found and new documents and the source URIs of the conflicts."""
        additions = CheckDocumentAdditions(LocalDocumentStreamProvider(), self.uow).execute(
            registry,
            str(self.data),
            model,
        )
        conflicts = sorted(document.source_uri for document in additions.conflicts)
        return additions.found_documents, additions.new_documents, conflicts


def _model(**collections: list[str]) -> KnowledgeModel:
    """Build a model with an entity type for each keyword, extracted from the given collections at chunk level."""
    return KnowledgeModelMapper().map_knowledge_model(
        KnowledgeModelSchema.model_validate(
            {
                'entity_types': {
                    name: {
                        'description': f'A {name}.',
                        'primary_key': 'name',
                        'fields': {'name': {'data_type': 'string', 'description': 'Name.', 'required': True}},
                        'document_collections': {'chunk': names},
                    }
                    for name, names in collections.items()
                },
            },
        ),
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Provide an empty workspace."""
    return Workspace(tmp_path)


def test_counts_the_documents_not_ingested_yet(workspace: Workspace) -> None:
    """Count each document found once, even if several files hold it, and tell how many aren't stored."""
    workspace.write('missions/old.txt', 'old')
    workspace.write('missions/new.txt', 'new')
    workspace.write('crew/new_again.txt', 'new')
    workspace.ingest('old', 'missions')

    found, new, conflicts = workspace.check(workspace.registry('missions', 'crew'), _model(Mission=['missions']))

    assert (found, new, conflicts) == (2, 1, [])


def test_an_extracted_document_joining_a_collection_of_another_entity_type_conflicts(workspace: Workspace) -> None:
    """Refuse to extract more entity types from a document whose relationships were extracted without them."""
    workspace.write('missions/report.txt', 'report')
    workspace.write('crew/report_copy.txt', 'report')
    workspace.ingest('report', 'missions', relationships_extracted=True)
    workspace.link('Mission', 'missions')
    workspace.link('Astronaut', 'crew')
    model = _model(Mission=['missions'], Astronaut=['crew'])

    _, _, conflicts = workspace.check(workspace.registry('missions', 'crew'), model)

    assert conflicts == ['report']


def test_joining_a_collection_that_adds_no_entity_type_does_not_conflict(workspace: Workspace) -> None:
    """Let an extracted document join a collection that no entity type, or only its own ones, is extracted from."""
    workspace.write('missions/report.txt', 'report')
    workspace.write('archive/report_copy.txt', 'report')
    workspace.write('logs/report_copy.txt', 'report')
    workspace.ingest('report', 'missions', relationships_extracted=True)
    workspace.link('Mission', 'missions', 'logs')

    _, _, conflicts = workspace.check(
        workspace.registry('missions', 'archive', 'logs'),
        _model(Mission=['missions', 'logs']),
    )

    assert conflicts == []


def test_a_document_without_extracted_relationships_may_gain_entity_types(workspace: Workspace) -> None:
    """Let a document gain entity types while its relationships are still to be extracted from all of them."""
    workspace.write('missions/report.txt', 'report')
    workspace.write('crew/report_copy.txt', 'report')
    workspace.ingest('report', 'missions')
    workspace.link('Mission', 'missions')
    workspace.link('Astronaut', 'crew')

    _, _, conflicts = workspace.check(
        workspace.registry('missions', 'crew'),
        _model(Mission=['missions'], Astronaut=['crew']),
    )

    assert conflicts == []


def test_adding_a_collection_of_an_extracted_document_to_an_entity_type_conflicts(workspace: Workspace) -> None:
    """Refuse a model that extracts another entity type from the collection of an extracted document."""
    workspace.write('missions/report.txt', 'report')
    workspace.write('crew/profile.txt', 'profile')
    workspace.ingest('report', 'missions', relationships_extracted=True)
    workspace.ingest('profile', 'crew', relationships_extracted=True)
    workspace.link('Mission', 'missions')
    workspace.link('Astronaut', 'crew')

    _, _, conflicts = workspace.check(
        workspace.registry('missions', 'crew'),
        _model(Mission=['missions'], Astronaut=['crew', 'missions']),
    )

    assert conflicts == ['report']
