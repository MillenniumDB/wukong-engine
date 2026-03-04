from pathlib import PurePath
from types import MappingProxyType

from wukong_engine.core.documents.model import DocumentCollection, DocumentRegistry, DocumentSource
from wukong_engine.core.documents.model.values import DocumentCollectionName

from .schemas import DocumentCollectionSchema, DocumentRegistrySchema, DocumentSourceSchema


def schema_to_document_registry(schema: DocumentRegistrySchema) -> DocumentRegistry:
    """Convert a DocumentRegistrySchema to a DocumentRegistry domain model."""
    return DocumentRegistry(
        collections=MappingProxyType(
            {
                DocumentCollectionName(name): _schema_to_document_collection(collection_schema)
                for name, collection_schema in schema.collections.items()
            },
        ),
    )


def _schema_to_document_collection(schema: DocumentCollectionSchema) -> DocumentCollection:
    """Convert a DocumentCollectionSchema to a DocumentCollection domain model."""
    return DocumentCollection(
        sources=tuple(_schema_to_document_source(source_schema) for source_schema in schema.sources),
    )


def _schema_to_document_source(schema: DocumentSourceSchema) -> DocumentSource:
    """Convert a DocumentSourceSchema to a DocumentSource domain model."""
    return DocumentSource(
        path=PurePath(schema.path),
        mode=schema.mode,
    )
