from pydantic import BaseModel, model_validator

from .groups import DocumentGroupSchema


class DocumentSchema(BaseModel):
    """Schema-level representation of a document model definition."""

    document_sets: list[DocumentGroupSchema]
