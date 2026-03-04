from pydantic import BaseModel, Field

from .source import DocumentSourceSchema


class DocumentCollectionSchema(BaseModel):
    """Schema-level representation of a document collection."""

    sources: list[DocumentSourceSchema] = Field(default_factory=list)
