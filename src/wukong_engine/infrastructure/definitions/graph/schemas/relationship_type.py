from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.extraction.model.values import ContextLevel
from wukong_engine.core.graph.model.values import MergeStrategy, RelationshipIdentityPolicy

from .field import RelationshipFieldSchema


class EndpointContextRule(BaseModel):
    """Rules for matching relationship endpoints based on context levels."""

    source_context_levels: list[ContextLevel] | ContextLevel
    target_context_levels: list[ContextLevel] | ContextLevel

    @field_validator('source_context_levels', 'target_context_levels')
    @classmethod
    def normalize_context_levels(cls, value: list[ContextLevel] | ContextLevel) -> list[ContextLevel]:
        """Normalize single ContextLevel values to lists."""
        if isinstance(value, ContextLevel):
            return [value]
        return value


class RelationshipTypeSchema(BaseModel):
    """Schema-level representation of a relationship type definition."""

    description: StrictStr
    instructions: StrictStr | None = None
    endpoints: dict[StrictStr, dict[StrictStr, list[EndpointContextRule] | EndpointContextRule]] = Field(
        default_factory=dict,
    )
    primary_key: StrictStr | None = None
    deduplication: RelationshipIdentityPolicy = RelationshipIdentityPolicy.PRIMARY_KEY
    fields: dict[StrictStr, RelationshipFieldSchema] = Field(default_factory=dict)
    default_merge_strategy: MergeStrategy = MergeStrategy.KEEP

    # Mapping of various string representations to RelationshipIdentityPolicy members
    _DEDUPLICATION_ALIASES: ClassVar[dict[str, RelationshipIdentityPolicy]] = {
        'none': RelationshipIdentityPolicy.NONE,
        'disabled': RelationshipIdentityPolicy.NONE,
        'off': RelationshipIdentityPolicy.NONE,
        'endpoints': RelationshipIdentityPolicy.ENDPOINTS,
        'structural': RelationshipIdentityPolicy.ENDPOINTS,
        'edge': RelationshipIdentityPolicy.ENDPOINTS,
        'primary_key': RelationshipIdentityPolicy.PRIMARY_KEY,
        'pk': RelationshipIdentityPolicy.PRIMARY_KEY,
        'identity': RelationshipIdentityPolicy.PRIMARY_KEY,
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
        """Normalize deduplication strings to RelationshipIdentityPolicy members."""
        if isinstance(value, str):
            return cls._DEDUPLICATION_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('default_merge_strategy', mode='before')
    @classmethod
    def normalize_merge_strategy(cls, value: Any) -> Any:
        """Normalize default merge strategy strings to MergeStrategy members."""
        if isinstance(value, str):
            return cls._MERGE_STRATEGY_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('endpoints')
    @classmethod
    def normalize_endpoint_rules(
        cls,
        value: dict[str, dict[str, list[EndpointContextRule] | EndpointContextRule]],
    ) -> dict[str, dict[str, list[EndpointContextRule]]]:
        """Normalize single EndpointContextRule instances to lists."""
        normalized = {}
        for source_entity, targets in value.items():
            normalized[source_entity] = {}
            for target_entity, rules in targets.items():
                if isinstance(rules, EndpointContextRule):
                    normalized[source_entity][target_entity] = [rules]
                else:
                    normalized[source_entity][target_entity] = rules
        return normalized
