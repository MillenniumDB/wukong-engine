"""Schema for document registry definitions."""

from pydantic import BaseModel, Field, StrictStr

from .collection import DocumentCollectionSchema


class DocumentRegistrySchema(BaseModel):
    """Schema-level representation of a document registry.

    Attributes:
        collections: Document collections keyed by collection name.
    """

    collections: dict[StrictStr, DocumentCollectionSchema] = Field(default_factory=dict)
