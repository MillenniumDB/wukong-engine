from pydantic import BaseModel, Field, StrictStr

from .entity_type import EntityTypeSchema


class GraphModelSchema(BaseModel):
    """Schema-level representation of a graph model definition."""

    # parameters: dict = {}
    # TODO: Validate naming here or in domain?
    entity_types: dict[StrictStr, EntityTypeSchema] = Field(default_factory=dict)
    # relationship_types: dict[StrictStr, RelationshipTypeSchema]
