import logging
from time import time

from wukong_engine.app.document_ingestion.ports import DocumentChunker, DocumentLoader, DocumentStreamProvider
from wukong_engine.app.document_ingestion.services import DocumentSourceNormalizer
from wukong_engine.app.shared import batched
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import LoadedDocument
from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry

# Logging
logger = logging.getLogger(__name__)

# Batching
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
        collections = tuple(registry.collections.values())
        with self._uow as tx:
            tx.documents.add_collections(collection.name for collection in collections)
        for collection in collections:
            self.ingest_collection(collection)
            return  # TODO: Remove after testing
        with self._uow as tx:
            total_docs = tx.documents.count_documents()
            total_chunks = tx.documents.count_chunks()
            logger.info(f'Total Documents → {total_docs}')
            logger.info(f'Total Chunks → {total_chunks}')

    def ingest_collection(self, collection: DocumentCollection) -> None:
        """Ingest a specific collection of documents into the system."""
        normalized_sources = self._source_normalizer.normalize(collection.sources)
        for doc_batch in batched(self._stream_provider.stream(normalized_sources), size=DOCUMENT_BATCH_SIZE):
            # TODO: Test chunking performance
            time_before_chunking = time()
            n = 1000000
            for _ in range(n):
                # test_doc = self._loader.load(doc_batch[0])
                test_doc = LoadedDocument(
                    metadata=doc_batch[0],
                    content="""
Ley 47 FIJA NUEVO TEXTO DE LA ORDENANZA GENERAL DE LA LEY GENERAL DE URBANISMO Y CONSTRUCCIONES,TITULO 2 DE LA PLANIFICACIÓN Y DE LOS PLANES DE INVERSIONES EN INFRAESTRUCTURA DE MOVILIDAD Y ESPACIO PÚBLICO,DISPOSICIONES COMPLEMENTARIAS,Artículo 2.1.18.(DEL ART. PRIMERO)|Artículo 2.1.18. Los instrumentos de planificación
territorial deberán reconocer las áreas de protección de
recursos de valor natural, así como definir o reconocer,
según corresponda, áreas de protección de recursos de
valor patrimonial cultural.
     Para estos efectos, se entenderán por "áreas de
protección de recursos de valor natural" todas aquellas en
que existan zonas o elementos naturales protegidos por el
ordenamiento jurídico vigente, tales como: bordes costeros
marítimos, lacustres o fluviales, parques nacionales,
reservas nacionales y monumentos naturales.
     En los casos indicados en el inciso anterior, los
instrumentos de planificación territorial podrán
establecer las condiciones urbanísticas que deberán
cumplir las edificaciones que se pretendan emplazar en
dichas áreas. Estas condiciones deberán ser compatibles
con la protección oficialmente establecida para dichas
áreas.
     Se entenderán por "áreas de protección de recursos
de valor patrimonial cultural" aquellas zonas o inmuebles de
conservación histórica que defina el plan regulador
comunal e inmuebles declarados monumentos nacionales en sus
distintas categorías, los cuales deberán ser reconocidos
por el instrumento de planificación territorial que
corresponda.
     Tratándose de áreas de protección de recursos de
valor patrimonial cultural, los instrumentos de
planificación territorial deberán establecer las normas
urbanísticas aplicables a las ampliaciones, reparaciones,
alteraciones u obras menores que se realicen en las
edificaciones existentes, así como las aplicables a las
nuevas edificaciones que se ejecuten en inmuebles que
correspondan a esta categoría, cuando corresponda. Estas
normas deberán ser compatibles con la protección
oficialmente establecida para dichas áreas.
""",
                )
                if test_doc is None:
                    return
                chunks = self._chunker.chunk(test_doc)
                if _ == 0:
                    for c in list(chunks):
                        print(
                            f'Idx: {c.chunk_index}, Length: {len(c.content)}, Offset: [{c.start_offset}-{c.end_offset}], Text: {c.content.strip()}',
                        )
            time_after_chunking = time()
            logger.info(
                f'Chunking performance test for {n} iterations: {time_after_chunking - time_before_chunking:.2f} seconds',
            )
            return
            with self._uow as tx:
                # Ingest documents
                tx.documents.bulk_upsert_documents(doc_batch)
                tx.documents.link_documents_to_collection(doc_batch, collection.name)

                # Ingest chunks
                for chunk_batch in batched(self._chunker.chunk_many(doc_batch), size=CHUNK_BATCH_SIZE):
                    tx.documents.bulk_upsert_chunks(chunk_batch)
