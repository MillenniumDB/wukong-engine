import json
from pathlib import Path

from wukong_engine.app.model_ingestion.ports import DocumentRegistryProvider
from wukong_engine.core.documents.model import DocumentRegistry

from .mappers import DocumentRegistryMapper
from .schemas import DocumentRegistrySchema


# TODO: Catch pydantic errors and raise DocumentRegistryLoadError or similar
# TODO: See if file_utils is used as a helper in infra
# TODO: Errors from file reading
class LocalDocumentRegistryProvider(DocumentRegistryProvider):
    """Loads document registry from a local JSON file."""

    def get(self, path: Path) -> DocumentRegistry:
        """Load a document registry from a local JSON file."""
        raw = json.load(path.open())
        schema = DocumentRegistrySchema.model_validate(raw)
        return DocumentRegistryMapper(base_dir=path.parent).map_registry(schema)
