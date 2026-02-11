from pydantic import BaseModel, Field, StrictStr

from .entity_type import EntityTypeSchema
from .extraction import ExtractionSchema
from .relationship_type import RelationshipTypeSchema


class GraphModelSchema(BaseModel):
    """Schema-level representation of a graph model definition."""

    extraction: ExtractionSchema = Field(default_factory=ExtractionSchema)
    entity_types: dict[StrictStr, EntityTypeSchema] = Field(default_factory=dict)
    relationship_types: dict[StrictStr, RelationshipTypeSchema] = Field(default_factory=dict)
