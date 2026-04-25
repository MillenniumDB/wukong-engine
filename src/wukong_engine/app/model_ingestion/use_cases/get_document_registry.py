from wukong_engine.app.model_ingestion.ports import DocumentRegistryProvider
from wukong_engine.core.documents.model import DocumentRegistry


class GetDocumentRegistry:
    def __init__(self, provider: DocumentRegistryProvider) -> None:
        self._provider = provider

    def execute(self, document_registry_uri: str) -> DocumentRegistry:
        return self._provider.get(document_registry_uri)
