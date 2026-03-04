from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.graph.model.values import ContextLevel, EntityDeduplicationMode

from .field import EntityFieldSchema


class EntityTypeSchema(BaseModel):
    """Schema-level representation of an entity type definition."""

    description: StrictStr
    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    primary_key: StrictStr
    deduplication_mode: EntityDeduplicationMode = EntityDeduplicationMode.NONE
    fields: dict[StrictStr, EntityFieldSchema] = Field(default_factory=dict)
    document_collections: dict[ContextLevel, list[StrictStr] | StrictStr] = Field(default_factory=dict)

    # Mapping of various string representations to EntityDeduplicationMode members
    _DEDUPLICATION_ALIASES: ClassVar[dict[str, EntityDeduplicationMode]] = {
        'none': EntityDeduplicationMode.NONE,
        'disabled': EntityDeduplicationMode.NONE,
        'off': EntityDeduplicationMode.NONE,
        'exact': EntityDeduplicationMode.EXACT,
        'strict': EntityDeduplicationMode.EXACT,
        'approximate': EntityDeduplicationMode.APPROXIMATE,
        'similar': EntityDeduplicationMode.APPROXIMATE,
        'fuzzy': EntityDeduplicationMode.APPROXIMATE,
    }

    @field_validator('deduplication_mode', mode='before')
    @classmethod
    def normalize_deduplication_mode(cls, value: Any) -> Any:
        """Normalize deduplication mode strings to EntityDeduplicationMode members."""
        if isinstance(value, str):
            return cls._DEDUPLICATION_ALIASES.get(value, value)
        return value

    @field_validator('instructions')
    @classmethod
    def normalize_instructions(cls, value: dict[ContextLevel, str] | str) -> dict[ContextLevel, str]:
        """Normalize instructions to a context level -> instruction mapping."""
        if isinstance(value, str):
            return dict.fromkeys(ContextLevel, value)
        return value

    @field_validator('document_collections')
    @classmethod
    def normalize_document_collections(
        cls,
        value: dict[ContextLevel, list[str] | str],
    ) -> dict[ContextLevel, list[str]]:
        """Normalize document collections to a context level -> list of document collections mapping."""
        return {k: [v] if isinstance(v, str) else v for k, v in value.items()}
