from wukong_engine.app.document_ingestion.ports import DocumentSourceValidator
from wukong_engine.core.documents.model import DocumentRegistry


class ValidateDocumentSources:
    def __init__(self, validator: DocumentSourceValidator) -> None:
        self._validator = validator

    def execute(self, document_registry: DocumentRegistry) -> None:
        sources = document_registry.get_all_sources()
        self._validator.validate(sources)
