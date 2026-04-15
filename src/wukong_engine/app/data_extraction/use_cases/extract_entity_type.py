from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.app.document_ingestion.ports import DocumentStreamProvider
from wukong_engine.app.document_ingestion.services import DocumentSourceNormalizer
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.extraction.elements import EntityExtractionRequest
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality, ContextLevel
from wukong_engine.core.graph.elements.values import EntityId, RelationshipId
from wukong_engine.core.graph.model import EntityType
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipIdentityPolicy, RelationshipTypeName


class ExtractEntityType:
    """Extract entities of a given type."""

    def __init__(
        self,
        stream_provider: DocumentStreamProvider,
        llm_client: LLMClient,
        pk_normalizer: PKNormalizer,
    ) -> None:
        """Initialize the use case with necessary dependencies."""
        self._source_normalizer = DocumentSourceNormalizer()
        self._stream_provider = stream_provider
        self._llm_client = llm_client
        self._pk_normalizer = pk_normalizer

    def execute(self, entity_type: EntityType, document_registry: DocumentRegistry) -> None:
        """Execute the entity extraction process for the given entity type."""
        # TODO: Params: change later
        context_level = ContextLevel.DOCUMENT
        cardinality = Cardinality.SINGLE
        task = EntityExtractionTask(context_level=context_level, cardinality=cardinality)

        # TODO: Execution
        # collections = entity_type.document_collections.get(context_level, ())
        # sources = document_registry.get_collection_sources(collections)
        # normalized_sources = self._source_normalizer.normalize(sources)
        # for document in self._stream_provider.stream(normalized_sources):
        #     print(f'Extracting entities from Document: {document.id}')
        #     request = EntityExtractionRequest(task=task, document=document)
        #     print(request)

        # TODO: Test runtime entities
        normalized_pk = self._pk_normalizer.normalize(' .( #123- 1|teA& Søren  Noël  key %válue  .)m')
        entity_id = EntityId.from_identity(entity_type.name, normalized_pk)
        print(f'Generated EntityId: {entity_id}')
