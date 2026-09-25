"""Mapper from knowledge model schemas to domain models."""

from types import MappingProxyType
from typing import Any

from wukong_engine.core.documents.model.values import ContextLevel, DocumentCollectionName, EndpointContext
from wukong_engine.core.knowledge.model import (
    Endpoint,
    EntityField,
    EntityType,
    ExtractionConfig,
    KnowledgeModel,
    RelationshipField,
    RelationshipType,
)
from wukong_engine.core.knowledge.model.values import (
    EntityTypeName,
    FieldName,
    RelationshipTypeName,
)
from wukong_engine.core.shared import RegexPattern

from .schemas import (
    EndpointContextRule,
    EntityFieldSchema,
    EntityTypeSchema,
    ExtractionConfigSchema,
    KnowledgeModelSchema,
    RelationshipFieldSchema,
    RelationshipTypeSchema,
)


class KnowledgeModelMapper:
    """Maps KnowledgeModel schemas to domain models."""

    def map_knowledge_model(self, schema: KnowledgeModelSchema) -> KnowledgeModel:
        """Convert a KnowledgeModelSchema to a KnowledgeModel domain model.

        Args:
            schema: Parsed knowledge model schema.

        Returns:
            The knowledge model, with entity and relationship types keyed by name.
        """
        return KnowledgeModel(
            extraction_config=self._map_extraction_config(schema.extraction_config),
            entity_types=MappingProxyType(
                {
                    EntityTypeName(name): self._map_entity_type(name, schema)
                    for name, schema in schema.entity_types.items()
                },
            ),
            relationship_types=MappingProxyType(
                {
                    RelationshipTypeName(name): self._map_relationship_type(name, schema)
                    for name, schema in schema.relationship_types.items()
                },
            ),
        )

    def _map_extraction_config(self, schema: ExtractionConfigSchema) -> ExtractionConfig:
        """Convert an ExtractionConfigSchema to an ExtractionConfig domain model.

        Args:
            schema: Parsed extraction config schema.

        Returns:
            The extraction config; projections stay None when the schema leaves them unset (all types enabled).
        """
        return ExtractionConfig(
            domain=schema.llm.domain,
            language=schema.llm.language,
            entity_projection=frozenset(EntityTypeName(name) for name in schema.projection.enabled_entities)
            if schema.projection.enabled_entities is not None
            else None,
            relationship_projection=frozenset(
                RelationshipTypeName(name) for name in schema.projection.enabled_relationships
            )
            if schema.projection.enabled_relationships is not None
            else None,
        )

    def _map_entity_type(self, name: str, schema: EntityTypeSchema) -> EntityType:
        """Convert an EntityTypeSchema to an EntityType domain model.

        Args:
            name: Name of the entity type, taken from its key in the knowledge model.
            schema: Parsed entity type schema.

        Returns:
            The entity type with its fields and document collections mapped to domain values.
        """
        return EntityType(
            name=EntityTypeName(name),
            description=schema.description,
            instructions=MappingProxyType(_as_dict(schema.instructions)),
            primary_key=FieldName(schema.primary_key),
            identity_policy=schema.deduplication,
            fields=MappingProxyType(
                {FieldName(name): self._map_entity_field(name, schema) for name, schema in schema.fields.items()},
            ),
            document_collections=MappingProxyType(
                {
                    k: tuple(DocumentCollectionName(c) for c in _as_list(v))
                    for k, v in schema.document_collections.items()
                },
            ),
            default_merge_strategy=schema.default_merge_strategy,
        )

    def _map_relationship_type(self, name: str, schema: RelationshipTypeSchema) -> RelationshipType:
        """Convert a RelationshipTypeSchema to a RelationshipType domain model.

        Args:
            name: Name of the relationship type, taken from its key in the knowledge model.
            schema: Parsed relationship type schema.

        Returns:
            The relationship type with its endpoints and fields mapped to domain values.
        """
        return RelationshipType(
            name=RelationshipTypeName(name),
            description=schema.description,
            instructions=schema.instructions,
            endpoints=self._materialize_endpoints(schema.endpoints),
            primary_key=FieldName(schema.primary_key) if schema.primary_key is not None else None,
            identity_policy=schema.deduplication,
            fields=MappingProxyType(
                {FieldName(name): self._map_relationship_field(name, schema) for name, schema in schema.fields.items()},
            ),
            default_merge_strategy=schema.default_merge_strategy,
        )

    def _map_entity_field(self, name: str, schema: EntityFieldSchema) -> EntityField:
        """Convert an EntityFieldSchema to an EntityField domain model.

        Args:
            name: Name of the field, taken from its key in the entity type.
            schema: Parsed entity field schema.

        Returns:
            The entity field with its per-context-level settings as read-only mappings.
        """
        return EntityField(
            name=FieldName(name),
            data_type=schema.data_type,
            description=schema.description,
            instructions=MappingProxyType(_as_dict(schema.instructions)),
            options=tuple(_as_list(schema.options)),
            examples=tuple(_as_list(schema.examples)),
            regex=MappingProxyType({k: RegexPattern(v) for k, v in _as_dict(schema.regex).items()}),
            default_value=MappingProxyType(_as_dict(schema.default_value)),
            retrieval_mode=MappingProxyType(_as_dict(schema.retrieval_mode)),
            required=schema.required,
            merge_strategy=schema.merge_strategy,
        )

    def _map_relationship_field(self, name: str, schema: RelationshipFieldSchema) -> RelationshipField:
        """Convert a RelationshipFieldSchema to a RelationshipField domain model.

        Args:
            name: Name of the field, taken from its key in the relationship type.
            schema: Parsed relationship field schema.

        Returns:
            The relationship field.
        """
        return RelationshipField(
            name=FieldName(name),
            data_type=schema.data_type,
            description=schema.description,
            instructions=schema.instructions,
            options=tuple(_as_list(schema.options)),
            examples=tuple(_as_list(schema.examples)),
            regex=RegexPattern(schema.regex) if schema.regex is not None else None,
            default_value=schema.default_value,
            retrieval_mode=schema.retrieval_mode,
            required=schema.required,
            merge_strategy=schema.merge_strategy,
        )

    def _materialize_endpoints(
        self,
        endpoints: dict[str, dict[str, list[EndpointContextRule] | EndpointContextRule]],
    ) -> tuple[Endpoint, ...]:
        """Materialize the relationship endpoints from the schema into the domain model format.

        Every rule for a source/target entity type pair is expanded into all combinations of its source and target
        context levels; the resulting pairs are deduplicated and sorted.

        Args:
            endpoints: Endpoint rules keyed by source entity type name, then by target entity type name.

        Returns:
            One endpoint per source/target entity type pair, with its allowed context level pairs.
        """
        endpoint_mapping: dict[
            tuple[EntityTypeName, EntityTypeName],
            tuple[tuple[ContextLevel, ContextLevel], ...],
        ] = {}
        for source, targets in endpoints.items():
            for target, rules in targets.items():
                # Collect all context level pairs for this entity type pair
                context_pairs = set()
                for rule in _as_list(rules):  # Generate all combinations of source and target context levels
                    for source_level in rule.source_context_levels:
                        for target_level in rule.target_context_levels:
                            context_pairs.add((source_level, target_level))

                # Add materialized combinations to the resulting mapping
                key = (EntityTypeName(source), EntityTypeName(target))
                endpoint_mapping[key] = tuple(sorted(context_pairs, key=lambda pair: (pair[0].value, pair[1].value)))

        # Convert to Endpoint domain models
        materialized_endpoints = []
        for (src, tgt), context_pairs in endpoint_mapping.items():
            endpoint_context_pairs = tuple(
                EndpointContext(source_level=src_level, target_level=tgt_level)
                for src_level, tgt_level in context_pairs
            )
            materialized_endpoints.append(
                Endpoint(
                    source=src,
                    target=tgt,
                    context_pairs=endpoint_context_pairs,
                ),
            )
        return tuple(materialized_endpoints)


def _as_dict(value: Any) -> dict:
    """Return the value unchanged after checking that it is a dictionary.

    Args:
        value: Value expected to be a dictionary (already normalized by the schema).

    Returns:
        The same value.

    Raises:
        TypeError: If the value is not a dictionary.
    """
    if not isinstance(value, dict):
        raise TypeError(f'Mapping Error: expected a dictionary, got {type(value)} instead')
    return value


def _as_list(value: Any) -> list:
    """Return the value unchanged after checking that it is a list.

    Args:
        value: Value expected to be a list (already normalized by the schema).

    Returns:
        The same value.

    Raises:
        TypeError: If the value is not a list.
    """
    if not isinstance(value, list):
        raise TypeError(f'Mapping Error: expected a list, got {type(value)} instead')
    return value
