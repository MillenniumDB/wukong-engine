"""Schema for document collection definitions."""

from pydantic import BaseModel, Field

from .source import DocumentSourceSchema


class DocumentCollectionSchema(BaseModel):
    """Schema-level representation of a document collection.

    Attributes:
        sources: Sources whose documents belong to the collection.
    """

    sources: list[DocumentSourceSchema] = Field(default_factory=list)
