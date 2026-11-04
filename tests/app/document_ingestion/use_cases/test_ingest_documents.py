"""Tests for ingesting document collections into staging storage."""

from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.document_ingestion.ports import DocumentChunker
from wukong_engine.app.document_ingestion.use_cases import IngestDocuments
from wukong_engine.core.documents.elements import Chunk, LoadedDocument
from wukong_engine.core.documents.elements.values import ChunkId
from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry, DocumentSource
from wukong_engine.core.documents.model.values import DocumentCollectionName, DocumentSourceMode
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem.documents import LocalDocumentLoader, LocalDocumentStreamProvider


class RecordingChunker(DocumentChunker):
    """Chunker turning each document into a single chunk, recording the text of the documents it chunks."""

    def __init__(self) -> None:
        """Initialize the chunker with no documents chunked."""
        self.chunked: list[str] = []

    def chunk(self, document: LoadedDocument) -> Iterator[Chunk]:
        """Record the document and yield it whole as its only chunk."""
        self.chunked.append(document.content)
        yield Chunk(
            id=ChunkId.from_identity(document.metadata.id, 0),
            document_id=document.metadata.id,
            chunk_index=0,
            start_offset=0,
            end_offset=len(document.content),
            content=document.content,
        )


def _registry(data: Path, *collections: str) -> DocumentRegistry:
    """Build a registry whose collections are the directories of the data directory with the same name."""
    return DocumentRegistry(
        collections=MappingProxyType(
            {
                DocumentCollectionName(name): DocumentCollection(
                    name=DocumentCollectionName(name),
                    sources=(DocumentSource(root=str(data / name), mode=DocumentSourceMode.DIRECTORY),),
                )
                for name in collections
            },
        ),
    )


def test_ingesting_again_only_chunks_the_documents_not_stored_yet(tmp_path: Path) -> None:
    """Chunk each document once, linking a stored one to any further collection it is found in."""
    data = tmp_path / 'data'
    for path, text in (('missions/a.txt', 'alpha'), ('missions/b.txt', 'beta')):
        (data / path).parent.mkdir(parents=True, exist_ok=True)
        (data / path).write_text(text)
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    uow = SQLiteUnitOfWork(connection_factory=factory)
    chunker = RecordingChunker()
    ingest = IngestDocuments(LocalDocumentStreamProvider(), LocalDocumentLoader(), lambda _: chunker, uow)
    ingest.execute(_registry(data, 'missions'), str(data), ChunkingConfig())

    (data / 'missions' / 'c.txt').write_text('gamma')
    (data / 'crew').mkdir()
    (data / 'crew' / 'a_copy.txt').write_text('alpha')
    ingest.execute(_registry(data, 'missions', 'crew'), str(data), ChunkingConfig())

    assert chunker.chunked == ['alpha', 'beta', 'gamma']
    with uow as tx:
        assert (tx.documents.count_documents(), tx.documents.count_chunks()) == (3, 3)
        assert tx.documents.count_documents_by_collection() == {'missions': 3, 'crew': 1}
