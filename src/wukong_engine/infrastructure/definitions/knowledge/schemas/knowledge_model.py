"""Pydantic schema for a full knowledge model definition."""

from pydantic import BaseModel, Field, StrictStr

from .entity_type import EntityTypeSchema
from .extraction_config import ExtractionConfigSchema
from .relationship_type import RelationshipTypeSchema


class KnowledgeModelSchema(BaseModel):
    """Schema-level representation of a knowledge model definition.

    Attributes:
        extraction_config: Parameters for the extraction process.
        entity_types: Entity type definitions, keyed by entity type name.
        relationship_types: Relationship type definitions, keyed by relationship type name.
    """

    extraction_config: ExtractionConfigSchema = Field(default_factory=ExtractionConfigSchema)
    entity_types: dict[StrictStr, EntityTypeSchema] = Field(default_factory=dict)
    relationship_types: dict[StrictStr, RelationshipTypeSchema] = Field(default_factory=dict)
