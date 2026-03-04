from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.graph.model.values import ContextLevel, RelationshipDeduplicationMode

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
    deduplication_mode: RelationshipDeduplicationMode = RelationshipDeduplicationMode.NONE
    fields: dict[StrictStr, RelationshipFieldSchema] = Field(default_factory=dict)

    # Mapping of various string representations to RelationshipDeduplicationMode members
    _DEDUPLICATION_ALIASES: ClassVar[dict[str, RelationshipDeduplicationMode]] = {
        'none': RelationshipDeduplicationMode.NONE,
        'disabled': RelationshipDeduplicationMode.NONE,
        'off': RelationshipDeduplicationMode.NONE,
        'exact': RelationshipDeduplicationMode.EXACT,
        'strict': RelationshipDeduplicationMode.EXACT,
        'approximate': RelationshipDeduplicationMode.APPROXIMATE,
        'similar': RelationshipDeduplicationMode.APPROXIMATE,
        'fuzzy': RelationshipDeduplicationMode.APPROXIMATE,
        'endpoints': RelationshipDeduplicationMode.ENDPOINTS,
        'nodes': RelationshipDeduplicationMode.ENDPOINTS,
    }

    @field_validator('deduplication_mode', mode='before')
    @classmethod
    def normalize_deduplication_mode(cls, value: Any) -> Any:
        """Normalize deduplication mode strings to RelationshipDeduplicationMode members."""
        if isinstance(value, str):
            return cls._DEDUPLICATION_ALIASES.get(value, value)
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
