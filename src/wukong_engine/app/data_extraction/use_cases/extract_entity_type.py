from wukong_engine.app.document_ingestion.ports import DocumentStreamProvider
from wukong_engine.app.document_ingestion.services import DocumentSourceNormalizer
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.core.graph.model import EntityType
from wukong_engine.core.graph.model.values import ContextLevel


class ExtractEntityType:
    def __init__(self, stream_provider: DocumentStreamProvider) -> None:
        self._source_normalizer = DocumentSourceNormalizer()
        self._stream_provider = stream_provider

    def execute(self, entity_type: EntityType, document_registry: DocumentRegistry) -> None:
        sources = document_registry.get_entity_sources(entity_type, ContextLevel.DOCUMENT)
        normalized_sources = self._source_normalizer.normalize(sources)
        for document in self._stream_provider.stream(normalized_sources):
            print(f'Extracting entities for: {document.id}')
