from pydantic import BaseModel, model_validator

from .document_set import DocumentSetSchema


class DocumentModelSchema(BaseModel):
    """Schema-level representation of a document model definition."""

    document_sets: list[DocumentSetSchema]
