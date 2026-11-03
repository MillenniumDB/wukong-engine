"""Tests for the reports of what the graph exporters wrote."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.knowledge.elements import Entity, Relationship
from wukong_engine.core.knowledge.elements.values import EntityId, RelationshipId
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema
from wukong_engine.infrastructure.export.graph import MillenniumDBKnowledgeExporter, Neo4jKnowledgeExporter

MODEL = KnowledgeModelMapper().map_knowledge_model(
    KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Person': {
                    'description': 'A person.',
                    'primary_key': 'name',
                    'fields': {'name': {'data_type': 'string', 'description': 'Name.', 'required': True}},
                    'document_collections': {'chunk': 'letters'},
                },
                'Place': {
                    'description': 'A place.',
                    'primary_key': 'name',
                    'fields': {'name': {'data_type': 'string', 'description': 'Name.', 'required': True}},
                    'document_collections': {'chunk': 'letters'},
                },
            },
            'relationship_types': {
                'Knows': {
                    'description': 'Knows.',
                    'deduplication': 'endpoints',
                    'endpoints': {
                        'Person': {'Person': {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}},
                    },
                },
            },
        },
    ),
)


def _id(cls: Any, name: str) -> Any:
    """Create an identifier of the given class from a name."""
    return cls.from_components(InstanceId.generate(), ContentHash.from_content_string(name))


def _repository() -> SimpleNamespace:
    """Repository holding a document with two chunks, two people who know each other, and no places."""
    person = MODEL.entity_types[EntityTypeName('Person')]
    knows = MODEL.relationship_types[RelationshipTypeName('Knows')]
    document = Document(id=_id(DocumentId, 'letter'), source_uri='letter.txt')
    chunks = [
        Chunk(
            id=_id(ChunkId, f'chunk-{index}'),
            document_id=document.id,
            chunk_index=index,
            start_offset=index,
            end_offset=index + 1,
            content='x',
        )
        for index in range(2)
    ]
    people = [Entity(_id(EntityId, name), person, {'name': name}) for name in ('Ada', 'Grace')]
    relationship = Relationship(_id(RelationshipId, 'knows'), knows, people[0].id, people[1].id, {})
    return SimpleNamespace(
        stream_all_documents=lambda: iter([document]),
        stream_all_chunks=lambda: iter(chunks),
        stream_entities_by_type=lambda entity_type: iter(people if entity_type is person else []),
        stream_entity_provenance=lambda _: iter([(chunks[0].id, people[0].id), (chunks[1].id, people[1].id)]),
        stream_relationships_by_type_with_provenance=lambda *_: iter([(relationship, (chunks[0].id, chunks[1].id))]),
    )


@pytest.mark.parametrize('exporter_type', [MillenniumDBKnowledgeExporter, Neo4jKnowledgeExporter])
def test_exports_report_every_label_and_type_with_what_they_wrote(tmp_path: Path, exporter_type: Any) -> None:
    """Count the objects of every exported label and type, a type with none included, and the files written."""
    report = exporter_type(_repository()).export(MODEL, str(tmp_path))

    assert report.nodes == {'Document': 1, 'Chunk': 2, 'Person': 2, 'Place': 0}
    assert report.edges == {'ChunkOf': 2, 'ExtractedFrom': 2, 'Knows': 1}
    assert report.relationship_provenance == 2
    directory = Path(report.directory)
    assert report.files == {
        path.relative_to(directory).as_posix(): path.stat().st_size for path in directory.rglob('*') if path.is_file()
    }
    assert report.total_bytes > 0
