from wukong_engine.app.document_ingestion.ports import DocumentStreamProvider
from wukong_engine.app.document_ingestion.services import DocumentSourceNormalizer
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.extraction.elements import EntityExtractionRequest
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality, ContextLevel
from wukong_engine.core.graph.model import EntityType


class ExtractEntityType:
    def __init__(self, stream_provider: DocumentStreamProvider) -> None:
        self._source_normalizer = DocumentSourceNormalizer()
        self._stream_provider = stream_provider

    def execute(self, entity_type: EntityType, document_registry: DocumentRegistry) -> None:
        # TODO: Params: change later
        context_level = ContextLevel.DOCUMENT
        cardinality = Cardinality.SINGLE
        task = EntityExtractionTask(entity_type=entity_type, context_level=context_level, cardinality=cardinality)

        # Execution
        sources = document_registry.get_entity_sources(entity_type, context_level)
        normalized_sources = self._source_normalizer.normalize(sources)
        for document in self._stream_provider.stream(normalized_sources):
            print(f'Extracting entities for: {document.id}')
            request = EntityExtractionRequest(task=task, document=document)
            print(request)
