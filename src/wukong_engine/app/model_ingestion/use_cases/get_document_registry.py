"""Use case for loading the document registry."""

from wukong_engine.app.document_ingestion.ports import DocumentSourceValidator
from wukong_engine.app.model_ingestion.ports import DocumentRegistryProvider
from wukong_engine.core.documents.model import DocumentRegistry


class GetDocumentRegistry:
    """Use case for retrieving the document registry from a specified URI."""

    def __init__(self, provider: DocumentRegistryProvider, validator: DocumentSourceValidator) -> None:
        """Initialize the use case with its dependencies.

        Args:
            provider: Provider used to load the document registry.
            validator: Validator used to check the registry's document sources.
        """
        self._provider = provider
        self._validator = validator

    def execute(self, document_registry_uri: str, data_uri: str) -> DocumentRegistry:
        """Retrieve the document registry from the specified URI and validate its sources.

        Args:
            document_registry_uri: Location of the document registry definition.
            data_uri: Base data location that sources are resolved against and must be contained in.

        Returns:
            The loaded document registry.

        Raises:
            ValueError: If the registry is invalid or any of its sources fails validation.
        """
        document_registry = self._provider.get(source_uri=document_registry_uri, data_uri=data_uri)
        self._validator.validate(sources=document_registry.get_all_sources(), data_uri=data_uri)
        return document_registry
