from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.extraction.model.values import ContextLevel
from wukong_engine.core.graph.model.values import EntityIdentityPolicy, MergeStrategy

from .field import EntityFieldSchema


class EntityTypeSchema(BaseModel):
    """Schema-level representation of an entity type definition."""

    description: StrictStr
    instructions: dict[ContextLevel, StrictStr] | StrictStr = Field(default_factory=dict)
    primary_key: StrictStr
    deduplication: EntityIdentityPolicy = EntityIdentityPolicy.PRIMARY_KEY
    fields: dict[StrictStr, EntityFieldSchema] = Field(default_factory=dict)
    document_collections: dict[ContextLevel, list[StrictStr] | StrictStr] = Field(default_factory=dict)
    default_merge_strategy: MergeStrategy = MergeStrategy.KEEP

    # Mapping of various string representations to EntityIdentityPolicy members
    _DEDUPLICATION_ALIASES: ClassVar[dict[str, EntityIdentityPolicy]] = {
        'primary_key': EntityIdentityPolicy.PRIMARY_KEY,
        'pk': EntityIdentityPolicy.PRIMARY_KEY,
        'identity': EntityIdentityPolicy.PRIMARY_KEY,
    }

    # Mapping of various string representations to MergeStrategy members
    _MERGE_STRATEGY_ALIASES: ClassVar[dict[str, MergeStrategy]] = {
        'keep': MergeStrategy.KEEP,
        'existing': MergeStrategy.KEEP,
        'preserve': MergeStrategy.KEEP,
        'retain': MergeStrategy.KEEP,
        'first': MergeStrategy.KEEP,
        'replace': MergeStrategy.REPLACE,
        'incoming': MergeStrategy.REPLACE,
        'overwrite': MergeStrategy.REPLACE,
        'update': MergeStrategy.REPLACE,
        'last': MergeStrategy.REPLACE,
        'longest': MergeStrategy.LONGEST,
        'verbose': MergeStrategy.LONGEST,
        'complete': MergeStrategy.LONGEST,
        'shortest': MergeStrategy.SHORTEST,
        'concise': MergeStrategy.SHORTEST,
        'minimal': MergeStrategy.SHORTEST,
    }

    @field_validator('deduplication', mode='before')
    @classmethod
    def normalize_deduplication(cls, value: Any) -> Any:
        """Normalize deduplication strings to EntityIdentityPolicy members."""
        if isinstance(value, str):
            return cls._DEDUPLICATION_ALIASES.get(value, value)
        return value

    @field_validator('default_merge_strategy', mode='before')
    @classmethod
    def normalize_merge_strategy(cls, value: Any) -> Any:
        """Normalize default merge strategy strings to MergeStrategy members."""
        if isinstance(value, str):
            return cls._MERGE_STRATEGY_ALIASES.get(value, value)
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
