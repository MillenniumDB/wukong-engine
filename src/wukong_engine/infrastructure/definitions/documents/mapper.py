"""Mapper from document registry schemas to domain models."""

from pathlib import Path
from types import MappingProxyType

from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry, DocumentSource
from wukong_engine.core.documents.model.values import DocumentCollectionName

from .schemas import DocumentCollectionSchema, DocumentRegistrySchema, DocumentSourceSchema


class DocumentRegistryMapper:
    """Maps DocumentRegistry schemas to domain models."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize the mapper.

        Args:
            base_dir: Directory that source roots are resolved against.
        """
        self._base_dir = base_dir

    def map_registry(self, schema: DocumentRegistrySchema) -> DocumentRegistry:
        """Convert a DocumentRegistrySchema to a DocumentRegistry domain model.

        Args:
            schema: Parsed document registry schema.

        Returns:
            The document registry, with its collections keyed by collection name.
        """
        return DocumentRegistry(
            collections=MappingProxyType(
                {
                    DocumentCollectionName(name): self._map_collection(name, collection_schema)
                    for name, collection_schema in schema.collections.items()
                },
            ),
        )

    def _map_collection(self, name: str, schema: DocumentCollectionSchema) -> DocumentCollection:
        """Convert a DocumentCollectionSchema to a DocumentCollection domain model.

        Args:
            name: Name of the collection, taken from its key in the registry.
            schema: Parsed collection schema.

        Returns:
            The document collection with its sources mapped to domain models.
        """
        return DocumentCollection(
            name=DocumentCollectionName(name),
            sources=tuple(self._map_source(source_schema) for source_schema in schema.sources),
        )

    def _map_source(self, schema: DocumentSourceSchema) -> DocumentSource:
        """Convert a DocumentSourceSchema to a DocumentSource domain model.

        Args:
            schema: Parsed source schema.

        Returns:
            The document source, with its root resolved against the base directory.
        """
        return DocumentSource(
            root=str(self._resolve_path(schema.root)),
            mode=schema.mode,
        )

    def _resolve_path(self, path: str) -> Path:
        """Resolve a source root against the base directory.

        Args:
            path: Source root, relative to the base directory or absolute.

        Returns:
            The absolute, resolved path.
        """
        real_path = self._base_dir / path
        return real_path.resolve()
