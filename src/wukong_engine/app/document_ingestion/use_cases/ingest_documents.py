import logging

from wukong_engine.app.document_ingestion.exceptions import DocumentIngestionError
from wukong_engine.app.document_ingestion.ports import DocumentChunker, DocumentLoader, DocumentStreamProvider
from wukong_engine.app.document_ingestion.services import DocumentSourceNormalizer
from wukong_engine.app.shared.iterables import batched
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus

# Logging
logger = logging.getLogger(__name__)

# Constants
DOCUMENT_BATCH_SIZE = 500
CHUNK_BATCH_SIZE = 2000


class IngestDocuments:
    """Use case for ingesting documents into the system."""

    def __init__(
        self,
        stream_provider: DocumentStreamProvider,
        loader: DocumentLoader,
        chunker: DocumentChunker,
        uow: UnitOfWork,
    ) -> None:
        """Initialize the use case with its dependencies."""
        self._source_normalizer = DocumentSourceNormalizer()
        self._stream_provider = stream_provider
        self._loader = loader
        self._chunker = chunker
        self._uow = uow

    def execute(self, registry: DocumentRegistry) -> None:
        """Ingest all document collections into the system."""
        # Add collection definitions
        collections = tuple(registry.collections.values())
        with self._uow as tx:
            tx.documents.add_collections(collection.name for collection in collections)

        # Ingest all document collections
        try:
            for collection in collections:
                self._ingest_collection(collection)
                logger.info(f'Ingested Document Collection: {collection.name}')
        except DocumentIngestionError as exc:
            error = 'Document Ingestion failed due to an unrecoverable error'
            logger.error(error)
            raise DocumentIngestionError(error) from exc

        # Log ingestion stats and mark the DOCUMENTS_INGESTED checkpoint as completed
        with self._uow as tx:
            total_docs = tx.documents.count_documents()
            total_chunks = tx.documents.count_chunks()
            logger.info(f'Total Documents: {total_docs}')
            logger.info(f'Total Chunks: {total_chunks}')
            tx.pipeline.set_checkpoint_status(PipelineCheckpoint.DOCUMENTS_INGESTED, PipelineCheckpointStatus.COMPLETED)

    def _ingest_collection(self, collection: DocumentCollection) -> None:
        """Ingest a specific collection of documents into the system."""
        try:
            normalized_sources = self._source_normalizer.normalize(collection.sources)
            for doc_batch in batched(self._stream_provider.stream(normalized_sources), size=DOCUMENT_BATCH_SIZE):
                with self._uow as tx:
                    # Ingest documents
                    tx.documents.bulk_upsert_documents(doc_batch)
                    tx.documents.link_documents_to_collection(doc_batch, collection.name)

                    # Ingest chunks
                    loaded_docs = (doc for doc in self._loader.load_many(doc_batch) if doc is not None)
                    for chunk_batch in batched(self._chunker.chunk_many(loaded_docs), size=CHUNK_BATCH_SIZE):
                        tx.documents.bulk_upsert_chunks(chunk_batch)
        except Exception as exc:
            error = f'Failed to ingest Document Collection "{collection.name}"'
            logger.error(error)
            raise DocumentIngestionError(error) from exc

    def reset(self) -> None:
        """Reset the document ingestion state."""
        logger.warning('Resetting document ingestion state. This will clear ALL ingested documents and chunks...')
        with self._uow as tx:
            tx.documents.clear()
