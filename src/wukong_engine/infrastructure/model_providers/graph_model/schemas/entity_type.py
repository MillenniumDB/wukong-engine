from typing import Any

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.graph.model.values import ContextLevel

from .field import FieldSchema


class EntityTypeSchema(BaseModel):
    """Schema-level representation of an entity type definition."""

    description: StrictStr
    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    primary_key: StrictStr
    fields: dict[StrictStr, FieldSchema] = Field(default_factory=dict)
    document_groups: dict[ContextLevel, list[StrictStr] | StrictStr] = Field(default_factory=dict)
    # duplicates: StrictStr | None = None  # TODO: design

    @field_validator('instructions', mode='before')
    @classmethod
    def parse_instructions(cls, value: Any) -> Any:
        """Parse context level -> instructions mapping."""
        if isinstance(value, str):  # Apply same value to all context levels
            return dict.fromkeys(ContextLevel, value)
        return value

    @field_validator('document_groups', mode='before')
    @classmethod
    def parse_document_groups(cls, value: Any) -> Any:
        """Parse context level -> document groups mapping."""
        if isinstance(value, dict):  # Convert single string values to single-item lists
            return {k: [v] if isinstance(v, str) else v for k, v in value.items()}
        return value
