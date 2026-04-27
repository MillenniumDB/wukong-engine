from wukong_engine.app.document_ingestion.ports import DocumentSourceValidator
from wukong_engine.app.model_ingestion.ports import DocumentRegistryProvider
from wukong_engine.core.documents.model import DocumentRegistry


class GetDocumentRegistry:
    """Use case for retrieving the document registry from a specified URI."""

    def __init__(self, provider: DocumentRegistryProvider, validator: DocumentSourceValidator) -> None:
        """Initialize the use case with its dependencies."""
        self._provider = provider
        self._validator = validator

    def execute(self, document_registry_uri: str) -> DocumentRegistry:
        """Retrieve the document registry from the specified URI."""
        document_registry = self._provider.get(document_registry_uri)
        self._validator.validate(document_registry.get_all_sources())
        return document_registry
