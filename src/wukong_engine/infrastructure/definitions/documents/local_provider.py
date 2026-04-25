import json
from pathlib import Path

from wukong_engine.app.model_ingestion.ports import DocumentRegistryProvider
from wukong_engine.core.documents.model import DocumentRegistry

from .mapper import DocumentRegistryMapper
from .schemas import DocumentRegistrySchema


class LocalDocumentRegistryProvider(DocumentRegistryProvider):
    """Loads document registry from a local JSON file."""

    def get(self, source_uri: str) -> DocumentRegistry:
        """Load a document registry from a local JSON file."""
        path = Path(source_uri)
        raw = json.load(path.open())
        schema = DocumentRegistrySchema.model_validate(raw)
        return DocumentRegistryMapper(base_dir=path.parent).map_registry(schema)
