from pydantic import BaseModel, Field, StrictStr

from .entity_type import EntityTypeSchema
from .extraction_config import ExtractionConfigSchema
from .relationship_type import RelationshipTypeSchema


class KnowledgeModelSchema(BaseModel):
    """Schema-level representation of a knowledge model definition."""

    extraction_config: ExtractionConfigSchema = Field(default_factory=ExtractionConfigSchema)
    entity_types: dict[StrictStr, EntityTypeSchema] = Field(default_factory=dict)
    relationship_types: dict[StrictStr, RelationshipTypeSchema] = Field(default_factory=dict)
