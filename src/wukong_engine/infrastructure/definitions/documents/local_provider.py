"""Document registry provider backed by a local JSON file."""

from pathlib import Path

from wukong_engine.app.model_ingestion.ports import DocumentRegistryProvider
from wukong_engine.core.documents.model import DocumentRegistry
from wukong_engine.infrastructure.storage.filesystem import load_json_file

from .mapper import DocumentRegistryMapper
from .schemas import DocumentRegistrySchema


class LocalDocumentRegistryProvider(DocumentRegistryProvider):
    """Loads document registry from a local JSON file."""

    def get(self, source_uri: str, data_uri: str) -> DocumentRegistry:
        """Load a document registry from a local JSON file, considering a base data uri for resolving paths.

        Args:
            source_uri: Path to the JSON file defining the document registry; ``~`` is expanded.
            data_uri: Base data directory that relative source roots are resolved against; ``~`` is expanded.

        Returns:
            The document registry with every source root resolved to an absolute path.
        """
        registry_path = Path(source_uri).expanduser().resolve()
        data_path = Path(data_uri).expanduser().resolve()
        raw_registry = load_json_file(registry_path)
        registry_schema = DocumentRegistrySchema.model_validate(raw_registry)
        return DocumentRegistryMapper(base_dir=data_path).map_registry(registry_schema)
