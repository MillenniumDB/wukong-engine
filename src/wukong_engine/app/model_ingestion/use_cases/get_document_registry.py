"""Use case for loading the document registry."""

import logging

from wukong_engine.app.document_ingestion.ports import DocumentSourceValidator
from wukong_engine.app.model_ingestion.exceptions import ModelIngestionError
from wukong_engine.app.model_ingestion.ports import DocumentRegistryProvider
from wukong_engine.core.documents.model import DocumentRegistry

# Logging
logger = logging.getLogger(__name__)


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

    def execute(self, document_registry_uri: str, data_uri: str, *, validate_sources: bool = True) -> DocumentRegistry:
        """Retrieve the document registry from the specified URI and validate its sources.

        Args:
            document_registry_uri: Location of the document registry definition.
            data_uri: Base data location that sources are resolved against and must be contained in.
            validate_sources: Whether to check that the sources exist in the data location, which only matters when
                documents are going to be ingested from them.

        Returns:
            The loaded document registry.

        Raises:
            ModelIngestionError: If the registry can't be read or is invalid, or any of its validated sources is
                invalid.
        """
        try:
            document_registry = self._provider.get(source_uri=document_registry_uri, data_uri=data_uri)
            if validate_sources:
                self._validator.validate(sources=document_registry.get_all_sources(), data_uri=data_uri)
        except Exception as exc:
            error = f'Failed to load the document collections from "{document_registry_uri}": {exc}'
            logger.error(error)
            raise ModelIngestionError(error) from exc
        return document_registry
