import logging

from wukong_engine.app.document_ingestion.ports import DocumentStreamProvider
from wukong_engine.app.document_ingestion.services import DocumentSourceNormalizer
from wukong_engine.app.shared import batched
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry

# Logging
logger = logging.getLogger(__name__)


class IngestDocuments:
    """Use case for ingesting documents into the system."""

    def __init__(self, stream_provider: DocumentStreamProvider, uow: UnitOfWork) -> None:
        """Initialize the use case with its dependencies."""
        self._source_normalizer = DocumentSourceNormalizer()
        self._stream_provider = stream_provider
        self._uow = uow

    def execute(self, registry: DocumentRegistry) -> None:
        """Ingest all document collections into the system."""
        collections = list(registry.collections.values())
        with self._uow as tx:
            tx.documents.add_collections(collections)
        for collection in collections:
            self.ingest_collection(collection)
        with self._uow as tx:
            total_docs = tx.documents.count()
            logger.info(f'Total Documents → {total_docs}')

    def ingest_collection(self, collection: DocumentCollection) -> None:
        """Ingest a specific collection of documents into the system."""
        normalized_sources = self._source_normalizer.normalize(collection.sources)
        for batch in batched(self._stream_provider.stream(normalized_sources), size=500):
            with self._uow as tx:
                tx.documents.upsert_batch(batch)
                tx.documents.link_batch_to_collection(batch, collection)
