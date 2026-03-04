from pydantic import BaseModel, Field, StrictStr

from .collection import DocumentCollectionSchema


class DocumentRegistrySchema(BaseModel):
    """Schema-level representation of a document registry."""

    collections: dict[StrictStr, DocumentCollectionSchema] = Field(default_factory=dict)
