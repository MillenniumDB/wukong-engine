from pathlib import Path, PurePath
from types import MappingProxyType

from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry, DocumentSource
from wukong_engine.core.documents.model.values import DocumentCollectionName

from .schemas import DocumentCollectionSchema, DocumentRegistrySchema, DocumentSourceSchema


class DocumentRegistryMapper:
    """Maps DocumentRegistry schemas to domain models."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize the mapper."""
        self._base_dir = base_dir

    def map_registry(self, schema: DocumentRegistrySchema) -> DocumentRegistry:
        """Convert a DocumentRegistrySchema to a DocumentRegistry domain model."""
        return DocumentRegistry(
            collections=MappingProxyType(
                {
                    DocumentCollectionName(name): self._map_collection(collection_schema)
                    for name, collection_schema in schema.collections.items()
                },
            ),
        )

    def _map_collection(self, schema: DocumentCollectionSchema) -> DocumentCollection:
        """Convert a DocumentCollectionSchema to a DocumentCollection domain model."""
        return DocumentCollection(
            sources=tuple(self._map_source(source_schema) for source_schema in schema.sources),
        )

    def _map_source(self, schema: DocumentSourceSchema) -> DocumentSource:
        """Convert a DocumentSourceSchema to a DocumentSource domain model."""
        return DocumentSource(
            source_path=PurePath(self._resolve_path(schema.path)),
            mode=schema.mode,
        )

    def _resolve_path(self, path: str) -> Path:
        real_path = Path(path)
        if not real_path.is_absolute():
            real_path = self._base_dir / real_path
        return real_path.expanduser().resolve()
