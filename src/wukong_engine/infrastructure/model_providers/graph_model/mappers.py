from types import MappingProxyType
from typing import Any

from wukong_engine.core.graph.model import EntityType, ExtractionConfig, Field, GraphModel, RelationshipType
from wukong_engine.core.graph.model.values import (
    ContextLevel,
    EntityTypeName,
    FieldName,
    RegexPattern,
    RelationshipTypeName,
)

from .schemas import (
    EndpointContextRule,
    EntityTypeSchema,
    ExtractionSchema,
    FieldSchema,
    GraphModelSchema,
    RelationshipTypeSchema,
)


def schema_to_graph_model(schema: GraphModelSchema) -> GraphModel:
    """Convert a GraphModelSchema to a GraphModel domain model."""
    return GraphModel(
        extraction_config=_schema_to_extraction_config(schema.extraction),
        entity_types=MappingProxyType(
            {EntityTypeName(name): _schema_to_entity_type(schema) for name, schema in schema.entity_types.items()},
        ),
        relationship_types=MappingProxyType(
            {
                RelationshipTypeName(name): _schema_to_relationship_type(schema)
                for name, schema in schema.relationship_types.items()
            },
        ),
    )


def _schema_to_extraction_config(schema: ExtractionSchema) -> ExtractionConfig:
    """Convert an ExtractionSchema to an ExtractionConfig domain model."""
    return ExtractionConfig(
        llm_persona=schema.llm.persona,
        document_context=schema.llm.document_context,
        input_language=schema.language.input,
        output_language=schema.language.output,
        entity_projection=frozenset(EntityTypeName(name) for name in schema.projection.enabled_entities)
        if schema.projection.enabled_entities is not None
        else None,
        relationship_projection=frozenset(
            RelationshipTypeName(name) for name in schema.projection.enabled_relationships
        )
        if schema.projection.enabled_relationships is not None
        else None,
    )


def _schema_to_entity_type(schema: EntityTypeSchema) -> EntityType:
    """Convert an EntityTypeSchema to an EntityType domain model."""
    return EntityType(
        description=schema.description,
        instructions=MappingProxyType(_as_dict(schema.instructions)),
        primary_key=FieldName(schema.primary_key),
        deduplication_mode=schema.deduplication_mode,
        fields=MappingProxyType({FieldName(name): _schema_to_field(schema) for name, schema in schema.fields.items()}),
        document_collections=MappingProxyType(
            {k: frozenset(_as_list(v)) for k, v in schema.document_collections.items()},
        ),
    )


def _schema_to_relationship_type(schema: RelationshipTypeSchema) -> RelationshipType:
    """Convert a RelationshipTypeSchema to a RelationshipType domain model."""
    return RelationshipType(
        description=schema.description,
        instructions=schema.instructions,
        endpoints=_materialize_endpoints(schema.endpoints),
        primary_key=FieldName(schema.primary_key) if schema.primary_key is not None else None,
        deduplication_mode=schema.deduplication_mode,
        fields=MappingProxyType({FieldName(name): _schema_to_field(schema) for name, schema in schema.fields.items()}),
    )


def _schema_to_field(schema: FieldSchema) -> Field:
    """Convert a FieldSchema to a Field domain model."""
    return Field(
        data_type=schema.data_type,
        description=schema.description,
        instructions=MappingProxyType(_as_dict(schema.instructions)),
        options=tuple(_as_list(schema.options)),
        examples=tuple(_as_list(schema.examples)),
        regex=MappingProxyType({k: RegexPattern(v) for k, v in _as_dict(schema.regex).items()}),
        default_value=MappingProxyType(_as_dict(schema.default_value)),
        retrieval_mode=MappingProxyType(_as_dict(schema.retrieval_mode)),
        required=schema.required,
    )


def _materialize_endpoints(
    endpoints: dict[str, dict[str, list[EndpointContextRule] | EndpointContextRule]],
) -> MappingProxyType[tuple[EntityTypeName, EntityTypeName], frozenset[tuple[ContextLevel, ContextLevel]]]:
    """Materialize the relationship endpoints from the schema into the domain model format."""
    result = {}
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
            result[key] = frozenset(context_pairs)

    return MappingProxyType(result)


def _as_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        raise TypeError(f'Mapping Error: expected a dictionary, got {type(value)} instead')
    return value


def _as_list(value: Any) -> list:
    if not isinstance(value, list):
        raise TypeError(f'Mapping Error: expected a list, got {type(value)} instead')
    return value
