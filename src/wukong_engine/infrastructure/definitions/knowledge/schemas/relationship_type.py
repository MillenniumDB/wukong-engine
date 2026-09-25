"""Pydantic schemas for relationship type definitions."""

from typing import Any, ClassVar

from pydantic import BaseModel, Field, StrictStr, field_validator

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model.values import MergeStrategy, RelationshipIdentityPolicy

from .field import RelationshipFieldSchema


class EndpointContextRule(BaseModel):
    """Rules for matching relationship endpoints based on context levels.

    Every combination of a source level and a target level is an allowed context pair for the endpoint.

    Attributes:
        source_context_levels: Context levels at which the source entity may be found; a single level is turned
            into a one-item list.
        target_context_levels: Context levels at which the target entity may be found; a single level is turned
            into a one-item list.
    """

    source_context_levels: list[ContextLevel] | ContextLevel
    target_context_levels: list[ContextLevel] | ContextLevel

    @field_validator('source_context_levels', 'target_context_levels')
    @classmethod
    def normalize_context_levels(cls, value: list[ContextLevel] | ContextLevel) -> list[ContextLevel]:
        """Normalize single ContextLevel values to lists.

        Args:
            value: Validated list of context levels, or a single context level.

        Returns:
            ``value`` wrapped in a list if it's a single context level, otherwise ``value`` unchanged.
        """
        if isinstance(value, ContextLevel):
            return [value]
        return value


class RelationshipTypeSchema(BaseModel):
    """Schema-level representation of a relationship type definition.

    Attributes:
        description: Description of what the relationship represents.
        instructions: Extra extraction instructions for the relationship type, if any.
        endpoints: Allowed endpoints as source entity type name -> target entity type name -> context rule(s).
        primary_key: Name of the field used as primary key, or None if the relationship has none.
        deduplication: Policy used to deduplicate relationships of this type; accepts aliases such as "pk" or
            "edge".
        fields: Field definitions, keyed by field name.
        default_merge_strategy: Merge strategy for fields that don't define their own; accepts aliases such as
            "overwrite" or "first".
    """

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
        """Normalize deduplication strings to RelationshipIdentityPolicy members.

        Args:
            value: Raw input for the ``deduplication`` field.

        Returns:
            The matching RelationshipIdentityPolicy member if ``value`` is a known alias, otherwise ``value``
            unchanged for regular validation.
        """
        if isinstance(value, str):
            return cls._DEDUPLICATION_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('default_merge_strategy', mode='before')
    @classmethod
    def normalize_merge_strategy(cls, value: Any) -> Any:
        """Normalize default merge strategy strings to MergeStrategy members.

        Args:
            value: Raw input for the ``default_merge_strategy`` field.

        Returns:
            The matching MergeStrategy member if ``value`` is a known alias, otherwise ``value`` unchanged for
            regular validation.
        """
        if isinstance(value, str):
            return cls._MERGE_STRATEGY_ALIASES.get(value.strip().lower(), value)
        return value

    @field_validator('endpoints')
    @classmethod
    def normalize_endpoint_rules(
        cls,
        value: dict[str, dict[str, list[EndpointContextRule] | EndpointContextRule]],
    ) -> dict[str, dict[str, list[EndpointContextRule]]]:
        """Normalize single EndpointContextRule instances to lists.

        Args:
            value: Validated endpoints mapping, whose values may be single rules or lists of rules.

        Returns:
            The same mapping with every single rule wrapped in a one-item list.
        """
        normalized = {}
        for source_entity, targets in value.items():
            normalized[source_entity] = {}
            for target_entity, rules in targets.items():
                if isinstance(rules, EndpointContextRule):
                    normalized[source_entity][target_entity] = [rules]
                else:
                    normalized[source_entity][target_entity] = rules
        return normalized
