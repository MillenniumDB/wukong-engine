"""Tests for building the requests of entity and relationship extraction jobs."""

import logging
import re
from typing import Any, cast

import pytest

from wukong_engine.app.data_extraction.elements import ExtractionJob
from wukong_engine.app.data_extraction.services import (
    EntityExtractionRequestBuilder,
    RelationshipExtractionRepository,
    RelationshipExtractionRequestBuilder,
)
from wukong_engine.app.data_extraction.services.request_builder import (
    DATE_PATTERN,
    _generate_field_schema,
    _render_value,
)
from wukong_engine.core.documents.elements import Chunk, Document, LoadedDocument
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model import KnowledgeModel, RelationshipType
from wukong_engine.core.knowledge.model.values import EntityTypeName, FieldName, RelationshipTypeName
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema

TEXT = 'Mission ARTEMIS-7 launched.\n\nThe crew landed on day 3.'
DOCUMENT = Document(id=DocumentId.from_content(TEXT.encode()), source_uri='/data/missions/artemis_7.txt')


def _chunk(index: int, start: int, end: int) -> Chunk:
    """Build a chunk of ``TEXT`` spanning ``[start, end)``."""
    return Chunk(
        id=ChunkId.from_identity(DOCUMENT.id, index),
        document_id=DOCUMENT.id,
        chunk_index=index,
        start_offset=start,
        end_offset=end,
        content=TEXT[start:end],
    )


class Repository:
    """Repository serving a document-level job on ``DOCUMENT`` and its chunks."""

    def __init__(self, chunks: tuple[Chunk, ...]) -> None:
        """Initialize the repository with the document's ingested chunks."""
        self.chunks = chunks

    def get_job_source_context(self, _: ExtractionJob) -> Document:
        """Return the job's document."""
        return DOCUMENT

    def get_job_entity_types(self, _: ExtractionJob) -> tuple[EntityTypeName, ...]:
        """Return the job's entity type."""
        return (EntityTypeName('Mission'),)

    def get_document_chunks(self, _: Document) -> tuple[Chunk, ...]:
        """Return the document's chunks."""
        return self.chunks


class MissingFileLoader:
    """Loader failing as if the document's file had been deleted since ingestion."""

    def load(self, document: Document, **_: Any) -> LoadedDocument:
        """Fail to read the file."""
        raise FileNotFoundError(document.source_uri)

    def truncate(self, content: str, _: int) -> str:
        """Keep the text whole."""
        return content


def _build(model: KnowledgeModel, repository: Repository, loader: Any) -> str:
    """Build the request of a document-level job and return its source text."""
    builder = EntityExtractionRequestBuilder(repository=repository, document_loader=loader)
    job = ExtractionJob.from_context(ContextLevel.DOCUMENT, DOCUMENT.id.content)
    return builder.build(job, model).spec.source_text


def test_a_document_that_cannot_be_read_is_rebuilt_from_its_chunks(
    model: KnowledgeModel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rebuild the text of a missing file from its overlapping chunks, logging the failure and the fallback."""
    chunks = (_chunk(0, 0, 27), _chunk(1, 18, 28), _chunk(2, 29, len(TEXT)))  # Overlap, then a whitespace-only gap

    with caplog.at_level(logging.WARNING):
        text = _build(model, Repository(chunks), MissingFileLoader())

    assert text == 'Mission ARTEMIS-7 launched.\n\nThe crew landed on day 3.'
    assert [record.levelname for record in caplog.records] == ['ERROR', 'WARNING']
    assert 'rebuilt from its 3 ingested chunk(s)' in caplog.text


@pytest.mark.parametrize(
    ('value', 'expected'), [(True, 'true'), (False, 'false'), (4, '4'), (2.5, '2.5'), ('Ada', 'Ada')]
)
def test_values_are_rendered_in_prompts_as_responses_write_them(value: Any, expected: str) -> None:
    """Render booleans as the JSON literals responses use, not as Python's ``True`` and ``False``."""
    assert _render_value(value) == expected


def test_dates_are_requested_as_iso_text_at_any_precision() -> None:
    """Ask for dates as text matching an ISO pattern down to the year, and write date options as ISO text."""
    model = KnowledgeModelMapper().map_knowledge_model(
        KnowledgeModelSchema.model_validate(
            {
                'entity_types': {
                    'Mission': {
                        'description': 'A mission.',
                        'primary_key': 'code',
                        'fields': {
                            'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
                            'launch': {'data_type': 'date', 'description': 'Launch.'},
                            'era': {'data_type': 'date', 'description': 'Era.', 'options': ['1960', '1970']},
                        },
                        'document_collections': {'chunk': 'missions'},
                    },
                },
            },
        ),
    )
    fields = model.entity_types[EntityTypeName('Mission')].fields

    launch, era = _generate_field_schema(fields[FieldName('launch')]), _generate_field_schema(fields[FieldName('era')])

    assert launch == {'type': ['string', 'null'], 'pattern': DATE_PATTERN}
    assert era == {'type': ['string', 'null'], 'enum': ['1960', '1970', None]}
    assert [bool(re.fullmatch(DATE_PATTERN[1:-1], text)) for text in ('1969', '1969-07', '1969-07-16', '1969-13')] == [
        True,
        True,
        True,
        False,
    ]


def _link_type(endpoints: dict[str, Any], **flags: bool) -> RelationshipType:
    """Load a ``Link`` relationship type with the given endpoints and flags, between missions and crews."""
    entity_type = {
        'description': 'An entity.',
        'primary_key': 'code',
        'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
        'document_collections': {'document': 'missions', 'chunk': 'missions'},
    }
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {'Mission': entity_type, 'Crew': entity_type},
            'relationship_types': {
                'Link': {'description': 'A link.', 'endpoints': endpoints, 'deduplication': 'endpoints', **flags},
            },
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema).relationship_types[RelationshipTypeName('Link')]


def _render(relationship_type: RelationshipType) -> str:
    """Render the prompt definition of a relationship type."""
    builder = RelationshipExtractionRequestBuilder(repository=cast('RelationshipExtractionRepository', None))
    return builder._render_relationship_type(relationship_type)


MISSION_TO_MISSION = {'Mission': {'Mission': {'source_context_levels': 'chunk', 'target_context_levels': 'document'}}}


def test_symmetric_types_are_rendered_with_undirected_endpoints() -> None:
    """Render a symmetric type's endpoints as undirected and ask for each pair once, unlike a directed type's."""
    directed, symmetric = (
        _render(_link_type(MISSION_TO_MISSION)),
        _render(_link_type(MISSION_TO_MISSION, symmetric=True)),
    )

    assert '- Mission (CHUNK) -> Mission (DOCUMENT)' in directed
    assert 'symmetric' not in directed
    assert '- Mission (CHUNK) <-> Mission (DOCUMENT)' in symmetric
    assert 'Extract each pair of related entities only once.' in symmetric


def test_self_relationships_are_ruled_out_only_where_an_endpoint_makes_them_possible() -> None:
    """Forbid or allow relating an entity to itself, saying nothing when no endpoint connects a type to itself."""
    crew_to_mission = {'Crew': {'Mission': {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}}}

    assert 'Never relate an entity to itself' in _render(_link_type(MISSION_TO_MISSION))
    assert 'An entity may be related to itself' in _render(
        _link_type(MISSION_TO_MISSION, allow_self_relationships=True),
    )
    assert 'itself' not in _render(_link_type(crew_to_mission))
