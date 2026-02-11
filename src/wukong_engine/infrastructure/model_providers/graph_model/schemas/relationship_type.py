from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.graph.model.values import ContextLevel, DeduplicationMode

from .field import FieldSchema


class RelationshipTypeSchema(BaseModel):
    """Schema-level representation of a relationship type definition."""

    description: StrictStr
    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    primary_key: StrictStr
    fields: dict[StrictStr, FieldSchema] = Field(default_factory=dict)
    deduplication: DeduplicationMode = DeduplicationMode.NONE

    # Mapping of various string representations to DeduplicationMode members
    _DEDUPLICATION_ALIASES: ClassVar[dict[str, DeduplicationMode]] = {
        'none': DeduplicationMode.NONE,
        'disabled': DeduplicationMode.NONE,
        'off': DeduplicationMode.NONE,
        'exact': DeduplicationMode.EXACT,
        'strict': DeduplicationMode.EXACT,
        'approximate': DeduplicationMode.APPROXIMATE,
        'similar': DeduplicationMode.APPROXIMATE,
        'fuzzy': DeduplicationMode.APPROXIMATE,
    }

    @field_validator('instructions', mode='before')
    @classmethod
    def parse_instructions(cls, value: Any) -> Any:
        """Parse context level -> instructions mapping."""
        if isinstance(value, str):  # Apply same value to all context levels
            return dict.fromkeys(ContextLevel, value)
        return value

    @field_validator('deduplication', mode='before')
    @classmethod
    def normalize_deduplication(cls, value: Any) -> Any:
        """Normalize deduplication strings to DeduplicationMode members."""
        if isinstance(value, str):
            return cls._DEDUPLICATION_ALIASES.get(value, value)
        return value
