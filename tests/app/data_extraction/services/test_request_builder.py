"""Tests for building the requests of entity extraction jobs."""

import logging
from typing import Any

import pytest

from wukong_engine.app.data_extraction.elements import ExtractionJob
from wukong_engine.app.data_extraction.services import EntityExtractionRequestBuilder
from wukong_engine.core.documents.elements import Chunk, Document, LoadedDocument
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName

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
